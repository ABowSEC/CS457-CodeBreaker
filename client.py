"""Code-Breaker console client.

Usage:
    python3 client.py -h
    python3 client.py -i server.bowman.edu -p 8080
    python3 client.py -i localhost -p 8080 -a Alice

Design:
    * The server hostname is resolved through DNS (socket.gethostbyname);
      no IP address is hard-coded.  Resolution failures exit cleanly.
    * A background *receiver thread* reads framed messages from the server,
      validates them, prints them, and updates shared client state.
    * The *main thread* only reads keyboard input, and only when input is
      actually needed (it is our turn, or a rematch question is open).
"""

import argparse
import socket
import sys
import threading

import protocol as proto

RECV_SIZE = 4096
CONNECT_TIMEOUT = 10        # seconds to wait for the TCP handshake

LINE = "-" * 52


class ClientState:
    """State shared between the receiver thread and the input thread."""

    def __init__(self):
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self.my_number = None
        self.aliases = {}          # {player_number: alias}
        self.turn_id = None
        self.active_player = None
        self.phase = "CONNECTING"  # LOBBY / PLAYING / GAME_OVER / DONE
        self.history = []          # [(turn, player, guess, cp, wp)]
        self.need_alias = False    # server rejected our alias
        self.alias = None

    def name(self, number):
        return self.aliases.get(number, f"Player {number}")


# ----------------------------------------------------------------------
# Rendering helpers (pure printing, no state changes)
# ----------------------------------------------------------------------

def show(text=""):
    print(text, flush=True)


def render_board(state):
    """Print every guess made in this round as a small table."""
    show(LINE)
    show(f" {'Turn':>4} | {'Player':<14} | {'Guess':^5} | "
         f"{'Right':^5} | {'Moved':^5}")
    show(LINE)
    if not state.history:
        show("  (no guesses yet)")
    for turn, player, guess, cp, wp in state.history:
        who = f"P{player} {state.name(player)}"[:14]
        if guess is None:
            show(f" {turn:>4} | {who:<14} | {'--':^5} | "
                 f"{'skip':^5} | {'':^5}")
        else:
            show(f" {turn:>4} | {who:<14} | {guess:^5} | "
                 f"{cp:^5} | {wp:^5}")
    show(LINE)


def render_scores(state, counters, attempt_limit=10):
    parts = []
    for c in counters:
        n = c["player_number"]
        parts.append(f"P{n} {state.name(n)}: {c['attempt_count']}/"
                     f"{attempt_limit} attempts, {c['miss_turn']} missed")
    show(" Score  " + "  |  ".join(parts))


def render_turn_status(state, seconds):
    if state.active_player == state.my_number:
        show(f"\n>>> YOUR TURN (turn {state.turn_id}, {seconds}s) <<<")
        show("Enter 4 unique digits, or 'quit' to leave.")
    else:
        show(f"\nWaiting for {state.name(state.active_player)}'s "
             f"guess... (turn {state.turn_id})")


def render_leaderboard(board):
    show(" Leaderboard (session)")
    show(f"  {'#':>2}  {'Player':<20} {'Wins':>4} {'Guesses':>8}")
    for rank, entry in enumerate(board, start=1):
        show(f"  {rank:>2}  {entry['alias']:<20} "
             f"{entry['rounds_won']:>4} {entry['total_guesses']:>8}")


# ----------------------------------------------------------------------
# Incoming message handling (runs in the receiver thread)
# ----------------------------------------------------------------------

