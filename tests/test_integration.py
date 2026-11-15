"""End-to-end tests: real server.py process + raw TCP test clients.

Each test starts the server on a free localhost port with a short turn
limit, then drives two clients through the wire protocol.
"""

import os
import re
import socket
import subprocess
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import protocol as proto  # noqa: E402

TURN_SECONDS = 2


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestClient:
    """Minimal blocking client used to script the protocol."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.inbox = proto.FrameBuffer()
        self.pending = []

    def send(self, msg_type, payload):
        self.sock.sendall(proto.encode_message(msg_type, payload))

    def recv(self, expected=None):
        while not self.pending:
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionError("server closed connection")
            self.inbox.feed(data)
            for raw in self.inbox.frames():
                self.pending.append(proto.validate_message(
                    proto.decode_payload(raw), proto.SERVER_MESSAGES))
        msg_type, payload = self.pending.pop(0)
        if expected:
            assert msg_type == expected, (msg_type, payload)
        return payload

    def close(self):
        self.sock.close()


class ServerTestCase(unittest.TestCase):

    def setUp(self):
        self.port = free_port()
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "server.py"),
             "-p", str(self.port), "-t", str(TURN_SECONDS)],
            stderr=subprocess.PIPE, text=True)
        self.log = []
        threading.Thread(target=self._read_log, daemon=True).start()
        self._wait_for("Listening on")
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.proc.kill()
        self.proc.wait()
        self.proc.stderr.close()

    def _read_log(self):
        for line in self.proc.stderr:
            self.log.append(line)

    def _wait_for(self, text, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if any(text in line for line in self.log):
                return
            time.sleep(0.05)
        self.fail(f"server never logged {text!r}")

    def secret(self):
        """Most recent secret code from the server log."""
        self._wait_for("secret code is")
        found = [re.search(r"secret code is (\d{4})", ln) for ln in self.log]
        return [m.group(1) for m in found if m][-1]

    def client(self):
        c = TestClient(self.port)
        self.clients.append(c)
        return c

    def start_two(self):
        a, b = self.client(), self.client()
        a.send(proto.CONNECT, {"alias": "Alice"})
        self.assertEqual(a.recv(proto.LOBBY_WAIT)["player_number"], 1)
        b.send(proto.CONNECT, {"alias": "Bob"})
        self.assertEqual(a.recv(proto.GAME_START)["player_number"], 1)
        self.assertEqual(b.recv(proto.GAME_START)["player_number"], 2)
        return a, b


class GameFlowTests(ServerTestCase):

    def wrong_guess(self, secret):
        """A valid guess that is guaranteed not to be the secret."""
        return secret[1:] + secret[0]

    def test_multi_turn_game_to_win(self):
        a, b = self.start_two()
        secret = self.secret()
        miss = self.wrong_guess(secret)

        a.send(proto.MOVE, {"guess": miss, "turn_id": 1})
        upd_a, upd_b = a.recv(proto.STATE_UPDATE), b.recv(proto.STATE_UPDATE)
        self.assertEqual(upd_a, upd_b)                  # same broadcast
        self.assertEqual((upd_a["active_player"], upd_a["turn_id"]), (2, 2))
        self.assertEqual(upd_a["correct_position"], 0)
        self.assertEqual(upd_a["wrong_position"], 4)

        b.send(proto.MOVE, {"guess": miss, "turn_id": 2})
        a.recv(proto.STATE_UPDATE)
        b.recv(proto.STATE_UPDATE)

        a.send(proto.MOVE, {"guess": secret, "turn_id": 3})
        over = a.recv(proto.GAME_OVER)
        self.assertEqual(b.recv(proto.GAME_OVER), over)
        self.assertEqual((over["outcome"], over["winner"], over["reason"]),
                         ("WIN", 1, "CODE_SOLVED"))
        self.assertEqual(over["leaderboard"][0]["alias"], "Alice")
        self.assertEqual(over["leaderboard"][0]["rounds_won"], 1)

    def test_invalid_moves_do_not_change_turn(self):
        a, b = self.start_two()
        b.send(proto.MOVE, {"guess": "0123", "turn_id": 1})
        self.assertEqual(b.recv(proto.ERROR)["code"], proto.E_OUT_OF_TURN)
        a.send(proto.MOVE, {"guess": "0123", "turn_id": 9})
        self.assertEqual(a.recv(proto.ERROR)["code"], proto.E_STALE_TURN)
        a.send(proto.MOVE, {"guess": "1123", "turn_id": 1})
        self.assertEqual(a.recv(proto.ERROR)["code"], proto.E_INVALID_GUESS)
        a.send("BOGUS", {})
        self.assertEqual(a.recv(proto.ERROR)["code"], proto.E_UNKNOWN)
        a.send(proto.CONNECT, {"alias": "Again"})
        self.assertEqual(a.recv(proto.ERROR)["code"],
                         proto.E_ALREADY_CONNECTED)
        # Still Player 1, turn 1, zero attempts used.
        a.send(proto.MOVE, {"guess": self.wrong_guess(self.secret()),
                            "turn_id": 1})
        upd = a.recv(proto.STATE_UPDATE)
        self.assertEqual(upd["players"][0]["attempt_count"], 1)

    def test_fragmented_frames_reach_server(self):
        a, b = self.start_two()
        data = proto.encode_message(
            proto.MOVE, {"guess": self.wrong_guess(self.secret()),
                         "turn_id": 1})
        for i in range(0, len(data), 5):           # dribble 5 bytes at a time
            a.sock.sendall(data[i:i + 5])
            time.sleep(0.01)
        self.assertEqual(a.recv(proto.STATE_UPDATE)["turn_id"], 2)

    def test_third_client_room_full(self):
        self.start_two()
        c = self.client()
        self.assertEqual(c.recv(proto.ERROR)["code"], proto.E_ROOM_FULL)

    def test_alias_rules(self):
        a, b = self.client(), self.client()
        a.send(proto.CONNECT, {"alias": "bad alias!"})
        self.assertEqual(a.recv(proto.ERROR)["code"], proto.E_INVALID_ALIAS)
        a.send(proto.CONNECT, {"alias": "Alice"})
        a.recv(proto.LOBBY_WAIT)
        b.send(proto.CONNECT, {"alias": "Alice"})
        self.assertEqual(b.recv(proto.ERROR)["code"], proto.E_INVALID_ALIAS)

    def test_timeout_skip_then_forfeit(self):
        a, b = self.start_two()
        skip = a.recv(proto.STATE_UPDATE)            # P1 times out once
        b.recv(proto.STATE_UPDATE)
        self.assertEqual(skip["event"], "TURN_SKIPPED")
        self.assertEqual(skip["players"][0]["miss_turn"], 1)
        self.assertEqual(skip["players"][0]["attempt_count"], 1)
        b.send(proto.MOVE, {"guess": self.wrong_guess(self.secret()),
                            "turn_id": 2})
        a.recv(proto.STATE_UPDATE)
        b.recv(proto.STATE_UPDATE)
        over = a.recv(proto.GAME_OVER)               # P1 times out again
        self.assertEqual((over["outcome"], over["winner"], over["reason"]),
                         ("FORFEIT", 2, "TURN_TIMEOUT"))

    def test_disconnect_forfeit_and_lobby_return(self):
        a, b = self.start_two()
        b.send(proto.DISCONNECT, {"reason": "quit"})
        over = a.recv(proto.GAME_OVER)
        self.assertEqual((over["outcome"], over["winner"], over["reason"]),
                         ("FORFEIT", 1, "PLAYER_QUIT"))
        self.assertEqual(a.recv(proto.LOBBY_WAIT)["player_number"], 1)

    def test_eof_is_connection_lost(self):
        a, b = self.start_two()
        a.close()
        over = b.recv(proto.GAME_OVER)
        self.assertEqual((over["winner"], over["reason"]),
                         (2, "CONNECTION_LOST"))
        lobby = b.recv(proto.LOBBY_WAIT)
        self.assertEqual(lobby["player_number"], 1)  # survivor renumbered

    def test_rematch_keeps_session_totals(self):
        a, b = self.start_two()
        a.send(proto.MOVE, {"guess": self.secret(), "turn_id": 1})
        a.recv(proto.GAME_OVER)
        b.recv(proto.GAME_OVER)
        a.send(proto.MOVE, {"guess": "0123", "turn_id": 2})
        self.assertEqual(a.recv(proto.ERROR)["code"], proto.E_INVALID_STATE)
        a.send(proto.REMATCH, {"play_again": True})
        b.send(proto.REMATCH, {"play_again": True})
        start = a.recv(proto.GAME_START)
        b.recv(proto.GAME_START)
        self.assertEqual(start["turn_id"], 1)
        # Bob wins round two; leaderboard reflects both rounds.
        a.send(proto.MOVE, {"guess": self.wrong_guess(self.secret()),
                            "turn_id": 1})
        a.recv(proto.STATE_UPDATE)
        b.recv(proto.STATE_UPDATE)
        b.send(proto.MOVE, {"guess": self.secret(), "turn_id": 2})
        over = b.recv(proto.GAME_OVER)
        wins = {e["alias"]: e["rounds_won"] for e in over["leaderboard"]}
        self.assertEqual(wins, {"Alice": 1, "Bob": 1})

    def test_rematch_decline_returns_lobby(self):
        a, b = self.start_two()
        a.send(proto.MOVE, {"guess": self.secret(), "turn_id": 1})
        a.recv(proto.GAME_OVER)
        b.recv(proto.GAME_OVER)
        b.send(proto.REMATCH, {"play_again": False})
        self.assertEqual(a.recv(proto.LOBBY_WAIT)["alias"], "Alice")


if __name__ == "__main__":
    unittest.main()
