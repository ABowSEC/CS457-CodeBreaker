"""Wire protocol for the Code-Breaker game (Sprint 1 blueprint).

This module only deals with *framing* and *schema* validation.  Game rules
(whose turn it is, whether a guess has unique digits, ...) live in game.py and
server.py so that transport concerns stay separate from game concerns.

Framing (docs/protocol_blueprint.md, "Option B"):
    +----------------------+-------------------------------+
    | 4-byte big-endian    | UTF-8 encoded JSON object     |
    | unsigned length (N)  | of exactly N bytes            |
    +----------------------+-------------------------------+

    1 <= N <= 16,384.  No newline terminator is used.
"""

import argparse
import json
import re
import struct

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

HEADER_SIZE = 4                    # bytes in the length prefix
HEADER_FORMAT = "!I"               # network order (big-endian) unsigned int
MIN_PAYLOAD = 1
MAX_PAYLOAD = 16_384

MIN_PORT = 1024
MAX_PORT = 65535

# Message names.
CONNECT = "CONNECT"
LOBBY_WAIT = "LOBBY_WAIT"
GAME_START = "GAME_START"
MOVE = "MOVE"
STATE_UPDATE = "STATE_UPDATE"
ERROR = "ERROR"
DISCONNECT = "DISCONNECT"
GAME_OVER = "GAME_OVER"
REMATCH = "REMATCH"

CLIENT_MESSAGES = frozenset({CONNECT, MOVE, DISCONNECT, REMATCH})
SERVER_MESSAGES = frozenset({LOBBY_WAIT, GAME_START, STATE_UPDATE, ERROR,
                             GAME_OVER})
ALL_MESSAGES = CLIENT_MESSAGES | SERVER_MESSAGES

# Error codes (blueprint ERROR table).
E_MALFORMED = "MALFORMED_MESSAGE"
E_UNKNOWN = "UNKNOWN_MESSAGE"
E_INVALID_STATE = "INVALID_STATE"
E_INVALID_ALIAS = "INVALID_ALIAS"
E_ALREADY_CONNECTED = "ALREADY_CONNECTED"
E_ROOM_FULL = "ROOM_FULL"
E_OUT_OF_TURN = "OUT_OF_TURN"
E_INVALID_GUESS = "INVALID_GUESS"
E_STALE_TURN = "STALE_TURN"

ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,20}$")


class FrameError(Exception):
    """The length header is outside the allowed range.

    The stream can no longer be trusted, so the caller must close the
    connection and run departure handling.
    """


class ProtocolError(Exception):
    """A complete frame arrived but its content breaks the schema.

    ``code`` is one of the blueprint error codes so the server can reply
    with a matching ERROR message.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------
# Serialization / framing
# --------------------------------------------------------------------------

def encode_message(msg_type, payload):
    """Serialize a message to bytes ready for ``sendall``.

    The length is measured *after* UTF-8 encoding so multi-byte characters
    are counted correctly.
    """
    body = json.dumps({"msg_type": msg_type, "payload": payload},
                      separators=(",", ":")).encode("utf-8")
    if not MIN_PAYLOAD <= len(body) <= MAX_PAYLOAD:
        raise ValueError(f"payload size {len(body)} outside protocol limits")
    return struct.pack(HEADER_FORMAT, len(body)) + body


class FrameBuffer:
    """Per-connection receive buffer that reassembles length-prefixed frames.

    TCP is a byte stream: one recv() may hold half a header, part of a
    payload, or several whole messages.  Bytes are accumulated here and only
    complete frames are released; leftovers wait for the next recv().
    """

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data):
        """Append newly received bytes."""
        self._buf.extend(data)

    def frames(self):
        """Yield every complete payload currently buffered (as bytes).

        Raises FrameError on an out-of-range length header.
        """
        while True:
            # Step 1: need the full 4-byte header first.
            if len(self._buf) < HEADER_SIZE:
                return
            (length,) = struct.unpack_from(HEADER_FORMAT, self._buf, 0)
            # Step 2: validate the length before waiting for the payload.
            if not MIN_PAYLOAD <= length <= MAX_PAYLOAD:
                raise FrameError(f"invalid payload length {length}")
            # Step 3: wait until the entire payload has arrived.
            end = HEADER_SIZE + length
            if len(self._buf) < end:
                return
            # Step 4: extract this frame and keep any following bytes.
            payload = bytes(self._buf[HEADER_SIZE:end])
            del self._buf[:end]
            yield payload

    def has_partial(self):
        """True if an incomplete frame is waiting for more bytes."""
        return len(self._buf) > 0

    def clear(self):
        """Discard any incomplete frame (used on EOF / disconnect)."""
        self._buf.clear()


def decode_payload(raw):
    """Turn one frame's payload bytes into a dict (no schema checks yet)."""
    try:
        msg = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProtocolError(E_MALFORMED, "Payload is not valid UTF-8 JSON.")
    if not isinstance(msg, dict):
        raise ProtocolError(E_MALFORMED, "Message must be a JSON object.")
    return msg


