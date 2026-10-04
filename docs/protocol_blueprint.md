Complete field specifications, data types, and framing rules for all message types (including DISCONNECT / forfeit management).

Concrete Framing Rule & Wire Examples: Concrete examples of your chosen framing mechanism on the continuous wire stream (e.g., JSON schema with newline delimiters, binary length-prefix framing, or text-delimited grammar).

The protocol uses Option B: Length-Prefixed Framing. Each message begins with a 4-byte unsigned big-endian header containing the byte length of the UTF-8 JSON payload, excluding the header. No newline terminator is used.

msg_type, STRING, must be one of eight defined message names

payload, OBJ, Required for each message types seen below. All field listed in schema are required

Client will input an alias and server will finalize conenction by validating alias and assigning player #

| Message | Direction | Payload contents |
|---|---|---|
| `CONNECT` | Client $\rightarrow$  Server | Player alias |
| `LOBBY_WAIT` | Server $\rightarrow$  Client | Assigned player number and waiting notification |
| `GAME_START` | Server $\rightarrow$ Both clients | Recipient’s player number, active player, code length, attempt limit, turn duration |
| `MOVE` | Client $\rightarrow$  Server | Guess and turn id |
| `STATE_UPDATE` | Server $\rightarrow$  Both clients | Feedback, both players’ counters, active player, turn identifier |
| `ERROR` | Server $\rightarrow$  Client | Error code and explanation |
| `DISCONNECT` | Client $\rightarrow$  Server | Departure reason |
| `GAME_OVER` | Server $\rightarrow$  Both connected clients | Outcome, winner, reason, final counters, and display message |

**EXPECTED STRUCTURE of each:**

CONNECT:

Request to join game

| Payload field | Type | Rule |
|---|---|---|
| `alias` | string | 1–20 ASCII letters, numbers, or underscores; must be unique among connected players |

```json
{
    "msg_type": "CONNECT",
    "payload": {
        "alias": "Superman"
    }
}
```

**LOBBY_WAIT:**

Confirm registration and notify the first player that the server is waiting for an opponent.

| Payload field | Type | Rule |
|---|---|---|
| `player_number` | integer | `1` |
| `alias` | string | Accepted client alias |
| `message` | string | Waiting notification |

```json
{
    "msg_type": "LOBBY_WAIT",
    "payload": {
        "player_number": 1,
        "alias": "Superman",
        "message": "Waiting for Player 2."
    }
}
```

**GAME_START:**

Purpose: Announce the game rules, player assignments, and first turn setup.

| Payload field | Type | Rule |
|---|---|---|
| `player_number` | integer | Recipient’s assigned number: `1` or `2` |
| `players` | array of objects | Two objects, each containing `player_number` (integer) and `alias` (string) |
| `active_player` | integer | Initially `1` |
| `code_length` | integer | `4`; secret contains unique digits from `0`–`9` |
| `attempt_limit` | integer | `10` per player |
| `turn_seconds` | integer | `120` |
| `turn_id` | integer | Initially `1`; increases by 1 for each new turn |

```json
{
    "msg_type": "GAME_START",
    "payload": {
        "player_number": 1,
        "players": [
            {
                "player_number": 1,
                "alias": "Superman"
            },
            {
                "player_number": 2,
                "alias": "Bizarro"
            }
        ],
        "active_player": 1,
        "code_length": 4,
        "attempt_limit": 10,
        "turn_seconds": 120,
        "turn_id": 1
    }
}
```

**MOVE:**

Active player submits guess for current turn

| Payload field | Type | Rule |
|---|---|---|
| `guess` | string | Exactly four unique ASCII digits from `0`–`9`; leading zeros allowed |
| `turn_id` | integer | Positive integer matching the current turn |

```json
{
    "msg_type": "MOVE",
    "payload": {
        "guess": "0123",
        "turn_id": 1
    }
}
```

**STATE_UPDATE:**

Send guess feedback or skipped turn Notification, update counters, and then next turn

| Payload field | Type | Rule |
|---|---|---|
| `event` | string | `"GUESS_RESULT"` or `"TURN_SKIPPED"` |
| `previous_player` | integer | Player whose turn was processed |
| `guess` | string or null | Submitted guess; `null` for a skipped turn |
| `correct_position` | integer or null | Correct digits in correct positions, `0`–`4`; `null` for a skipped turn |
| `wrong_position` | integer or null | Correct digits in wrong positions, `0`–`4`; `null` for a skipped turn |
| `players` | array of objects | Two player-counter objects defined below |
| `active_player` | integer | Next player with attempts remaining |
| `turn_id` | integer | Previous turn ID plus 1 |
| `turn_seconds` | integer | `120` for the new turn |

**PLAYERs OBJECTS**

| Field | Type | Rule |
|---|---|---|
| `player_number` | integer | `1` or `2`, each appearing once |
| `attempt_count` | integer | `0`–`10`; includes first-timeout penalties |
| `miss_turn` | integer | `0`–`2`; number of turn timeouts |

```json
{
    "msg_type": "STATE_UPDATE",
    "payload": {
        "event": "GUESS_RESULT",
        "previous_player": 1,
        "guess": "0123",
        "correct_position": 1,
        "wrong_position": 2,
        "players": 
        [
            {
                "player_number": 1,
                "attempt_count": 1,
                "miss_turn": 0
            },
            {
                "player_number": 2,
                "attempt_count": 0,
                "miss_turn": 0
            }
        ],
        "active_player": 2,
        "turn_id": 2,
        "turn_seconds": 120
    }
}
```

**ERROR:**

Explain why a msg or action got rejected