def handle_message(state, msg_type, p):
    """Update shared state for one server message and print it."""
    with state.lock:
        if msg_type == proto.LOBBY_WAIT:
            state.my_number = p["player_number"]
            state.alias = p["alias"]
            state.aliases = {state.my_number: p["alias"]}
            state.phase = "LOBBY"
            show(f"\nRegistered as Player {p['player_number']} "
                 f"({p['alias']}). {p['message']}")
            show("Waiting for Player 2...")

        elif msg_type == proto.GAME_START:
            state.my_number = p["player_number"]
            state.aliases = {pl["player_number"]: pl["alias"]
                             for pl in p["players"]}
            state.turn_id = p["turn_id"]
            state.active_player = p["active_player"]
            state.history = []
            state.phase = "PLAYING"
            show("\n" + "=" * 52)
            show(" GAME START: "
                 + " vs ".join(f"P{n} {a}"
                               for n, a in sorted(state.aliases.items())))
            show(f" You are Player {state.my_number}. Crack the "
                 f"{p['code_length']}-digit code (unique digits), "
                 f"{p['attempt_limit']} attempts each.")
            show("=" * 52)
            render_turn_status(state, p["turn_seconds"])

        elif msg_type == proto.STATE_UPDATE:
            prev = p["previous_player"]
            state.history.append((state.turn_id, prev, p["guess"],
                                  p["correct_position"],
                                  p["wrong_position"]))
            if p["event"] == "TURN_SKIPPED":
                show(f"\n{state.name(prev)} ran out of time; "
                     f"turn skipped (costs one attempt).")
            else:
                show(f"\n{state.name(prev)} guessed {p['guess']}: "
                     f"{p['correct_position']} right place, "
                     f"{p['wrong_position']} wrong place.")
            state.turn_id = p["turn_id"]
            state.active_player = p["active_player"]
            render_board(state)
            render_scores(state, p["players"])
            render_turn_status(state, p["turn_seconds"])

        elif msg_type == proto.ERROR:
            show(f"\n[SERVER ERROR] {p['code']}: {p['message']}")
            if p["code"] == proto.E_INVALID_ALIAS:
                state.need_alias = True
            elif p["code"] == proto.E_ROOM_FULL:
                state.phase = "DONE"
            elif (state.phase == "PLAYING"
                  and state.active_player in (None, state.my_number)):
                # active_player is None while our MOVE awaits a reply.
                show("Still your turn. Try again.")

        elif msg_type == proto.GAME_OVER:
            state.phase = "GAME_OVER"
            if p["final_guess"] and p["reason"] == "CODE_SOLVED":
                state.history.append((state.turn_id, p["winner"],
                                      p["final_guess"], 4, 0))
            show("\n" + "=" * 52)
            if p["outcome"] == "DRAW":
                headline = "DRAW"
            elif p["winner"] == state.my_number:
                headline = "YOU WIN!"
            else:
                headline = f"{state.name(p['winner'])} WINS"
            show(f" GAME OVER: {headline} ({p['outcome']}, {p['reason']})")
            show(f" {p['message']}")
            show(f" Secret code was {p['secret_code']}")
            show("=" * 52)
            render_board(state)
            render_scores(state, p["players"])
            render_leaderboard(p["leaderboard"])

        state.changed.notify_all()


def receiver(sock, state):
    """Background thread: read frames until the connection ends."""
    inbox = proto.FrameBuffer()
    try:
        while True:
            data = sock.recv(RECV_SIZE)
            if not data:                       # server closed (EOF)
                break
            inbox.feed(data)
            for raw in inbox.frames():
                try:
                    msg = proto.decode_payload(raw)
                    msg_type, payload = proto.validate_message(
                        msg, proto.SERVER_MESSAGES)
                except proto.ProtocolError as exc:
                    show(f"[WARN] Ignoring bad server message: "
                         f"{exc.message}")
                    continue
                handle_message(state, msg_type, payload)
    except proto.FrameError as exc:
        show(f"[WARN] Corrupt stream from server ({exc}).")
    except OSError:
        pass                                   # socket closed / reset
    with state.lock:
        if state.phase != "DONE":
            show("\nConnection to server closed.")
        state.phase = "DONE"
        state.changed.notify_all()


# ----------------------------------------------------------------------
# Outgoing messages + input loop (main thread)
# ----------------------------------------------------------------------

def send(sock, msg_type, payload):
    sock.sendall(proto.encode_message(msg_type, payload))


def read_line(prompt):
    """input() that treats Ctrl+D / Ctrl+C / closed stdin as 'quit'."""
    try:
        line = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return "quit"
    if not sys.stdin.isatty():
        print(line, flush=True)    # echo scripted input so logs show it
    return line


def ask_alias():
    while True:
        alias = read_line("Choose an alias (letters, digits, _): ")
        if proto.ALIAS_PATTERN.match(alias):
            return alias
        if alias == "quit":
            sys.exit(0)
        show("Alias must be 1-20 letters, digits or underscores.")


def wait_for_input_needed(state):
    """Block until the user must type something; return what is needed."""
    with state.lock:
        while True:
            if state.phase == "DONE":
                return "done", None
            if state.need_alias:
                state.need_alias = False
                return "alias", None
            if state.phase == "GAME_OVER":
                return "rematch", None
            if (state.phase == "PLAYING"
                    and state.active_player == state.my_number):
                return "guess", state.turn_id
            state.changed.wait()