# --------------------------------------------------------------------------
# Schema validation
# --------------------------------------------------------------------------

def _is_int(value):
    # bool is a subclass of int in Python; the protocol treats them apart.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_int_or_none(value):
    return value is None or _is_int(value)


def _is_str_or_none(value):
    return value is None or isinstance(value, str)


def _is_player_counters(value):
    """Validate the two-element player-counter array used by updates."""
    if not isinstance(value, list) or len(value) != 2:
        return False
    numbers = set()
    for item in value:
        if not isinstance(item, dict):
            return False
        if not all(_is_int(item.get(k)) for k in
                   ("player_number", "attempt_count", "miss_turn")):
            return False
        numbers.add(item["player_number"])
    return numbers == {1, 2}


def _is_player_list(value):
    """GAME_START players: [{player_number, alias}, ...] x2."""
    if not isinstance(value, list) or len(value) != 2:
        return False
    return all(isinstance(p, dict) and _is_int(p.get("player_number"))
               and isinstance(p.get("alias"), str) for p in value)


def _is_leaderboard(value):
    if not isinstance(value, list):
        return False
    return all(isinstance(e, dict) and _is_int(e.get("player_number"))
               and isinstance(e.get("alias"), str)
               and _is_int(e.get("rounds_won"))
               and _is_int(e.get("total_guesses")) for e in value)


# For each message: {field_name: predicate}.  Every listed field is required.
SCHEMAS = {
    CONNECT: {"alias": lambda v: isinstance(v, str)},
    LOBBY_WAIT: {"player_number": _is_int,
                 "alias": lambda v: isinstance(v, str),
                 "message": lambda v: isinstance(v, str)},
    GAME_START: {"player_number": _is_int,
                 "players": _is_player_list,
                 "active_player": _is_int,
                 "code_length": _is_int,
                 "attempt_limit": _is_int,
                 "turn_seconds": _is_int,
                 "turn_id": _is_int},
    MOVE: {"guess": lambda v: isinstance(v, str),
           "turn_id": _is_int},
    STATE_UPDATE: {"event": lambda v: v in ("GUESS_RESULT", "TURN_SKIPPED"),
                   "previous_player": _is_int,
                   "guess": _is_str_or_none,
                   "correct_position": _is_int_or_none,
                   "wrong_position": _is_int_or_none,
                   "players": _is_player_counters,
                   "active_player": _is_int,
                   "turn_id": _is_int,
                   "turn_seconds": _is_int},
    ERROR: {"code": lambda v: isinstance(v, str),
            "message": lambda v: isinstance(v, str),
            "turn_id": _is_int_or_none},
    DISCONNECT: {"reason": lambda v: v == "quit"},
    GAME_OVER: {"outcome": lambda v: v in ("WIN", "DRAW", "FORFEIT"),
                "winner": _is_int_or_none,
                "reason": lambda v: v in ("CODE_SOLVED", "ATTEMPTS_EXHAUSTED",
                                          "PLAYER_QUIT", "CONNECTION_LOST",
                                          "TURN_TIMEOUT"),
                "secret_code": lambda v: isinstance(v, str),
                "final_guess": _is_str_or_none,
                "players": _is_player_counters,
                "message": lambda v: isinstance(v, str),
                "leaderboard": _is_leaderboard},
    REMATCH: {"play_again": lambda v: isinstance(v, bool)},
}


def validate_message(msg, allowed):
    """Check a decoded message against the blueprint schema.

    ``allowed`` is the set of message names this side may receive
    (CLIENT_MESSAGES on the server, SERVER_MESSAGES on the client).
    Returns ``(msg_type, payload)`` or raises ProtocolError.
    """
    msg_type = msg.get("msg_type")
    if not isinstance(msg_type, str):
        raise ProtocolError(E_MALFORMED, "Missing or non-string msg_type.")
    if msg_type not in ALL_MESSAGES or msg_type not in allowed:
        raise ProtocolError(E_UNKNOWN, f"Unknown message type '{msg_type}'.")

    payload = msg.get("payload")
    if not isinstance(payload, dict):
        raise ProtocolError(E_MALFORMED, "Missing or non-object payload.")

    for field, check in SCHEMAS[msg_type].items():
        if field not in payload:
            raise ProtocolError(E_MALFORMED,
                                f"{msg_type} is missing field '{field}'.")
        if not check(payload[field]):
            raise ProtocolError(E_MALFORMED,
                                f"{msg_type} field '{field}' is invalid.")
    return msg_type, payload


# --------------------------------------------------------------------------
# Shared CLI helper
# --------------------------------------------------------------------------

def port_type(text):
    """argparse type: an integer port in the range 1024-65535."""
    try:
        port = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number")
    if not MIN_PORT <= port <= MAX_PORT:
        raise argparse.ArgumentTypeError(
            f"{port} is out of range (must be {MIN_PORT}-{MAX_PORT})")
    return port