| Payload field | Type | Rule |
|---|---|---|
| `code` | string | One of the error codes below |
| `message` | string | Human-readable explanation |
| `turn_id` | integer or null | Current turn ID; `null` before or after an active game |
| Error code | Meaning |
|---|---|
| `MALFORMED_MESSAGE` | Invalid UTF-8, JSON, fields, or field types |
| `UNKNOWN_MESSAGE` | Unrecognized `msg_type` |
| `INVALID_STATE` | Message is not allowed in the current game state |
| `INVALID_ALIAS` | Alias violates its rules or is already in use |
| `ALREADY_CONNECTED` | Registered client sent another `CONNECT` |
| `ROOM_FULL` | Two player slots are already occupied |
| `OUT_OF_TURN` | Sender is not the active player |
| `INVALID_GUESS` | Guess violates the digit rules |
| `STALE_TURN` | `turn_id` does not match the current turn |

```json
{
    "msg_type": "ERROR",
    "payload": {
        "code": "OUT_OF_TURN",
        "message": "It is Player 2's turn.",
        "turn_id": 2
    }
}
```

**DISCONNECT:**

Notify server of a deemed intentional departure

| Payload field | Type | Rule |
|---|---|---|
| `reason` | string | Exactly `"quit"` |

```json
{
    "msg_type": "DISCONNECT",
    "payload": {
        "reason": "quit"
    }
}
```

**GAME_OVER:**

ANNOUCEs final result and counters

| Payload field | Type | Rule |
|---|---|---|
| `outcome` | string | `"WIN"`, `"DRAW"`, or `"FORFEIT"` |
| `winner` | integer or null | Winning player number; `null` for a draw |
| `reason` | string | `"CODE_SOLVED"`, `"ATTEMPTS_EXHAUSTED"`, `"PLAYER_QUIT"`, `"CONNECTION_LOST"`, or `"TURN_TIMEOUT"` |
| `secret_code` | string | Four-digit secret, revealed after the game |
| `final_guess` | string or null | Most recent accepted guess; `null` if none |
| `players` | array of objects | Same player-counter structure as `STATE_UPDATE` |
| `message` | string | Human-readable result |

```json
{
    "msg_type": "GAME_OVER",
    "payload": {
        "outcome": "DRAW",
        "winner": null,
        "reason": "ATTEMPTS_EXHAUSTED",
        "secret_code": "5072",
        "final_guess": "0123",
        "players": [
            {
                "player_number": 1,
                "attempt_count": 10,
                "miss_turn": 0
            },
            {
                "player_number": 2,
                "attempt_count": 10,
                "miss_turn": 1
            }
        ],
        "message": "You both lose."
    }
}
```

**Framing and Receiver Rules**

Every message uses the same 4-byte unsigned big-endian length header followed by its UTF-8 JSON payload. Payload lengths must be between 1 and 16,384 bytes. A length outside this range causes the affected connection to close and triggers disconnect handling.

The sender serializes the JSON, encodes it as UTF-8, calculates the encoded byte length, and sends the header followed by the payload using sendall().

The receiver keeps a separate byte buffer for each client:

1. Accumulate at least four bytes to read the header.
2. Decode and validate the payload length.
3. Accumulate the specified number of payload bytes.
4. Extract the complete payload, decode UTF-8, parse JSON, and validate its schema.
5. Process additional complete frames already in the buffer.
6. Keep incomplete bytes for the next read.

One recv() may contain part of a header, part of a payload, or several messages. Turn deadlines must still be checked while a frame is incomplete.

**Continous wire Example**

tcp doesnt include insert seperators so we will use the length stored in first 4 bytes of header to tell reciever where msg should end based of senders UTF-8 byte length of json

```text
\x00\x00\x00\x3A{"msg_type":"MOVE","payload":{"guess":"0123","turn_id":1}}\x00\x00\x00\x3A{"msg_type":"MOVE","payload":{"guess":"4567","turn_id":2}}
```

Each JSON payload shown above is 58 bytes. Its header is 4 bytes 00 00 00 3A, representing 58 in big-endian order. Whole frame here is 62 bytes

TCP may deliver both frames in one read or split either header or payload across several reads. The receiver first collects four header bytes and interprets them as a big-endian payload length. In these examples, that length is 58, so it collects the next 58 bytes before parsing the JSON. The sender calculates the actual UTF-8 payload length for every message. For example, a 500-byte payload would have the header 00 00 01 F4. The \x notation represents actual binary header bytes.

**Validation and Game Handling**

The server validates message names, required fields, types, and values. Invalid messages produce ERROR without changing attempts, active player, or deadline. MOVE must come from the active player and match the current turn_id. Each new turn increments turn_id. Timeout behavior follows the FSM specification. Feedback provides counts only, without identifying which digits or positions are correct.

**Connection Termination and Socket Lifecycle**

The client sends DISCONNECT before closing its socket. A lobby departure frees the player slot;  an active-game departure gives the connected opponent a win by forfeit.

TCP FIN/clean closure is detected when recv() returns b"". Stop reading that socket to prevent an infinite loop and discard any incomplete frame. ConnectionResetError, BrokenPipeError, and ConnectionAbortedError trigger the same departure handling. TCP RST may cause ConnectionResetError; failed sends may cause BrokenPipeError. Both trigger the same departure handling. Silent network drops may not be detected immediately, but the FSM’s turn-timeout rules eventually end the game if the player cannot submit valid moves.

Handle each departure once. After the game, close client sockets, reset game data, and keep the listening socket open. If neither player remains before a result is recorded, clean up without a winner.