def play(sock, state, alias):
    """Main-thread loop: prompt only when the game needs our input."""
    send(sock, proto.CONNECT, {"alias": alias})

    while True:
        need, turn_id = wait_for_input_needed(state)

        if need == "done":
            return

        if need == "alias":
            send(sock, proto.CONNECT, {"alias": ask_alias()})
            continue

        if need == "guess":
            guess = read_line("Your guess: ")
            if guess.lower() == "quit":
                send(sock, proto.DISCONNECT, {"reason": "quit"})
                show("You left the game.")
                return
            with state.lock:
                # Turn may have ended (timeout) while we were typing.
                if state.turn_id != turn_id or state.phase != "PLAYING":
                    show("Too late, that turn has ended.")
                    continue
                # Mark as pending so we do not prompt again until the
                # server replies with STATE_UPDATE / ERROR / GAME_OVER.
                state.active_player = None
            send(sock, proto.MOVE, {"guess": guess, "turn_id": turn_id})
            wait_for_reply(state, turn_id)
            continue

        if need == "rematch":
            answer = read_line("\nPlay again? (y/n): ").lower()
            with state.lock:
                if state.phase != "GAME_OVER":
                    continue     # opponent left; we are back in the lobby
                state.phase = "REMATCH_SENT"
            if answer.startswith("y"):
                send(sock, proto.REMATCH, {"play_again": True})
                show("Waiting for the other player to decide...")
            else:
                send(sock, proto.REMATCH, {"play_again": False})
                show("Thanks for playing!")
                return


def wait_for_reply(state, turn_id):
    """After sending MOVE, wait for the server to answer it."""
    with state.lock:
        while (state.phase == "PLAYING" and state.turn_id == turn_id
               and state.active_player is None):
            # An ERROR reply leaves turn_id unchanged; restore our turn.
            if not state.changed.wait(timeout=0.2):
                continue
            if state.phase == "PLAYING" and state.turn_id == turn_id:
                state.active_player = state.my_number
                return


# ----------------------------------------------------------------------
# Startup: arguments, DNS, TCP connect
# ----------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="client.py",
        description="Code-Breaker (Mastermind) console client.",
        epilog="examples:\n"
               "  python3 client.py -i server.bowman.edu -p 8080\n"
               "  python3 client.py -i localhost -p 8080 -a Alice",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-i", "--ip", dest="hostname", required=True,
                        metavar="HOSTNAME",
                        help="server DNS hostname (or IP), resolved via DNS")
    parser.add_argument("-p", "--port", required=True, type=proto.port_type,
                        metavar="PORT", help="server port (1024-65535)")
    parser.add_argument("-a", "--alias", metavar="ALIAS",
                        help="player alias (prompted for if omitted)")
    return parser.parse_args(argv)


def resolve_server(hostname):
    """Resolve the server hostname through DNS, failing gracefully."""
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        print(f"[ERROR] Unable to resolve DNS hostname '{hostname}'.")
        print("Please check your Cisco router DNS configuration "
              "('ip dns server' / 'ip host') or verify domain spelling.")
        sys.exit(1)


def connect(server_ip, port):
    """Open the TCP connection, exiting cleanly if the server is down."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(CONNECT_TIMEOUT)
    try:
        sock.connect((server_ip, port))
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        print(f"[ERROR] Could not connect to {server_ip}:{port} ({exc}).")
        print("Is the server running and reachable?")
        sock.close()
        sys.exit(1)
    sock.settimeout(None)       # blocking mode for the receiver thread
    return sock


def main(argv=None):
    args = parse_args(argv)
    if args.alias and not proto.ALIAS_PATTERN.match(args.alias):
        print("[ERROR] Alias must be 1-20 letters, digits or underscores.")
        sys.exit(1)

    server_ip = resolve_server(args.hostname)
    show(f"Resolved {args.hostname} -> {server_ip}")
    alias = args.alias or ask_alias()
    sock = connect(server_ip, args.port)
    show(f"Connected to {server_ip}:{args.port} as {alias}")

    state = ClientState()
    thread = threading.Thread(target=receiver, args=(sock, state),
                              daemon=True)
    thread.start()
    try:
        play(sock, state, alias)
    except OSError:
        show("Lost connection to the server.")
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        thread.join(timeout=1)


if __name__ == "__main__":
    main()
