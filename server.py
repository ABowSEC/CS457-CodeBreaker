"""Code-Breaker game server.

Usage:
    python3 server.py -h
    python3 server.py -p 8080

Architecture (docs/concurrency_design.md):
    A single thread runs a ``selectors`` event loop over the listening socket
    and every client socket (all non-blocking).  Because only one thread ever
    touches game state, no locks are needed.  Outgoing data is queued in a
    per-client buffer and written when the socket is writable.

Game flow (docs/fsm_specifications.md):
    INIT -> WAITING_FOR_PLAYERS -> GAME_START -> PLAYER_TURN <-> EVALUATE_MOVE
         -> GAME_OVER -> REMATCH_WAIT -> (GAME_START | CLEANUP)
    CLEANUP -> WAITING_FOR_PLAYERS
"""

import argparse
import enum
import json
import logging
import selectors
import socket
import sys
import time

import game
import protocol as proto

BIND_ADDRESS = "0.0.0.0"   # listen on every interface (assignment spec)
RECV_SIZE = 4096
BACKLOG = 5

log = logging.getLogger("server")


class State(enum.Enum):
    """FSM states from docs/fsm_specifications.md."""
    INIT = "INIT"
    WAITING_FOR_PLAYERS = "WAITING_FOR_PLAYERS"
    GAME_START = "GAME_START"
    PLAYER_TURN = "PLAYER_TURN"
    EVALUATE_MOVE = "EVALUATE_MOVE"
    GAME_OVER = "GAME_OVER"
    REMATCH_WAIT = "REMATCH_WAIT"
    CLEANUP = "CLEANUP"


class ClientConn:
    """Everything the server tracks for one TCP connection."""

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.inbox = proto.FrameBuffer()     # partial incoming frames
        self.outbox = bytearray()            # bytes waiting to be sent
        self.player = None                   # game.Player once registered
        self.departed = False                # departure handled once only
        self.close_after_flush = False       # e.g. after ROOM_FULL

    @property
    def number(self):
        return self.player.player_number if self.player else None

    def label(self):
        """Readable name for log lines."""
        if self.player:
            return f"P{self.player.player_number}:{self.player.alias}"
        return f"{self.addr[0]}:{self.addr[1]}"


class GameServer:
    """Owns the listening socket, the selector, and the game FSM."""

    def __init__(self, port, turn_seconds=game.TURN_SECONDS):
        self.port = port
        self.turn_seconds = turn_seconds
        self.sel = selectors.DefaultSelector()
        self.listener = None
        self.state = State.INIT
        self.players = {}           # {player_number: ClientConn}
        self.round = None           # game.Round while a game is running
        self.deadline = None        # time.monotonic() turn deadline
        self.rematch_votes = set()  # player numbers that said yes

    # ------------------------------------------------------------------
    # Setup and main loop
    # ------------------------------------------------------------------

    def start(self):
        """INIT: create the TCP listening socket bound to 0.0.0.0."""
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((BIND_ADDRESS, self.port))
        self.listener.listen(BACKLOG)
        self.listener.setblocking(False)
        self.sel.register(self.listener, selectors.EVENT_READ, data=None)
        log.info("Listening on %s:%d (turn limit %ds)",
                 BIND_ADDRESS, self.port, self.turn_seconds)
        self.set_state(State.WAITING_FOR_PLAYERS)

    def serve_forever(self):
        """Run the event loop until interrupted."""
        while True:
            # Wake up for socket activity OR the turn deadline, whichever
            # comes first.  No deadline (lobby) means block indefinitely.
            timeout = None
            if self.deadline is not None:
                timeout = max(0.0, self.deadline - time.monotonic())

            events = self.sel.select(timeout=timeout)

            # Check the deadline before handling any MOVE, so a guess that
            # arrives late is not accepted.
            self.check_turn_deadline()

            for key, mask in events:
                if key.data is None:
                    self.accept()
                    continue
                conn = key.data
                if mask & selectors.EVENT_READ and not conn.departed:
                    self.read_from(conn)
                if mask & selectors.EVENT_WRITE and not conn.departed:
                    self.write_to(conn)

            # Handling events may have run past the deadline as well.
            self.check_turn_deadline()

    def shutdown(self):
        """Close every socket (used on Ctrl+C)."""
        for conn in list(self.players.values()):
            self.close_conn(conn)
        for key in list(self.sel.get_map().values()):
            if key.data is not None:
                self.close_conn(key.data)
        if self.listener:
            self.sel.unregister(self.listener)
            self.listener.close()
        self.sel.close()

    def set_state(self, new_state):
        if new_state != self.state:
            log.info("FSM %s -> %s", self.state.value, new_state.value)
        self.state = new_state

    # ------------------------------------------------------------------
    # Socket I/O
    # ------------------------------------------------------------------

    def accept(self):
        """Listening socket is readable: accept a new client."""
        try:
            sock, addr = self.listener.accept()
        except BlockingIOError:
            return
        sock.setblocking(False)
        conn = ClientConn(sock, addr)
        self.sel.register(sock, selectors.EVENT_READ, data=conn)
        log.info("Accepted connection from %s:%d", addr[0], addr[1])

        # A third client while both seats are taken is turned away.
        if len(self.players) >= 2:
            self.send_error(conn, proto.E_ROOM_FULL,
                            "Two players are already in the game.")
            conn.close_after_flush = True

    def read_from(self, conn):
        """Client socket readable: buffer bytes and process whole frames."""
        try:
            data = conn.sock.recv(RECV_SIZE)
        except BlockingIOError:
            return                      # nothing to read after all
        except (ConnectionResetError, ConnectionAbortedError, OSError) as exc:
            log.info("%s socket error: %s", conn.label(), exc)
            self.handle_departure(conn, "CONNECTION_LOST")
            return

        if not data:                    # b"" -> peer closed (TCP FIN)
            log.info("%s closed the connection (EOF)", conn.label())
            conn.inbox.clear()          # discard any incomplete frame
            self.handle_departure(conn, "CONNECTION_LOST")
            return

        conn.inbox.feed(data)
        try:
            for raw in conn.inbox.frames():
                self.handle_frame(conn, raw)
                if conn.departed:
                    return
        except proto.FrameError as exc:
            log.warning("%s sent a bad frame (%s); closing",
                        conn.label(), exc)
            self.handle_departure(conn, "CONNECTION_LOST")

    def write_to(self, conn):
        """Client socket writable: send as much queued data as possible."""
        try:
            sent = conn.sock.send(conn.outbox)
        except BlockingIOError:
            return
        except (BrokenPipeError, ConnectionResetError,
                ConnectionAbortedError, OSError) as exc:
            log.info("%s send failed: %s", conn.label(), exc)
            self.handle_departure(conn, "CONNECTION_LOST")
            return
        del conn.outbox[:sent]
        if not conn.outbox:
            if conn.close_after_flush:
                self.close_conn(conn)
            else:
                self.update_interest(conn)

    def update_interest(self, conn):
        """Watch for writability only while there is data to send."""
        if conn.departed:
            return
        events = selectors.EVENT_READ
        if conn.outbox:
            events |= selectors.EVENT_WRITE
        self.sel.modify(conn.sock, events, data=conn)

    def send(self, conn, msg_type, payload):
        """Queue a framed message for one client."""
        if conn is None or conn.departed:
            return
        conn.outbox.extend(proto.encode_message(msg_type, payload))
        self.update_interest(conn)
        log.info("SEND -> %s %s %s", conn.label(), msg_type,
                 json.dumps(payload, separators=(",", ":")))

    def broadcast(self, msg_type, payload):
        """Queue the same message (same server state) for every player."""
        for number in sorted(self.players):
            self.send(self.players[number], msg_type, payload)

    def send_error(self, conn, code, message):
        turn_id = None
        if self.state == State.PLAYER_TURN and self.round:
            turn_id = self.round.turn_id
        self.send(conn, proto.ERROR,
                  {"code": code, "message": message, "turn_id": turn_id})

    def close_conn(self, conn):
        """Unregister then close a socket (safe to call twice)."""
        conn.departed = True
        try:
            self.sel.unregister(conn.sock)
        except (KeyError, ValueError):
            pass
        try:
            conn.sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    def handle_frame(self, conn, raw):
        """Decode + schema-validate one frame, then hand it to the FSM."""
        try:
            msg = proto.decode_payload(raw)
            msg_type, payload = proto.validate_message(
                msg, proto.CLIENT_MESSAGES)
        except proto.ProtocolError as exc:
            log.info("RECV <- %s rejected: %s", conn.label(), exc.message)
            self.send_error(conn, exc.code, exc.message)
            return

        log.info("RECV <- %s %s %s", conn.label(), msg_type,
                 json.dumps(payload, separators=(",", ":")))
        handler = {
            proto.CONNECT: self.on_connect,
            proto.MOVE: self.on_move,
            proto.DISCONNECT: self.on_disconnect,
            proto.REMATCH: self.on_rematch,
        }[msg_type]
        handler(conn, payload)

    def on_connect(self, conn, payload):
        """WAITING_FOR_PLAYERS: register a player by alias."""
        if conn.player is not None:
            self.send_error(conn, proto.E_ALREADY_CONNECTED,
                            "You are already registered.")
            return
        if self.state != State.WAITING_FOR_PLAYERS or len(self.players) >= 2:
            self.send_error(conn, proto.E_ROOM_FULL,
                            "Two players are already in the game.")
            conn.close_after_flush = True
            return

        alias = payload["alias"]
        taken = {c.player.alias.lower() for c in self.players.values()}
        if not proto.ALIAS_PATTERN.match(alias):
            self.send_error(conn, proto.E_INVALID_ALIAS,
                            "Alias must be 1-20 letters, digits or _.")
            return
        if alias.lower() in taken:
            self.send_error(conn, proto.E_INVALID_ALIAS,
                            f"Alias '{alias}' is already in use.")
            return

        number = 1 if 1 not in self.players else 2
        conn.player = game.Player(alias, number)
        self.players[number] = conn
        log.info("Registered %s", conn.label())

        if len(self.players) == 1:
            self.send_lobby_wait(conn)
        else:
            self.start_game()

    def on_move(self, conn, payload):
        """PLAYER_TURN -> EVALUATE_MOVE -> (PLAYER_TURN | GAME_OVER)."""
        if conn.player is None or self.state != State.PLAYER_TURN:
            self.send_error(conn, proto.E_INVALID_STATE,
                            "No game turn is active right now.")
            return

        # Validation failures leave attempts, turn and deadline untouched.
        rnd = self.round
        if conn.number != rnd.active_player:
            other = self.players[rnd.active_player].player.alias
            self.send_error(conn, proto.E_OUT_OF_TURN,
                            f"It is Player {rnd.active_player}'s "
                            f"({other}) turn.")
            return
        if payload["turn_id"] != rnd.turn_id:
            self.send_error(conn, proto.E_STALE_TURN,
                            f"turn_id {payload['turn_id']} is not the "
                            f"current turn ({rnd.turn_id}).")
            return
        guess = payload["guess"]
        if not game.is_valid_guess(guess):
            self.send_error(conn, proto.E_INVALID_GUESS,
                            "Guess must be 4 unique digits (0-9).")
            return

        self.set_state(State.EVALUATE_MOVE)
        player_number = rnd.active_player
        correct, wrong = rnd.apply_guess(guess)

        if correct == game.CODE_LENGTH:
            alias = conn.player.alias
            self.game_over("WIN", player_number, "CODE_SOLVED",
                           f"{alias} cracked the code {rnd.secret}!")
            return
        if rnd.both_exhausted():
            self.game_over("DRAW", None, "ATTEMPTS_EXHAUSTED",
                           game.DRAW_MESSAGE)
            return

        rnd.advance_turn(rnd.next_eligible_player())
        self.broadcast_state_update("GUESS_RESULT", player_number,
                                    guess, correct, wrong)
        self.begin_turn()

    def on_disconnect(self, conn, payload):
        """Intentional quit (payload reason is always 'quit')."""
        self.handle_departure(conn, "PLAYER_QUIT")

    def on_rematch(self, conn, payload):
        """REMATCH_WAIT: collect play-again votes."""
        if conn.player is None or self.state != State.REMATCH_WAIT:
            self.send_error(conn, proto.E_INVALID_STATE,
                            "There is no finished game to rematch.")
            return
        if not payload["play_again"]:
            log.info("%s declined the rematch", conn.label())
            self.handle_departure(conn, "PLAYER_QUIT")
            return
        self.rematch_votes.add(conn.number)
        log.info("%s wants a rematch (%d/2)", conn.label(),
                 len(self.rematch_votes))
        if self.rematch_votes == {1, 2}:
            self.start_game()

    # ------------------------------------------------------------------
    # FSM actions
    # ------------------------------------------------------------------

    def send_lobby_wait(self, conn):
        self.send(conn, proto.LOBBY_WAIT,
                  {"player_number": conn.number,
                   "alias": conn.player.alias,
                   "message": "Waiting for Player 2."})

    def start_game(self):
        """GAME_START: new secret, reset round counters, Player 1 first."""
        self.set_state(State.GAME_START)
        self.rematch_votes.clear()
        players = {n: c.player for n, c in self.players.items()}
        self.round = game.Round(players, self.turn_seconds)
        log.info("New round, secret code is %s", self.round.secret)

        roster = [{"player_number": n, "alias": players[n].alias}
                  for n in (1, 2)]
        for number, conn in sorted(self.players.items()):
            self.send(conn, proto.GAME_START,
                      {"player_number": number,
                       "players": roster,
                       "active_player": self.round.active_player,
                       "code_length": game.CODE_LENGTH,
                       "attempt_limit": game.ATTEMPT_LIMIT,
                       "turn_seconds": self.turn_seconds,
                       "turn_id": self.round.turn_id})
        self.begin_turn()

    def begin_turn(self):
        """Enter PLAYER_TURN and start a fresh turn timer."""
        self.set_state(State.PLAYER_TURN)
        self.deadline = time.monotonic() + self.turn_seconds
        log.info("Turn %d: Player %d to move (%ds)", self.round.turn_id,
                 self.round.active_player, self.turn_seconds)

    def broadcast_state_update(self, event, previous_player, guess,
                               correct, wrong):
        self.broadcast(proto.STATE_UPDATE,
                       {"event": event,
                        "previous_player": previous_player,
                        "guess": guess,
                        "correct_position": correct,
                        "wrong_position": wrong,
                        "players": self.round.counters(),
                        "active_player": self.round.active_player,
                        "turn_id": self.round.turn_id,
                        "turn_seconds": self.turn_seconds})

    def check_turn_deadline(self):
        """Apply the timeout rules if the active player ran out of time."""
        if self.state != State.PLAYER_TURN or self.deadline is None:
            return
        if time.monotonic() < self.deadline:
            return

        rnd = self.round
        timed_out = rnd.active_player
        alias = rnd.players[timed_out].alias
        log.info("Player %d (%s) timed out on turn %d",
                 timed_out, alias, rnd.turn_id)

        if rnd.apply_timeout():      # second timeout -> forfeit
            winner = rnd.opponent_of(timed_out)
            self.game_over("FORFEIT", winner, "TURN_TIMEOUT",
                           f"{alias} timed out twice and forfeits.")
            return
        if rnd.both_exhausted():
            self.game_over("DRAW", None, "ATTEMPTS_EXHAUSTED",
                           game.DRAW_MESSAGE)
            return

        rnd.advance_turn(rnd.next_eligible_player())
        self.broadcast_state_update("TURN_SKIPPED", timed_out,
                                    None, None, None)
        self.begin_turn()

    def game_over(self, outcome, winner, reason, message):
        """GAME_OVER: record the result once and tell connected players."""
        self.set_state(State.GAME_OVER)
        self.deadline = None
        rnd = self.round
        if winner is not None:
            rnd.players[winner].rounds_won += 1

        self.broadcast(proto.GAME_OVER,
                       {"outcome": outcome,
                        "winner": winner,
                        "reason": reason,
                        "secret_code": rnd.secret,
                        "final_guess": rnd.final_guess,
                        "players": rnd.counters(),
                        "message": message,
                        "leaderboard": game.leaderboard(
                            rnd.players.values())})

        if len(self.players) == 2:
            self.rematch_votes.clear()
            self.set_state(State.REMATCH_WAIT)
        else:
            self.cleanup()

    def handle_departure(self, conn, reason):
        """DISCONNECT, EOF or socket error (handled exactly once)."""
        if conn.departed:
            return
        self.close_conn(conn)
        if conn.player is None:
            return                       # never registered; nothing else
        number = conn.number
        log.info("%s departed (%s) during %s", conn.label(), reason,
                 self.state.value)
        self.players.pop(number, None)

        if self.state == State.WAITING_FOR_PLAYERS:
            return                       # slot is simply freed
        if self.state == State.PLAYER_TURN:
            if self.players:             # opponent still here -> forfeit
                winner = self.round.opponent_of(number)
                why = "quit" if reason == "PLAYER_QUIT" else \
                    "lost connection"
                self.game_over("FORFEIT", winner, reason,
                               f"{conn.player.alias} {why}; "
                               f"{self.round.players[winner].alias} wins "
                               f"by forfeit.")
            else:                        # nobody left -> no winner
                self.cleanup()
            return
        # REMATCH_WAIT (or any other post-game state)
        self.cleanup()

    def cleanup(self):
        """CLEANUP: reset round data, keep the remaining player as P1."""
        self.set_state(State.CLEANUP)
        self.round = None
        self.deadline = None
        self.rematch_votes.clear()

        remaining = list(self.players.values())
        self.players = {}
        for conn in remaining:
            conn.player.player_number = 1      # survivor becomes Player 1
            conn.player.reset_round()
            self.players[1] = conn

        self.set_state(State.WAITING_FOR_PLAYERS)
        for conn in self.players.values():
            self.send_lobby_wait(conn)


# ----------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="server.py",
        description="Code-Breaker (Mastermind) game server. Listens on "
                    "0.0.0.0 for two players over TCP.",
        epilog="example: python3 server.py -p 8080")
    parser.add_argument("-p", "--port", required=True, type=proto.port_type,
                        metavar="PORT",
                        help="listening port (1024-65535)")
    parser.add_argument("-t", "--turn-seconds", type=int,
                        default=game.TURN_SECONDS, metavar="SECONDS",
                        help="seconds allowed per turn "
                             f"(default {game.TURN_SECONDS})")
    args = parser.parse_args(argv)
    if args.turn_seconds < 1:
        parser.error("--turn-seconds must be at least 1")
    return args


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [SERVER] %(message)s",
                        datefmt="%H:%M:%S")
    server = GameServer(args.port, args.turn_seconds)
    try:
        server.start()
    except OSError as exc:
        print(f"[ERROR] Cannot listen on port {args.port}: {exc}",
              file=sys.stderr)
        sys.exit(1)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down (Ctrl+C)")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
