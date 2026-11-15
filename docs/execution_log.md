# Sprint 3 Execution Log (localhost / 127.0.0.1)

Captured on 2026-11-15 with Python 3.14.0 on Windows 11. These are real, unedited console captures.
The server ran in one terminal and two clients in two others, all on localhost.
Client input was piped from stdin; the client echoes scripted input so the guesses appear below.

## Commands

```text
python server.py -p 5000
python client.py -i localhost -p 5000 -a Alice
python client.py -i localhost -p 5000 -a Bob
```

## What this run shows

- Two simultaneous clients connected. The hostname `localhost` is resolved through DNS (`socket.gethostbyname`).
- **8 completed turns** with alternating players, a board and score summary after every turn, and "YOUR TURN" / "Waiting for ..." status lines.
- An invalid guess (`1123`, repeated digit) is rejected with `INVALID_GUESS`. No attempt is used, and it stays Alice's turn (turn 3).
- Every `STATE_UPDATE` is queued identically to both players from the same server state.
- Alice types `quit`, so the client sends `DISCONNECT` and Bob wins by forfeit. `GAME_OVER` includes the leaderboard.
- Server FSM: `GAME_OVER -> CLEANUP -> WAITING_FOR_PLAYERS`. Bob stays connected and is renumbered Player 1 (`LOBBY_WAIT`).

## Server console

```text
15:38:01 [SERVER] Listening on 0.0.0.0:5000 (turn limit 120s)
15:38:01 [SERVER] FSM INIT -> WAITING_FOR_PLAYERS
15:38:02 [SERVER] Accepted connection from 127.0.0.1:57828
15:38:02 [SERVER] RECV <- 127.0.0.1:57828 CONNECT {"alias":"Alice"}
15:38:02 [SERVER] Registered P1:Alice
15:38:02 [SERVER] SEND -> P1:Alice LOBBY_WAIT {"player_number":1,"alias":"Alice","message":"Waiting for Player 2."}
15:38:03 [SERVER] Accepted connection from 127.0.0.1:57829
15:38:03 [SERVER] RECV <- 127.0.0.1:57829 CONNECT {"alias":"Bob"}
15:38:03 [SERVER] Registered P2:Bob
15:38:03 [SERVER] FSM WAITING_FOR_PLAYERS -> GAME_START
15:38:03 [SERVER] New round, secret code is 5846
15:38:03 [SERVER] SEND -> P1:Alice GAME_START {"player_number":1,"players":[{"player_number":1,"alias":"Alice"},{"player_number":2,"alias":"Bob"}],"active_player":1,"code_length":4,"attempt_limit":10,"turn_seconds":120,"turn_id":1}
15:38:03 [SERVER] SEND -> P2:Bob GAME_START {"player_number":2,"players":[{"player_number":1,"alias":"Alice"},{"player_number":2,"alias":"Bob"}],"active_player":1,"code_length":4,"attempt_limit":10,"turn_seconds":120,"turn_id":1}
15:38:03 [SERVER] FSM GAME_START -> PLAYER_TURN
15:38:03 [SERVER] Turn 1: Player 1 to move (120s)
15:38:03 [SERVER] RECV <- P1:Alice MOVE {"guess":"0123","turn_id":1}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"0123","correct_position":0,"wrong_position":0,"players":[{"player_number":1,"attempt_count":1,"miss_turn":0},{"player_number":2,"attempt_count":0,"miss_turn":0}],"active_player":2,"turn_id":2,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"0123","correct_position":0,"wrong_position":0,"players":[{"player_number":1,"attempt_count":1,"miss_turn":0},{"player_number":2,"attempt_count":0,"miss_turn":0}],"active_player":2,"turn_id":2,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 2: Player 2 to move (120s)
15:38:03 [SERVER] RECV <- P2:Bob MOVE {"guess":"3210","turn_id":2}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"3210","correct_position":0,"wrong_position":0,"players":[{"player_number":1,"attempt_count":1,"miss_turn":0},{"player_number":2,"attempt_count":1,"miss_turn":0}],"active_player":1,"turn_id":3,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"3210","correct_position":0,"wrong_position":0,"players":[{"player_number":1,"attempt_count":1,"miss_turn":0},{"player_number":2,"attempt_count":1,"miss_turn":0}],"active_player":1,"turn_id":3,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 3: Player 1 to move (120s)
15:38:03 [SERVER] RECV <- P1:Alice MOVE {"guess":"1123","turn_id":3}
15:38:03 [SERVER] SEND -> P1:Alice ERROR {"code":"INVALID_GUESS","message":"Guess must be 4 unique digits (0-9).","turn_id":3}
15:38:03 [SERVER] RECV <- P1:Alice MOVE {"guess":"4567","turn_id":3}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"4567","correct_position":0,"wrong_position":3,"players":[{"player_number":1,"attempt_count":2,"miss_turn":0},{"player_number":2,"attempt_count":1,"miss_turn":0}],"active_player":2,"turn_id":4,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"4567","correct_position":0,"wrong_position":3,"players":[{"player_number":1,"attempt_count":2,"miss_turn":0},{"player_number":2,"attempt_count":1,"miss_turn":0}],"active_player":2,"turn_id":4,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 4: Player 2 to move (120s)
15:38:03 [SERVER] RECV <- P2:Bob MOVE {"guess":"7654","turn_id":4}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"7654","correct_position":0,"wrong_position":3,"players":[{"player_number":1,"attempt_count":2,"miss_turn":0},{"player_number":2,"attempt_count":2,"miss_turn":0}],"active_player":1,"turn_id":5,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"7654","correct_position":0,"wrong_position":3,"players":[{"player_number":1,"attempt_count":2,"miss_turn":0},{"player_number":2,"attempt_count":2,"miss_turn":0}],"active_player":1,"turn_id":5,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 5: Player 1 to move (120s)
15:38:03 [SERVER] RECV <- P1:Alice MOVE {"guess":"8901","turn_id":5}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"8901","correct_position":0,"wrong_position":1,"players":[{"player_number":1,"attempt_count":3,"miss_turn":0},{"player_number":2,"attempt_count":2,"miss_turn":0}],"active_player":2,"turn_id":6,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"8901","correct_position":0,"wrong_position":1,"players":[{"player_number":1,"attempt_count":3,"miss_turn":0},{"player_number":2,"attempt_count":2,"miss_turn":0}],"active_player":2,"turn_id":6,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 6: Player 2 to move (120s)
15:38:03 [SERVER] RECV <- P2:Bob MOVE {"guess":"9876","turn_id":6}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"9876","correct_position":2,"wrong_position":0,"players":[{"player_number":1,"attempt_count":3,"miss_turn":0},{"player_number":2,"attempt_count":3,"miss_turn":0}],"active_player":1,"turn_id":7,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"9876","correct_position":2,"wrong_position":0,"players":[{"player_number":1,"attempt_count":3,"miss_turn":0},{"player_number":2,"attempt_count":3,"miss_turn":0}],"active_player":1,"turn_id":7,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 7: Player 1 to move (120s)
15:38:03 [SERVER] RECV <- P1:Alice MOVE {"guess":"2345","turn_id":7}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"2345","correct_position":1,"wrong_position":1,"players":[{"player_number":1,"attempt_count":4,"miss_turn":0},{"player_number":2,"attempt_count":3,"miss_turn":0}],"active_player":2,"turn_id":8,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":1,"guess":"2345","correct_position":1,"wrong_position":1,"players":[{"player_number":1,"attempt_count":4,"miss_turn":0},{"player_number":2,"attempt_count":3,"miss_turn":0}],"active_player":2,"turn_id":8,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 8: Player 2 to move (120s)
15:38:03 [SERVER] RECV <- P2:Bob MOVE {"guess":"5432","turn_id":8}
15:38:03 [SERVER] FSM PLAYER_TURN -> EVALUATE_MOVE
15:38:03 [SERVER] SEND -> P1:Alice STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"5432","correct_position":1,"wrong_position":1,"players":[{"player_number":1,"attempt_count":4,"miss_turn":0},{"player_number":2,"attempt_count":4,"miss_turn":0}],"active_player":1,"turn_id":9,"turn_seconds":120}
15:38:03 [SERVER] SEND -> P2:Bob STATE_UPDATE {"event":"GUESS_RESULT","previous_player":2,"guess":"5432","correct_position":1,"wrong_position":1,"players":[{"player_number":1,"attempt_count":4,"miss_turn":0},{"player_number":2,"attempt_count":4,"miss_turn":0}],"active_player":1,"turn_id":9,"turn_seconds":120}
15:38:03 [SERVER] FSM EVALUATE_MOVE -> PLAYER_TURN
15:38:03 [SERVER] Turn 9: Player 1 to move (120s)
15:38:03 [SERVER] RECV <- P1:Alice DISCONNECT {"reason":"quit"}
15:38:03 [SERVER] P1:Alice departed (PLAYER_QUIT) during PLAYER_TURN
15:38:03 [SERVER] FSM PLAYER_TURN -> GAME_OVER
15:38:03 [SERVER] SEND -> P2:Bob GAME_OVER {"outcome":"FORFEIT","winner":2,"reason":"PLAYER_QUIT","secret_code":"5846","final_guess":"5432","players":[{"player_number":1,"attempt_count":4,"miss_turn":0},{"player_number":2,"attempt_count":4,"miss_turn":0}],"message":"Alice quit; Bob wins by forfeit.","leaderboard":[{"player_number":2,"alias":"Bob","rounds_won":1,"total_guesses":4},{"player_number":1,"alias":"Alice","rounds_won":0,"total_guesses":4}]}
15:38:03 [SERVER] FSM GAME_OVER -> CLEANUP
15:38:03 [SERVER] FSM CLEANUP -> WAITING_FOR_PLAYERS
15:38:03 [SERVER] SEND -> P1:Bob LOBBY_WAIT {"player_number":1,"alias":"Bob","message":"Waiting for Player 2."}
```

## Client 1 (Alice)

```text
Resolved localhost -> 127.0.0.1
Connected to 127.0.0.1:5000 as Alice

Registered as Player 1 (Alice). Waiting for Player 2.
Waiting for Player 2...

====================================================
 GAME START: P1 Alice vs P2 Bob
 You are Player 1. Crack the 4-digit code (unique digits), 10 attempts each.
====================================================

>>> YOUR TURN (turn 1, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 0123

Alice guessed 0123: 0 right place, 0 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
----------------------------------------------------
 Score  P1 Alice: 1/10 attempts, 0 missed  |  P2 Bob: 0/10 attempts, 0 missed

Waiting for Bob's guess... (turn 2)

Bob guessed 3210: 0 right place, 0 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
----------------------------------------------------
 Score  P1 Alice: 1/10 attempts, 0 missed  |  P2 Bob: 1/10 attempts, 0 missed

>>> YOUR TURN (turn 3, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 1123

[SERVER ERROR] INVALID_GUESS: Guess must be 4 unique digits (0-9).
Still your turn - try again.
Your guess: 4567

Alice guessed 4567: 0 right place, 3 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
----------------------------------------------------
 Score  P1 Alice: 2/10 attempts, 0 missed  |  P2 Bob: 1/10 attempts, 0 missed

Waiting for Bob's guess... (turn 4)

Bob guessed 7654: 0 right place, 3 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
----------------------------------------------------
 Score  P1 Alice: 2/10 attempts, 0 missed  |  P2 Bob: 2/10 attempts, 0 missed

>>> YOUR TURN (turn 5, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 8901

Alice guessed 8901: 0 right place, 1 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
----------------------------------------------------
 Score  P1 Alice: 3/10 attempts, 0 missed  |  P2 Bob: 2/10 attempts, 0 missed

Waiting for Bob's guess... (turn 6)

Bob guessed 9876: 2 right place, 0 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
----------------------------------------------------
 Score  P1 Alice: 3/10 attempts, 0 missed  |  P2 Bob: 3/10 attempts, 0 missed

>>> YOUR TURN (turn 7, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 2345

Alice guessed 2345: 1 right place, 1 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
    7 | P1 Alice       | 2345  |   1   |   1  
----------------------------------------------------
 Score  P1 Alice: 4/10 attempts, 0 missed  |  P2 Bob: 3/10 attempts, 0 missed

Waiting for Bob's guess... (turn 8)

Bob guessed 5432: 1 right place, 1 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
    7 | P1 Alice       | 2345  |   1   |   1  
    8 | P2 Bob         | 5432  |   1   |   1  
----------------------------------------------------
 Score  P1 Alice: 4/10 attempts, 0 missed  |  P2 Bob: 4/10 attempts, 0 missed

>>> YOUR TURN (turn 9, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: quit
You left the game.

Connection to server closed.
```

## Client 2 (Bob)

```text
Resolved localhost -> 127.0.0.1
Connected to 127.0.0.1:5000 as Bob

====================================================
 GAME START: P1 Alice vs P2 Bob
 You are Player 2. Crack the 4-digit code (unique digits), 10 attempts each.
====================================================

Waiting for Alice's guess... (turn 1)

Alice guessed 0123: 0 right place, 0 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
----------------------------------------------------
 Score  P1 Alice: 1/10 attempts, 0 missed  |  P2 Bob: 0/10 attempts, 0 missed

>>> YOUR TURN (turn 2, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 3210

Bob guessed 3210: 0 right place, 0 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
----------------------------------------------------
 Score  P1 Alice: 1/10 attempts, 0 missed  |  P2 Bob: 1/10 attempts, 0 missed

Waiting for Alice's guess... (turn 3)

Alice guessed 4567: 0 right place, 3 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
----------------------------------------------------
 Score  P1 Alice: 2/10 attempts, 0 missed  |  P2 Bob: 1/10 attempts, 0 missed

>>> YOUR TURN (turn 4, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 7654

Bob guessed 7654: 0 right place, 3 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
----------------------------------------------------
 Score  P1 Alice: 2/10 attempts, 0 missed  |  P2 Bob: 2/10 attempts, 0 missed

Waiting for Alice's guess... (turn 5)

Alice guessed 8901: 0 right place, 1 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
----------------------------------------------------
 Score  P1 Alice: 3/10 attempts, 0 missed  |  P2 Bob: 2/10 attempts, 0 missed

>>> YOUR TURN (turn 6, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 9876

Bob guessed 9876: 2 right place, 0 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
----------------------------------------------------
 Score  P1 Alice: 3/10 attempts, 0 missed  |  P2 Bob: 3/10 attempts, 0 missed

Waiting for Alice's guess... (turn 7)

Alice guessed 2345: 1 right place, 1 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
    7 | P1 Alice       | 2345  |   1   |   1  
----------------------------------------------------
 Score  P1 Alice: 4/10 attempts, 0 missed  |  P2 Bob: 3/10 attempts, 0 missed

>>> YOUR TURN (turn 8, 120s) <<<
Enter 4 unique digits, or 'quit' to leave.
Your guess: 5432

Bob guessed 5432: 1 right place, 1 wrong place.
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
    7 | P1 Alice       | 2345  |   1   |   1  
    8 | P2 Bob         | 5432  |   1   |   1  
----------------------------------------------------
 Score  P1 Alice: 4/10 attempts, 0 missed  |  P2 Bob: 4/10 attempts, 0 missed

Waiting for Alice's guess... (turn 9)

====================================================
 GAME OVER - YOU WIN! (FORFEIT, PLAYER_QUIT)
 Alice quit; Bob wins by forfeit.
 Secret code was 5846
====================================================
----------------------------------------------------
 Turn | Player         | Guess | Right | Moved
----------------------------------------------------
    1 | P1 Alice       | 0123  |   0   |   0  
    2 | P2 Bob         | 3210  |   0   |   0  
    3 | P1 Alice       | 4567  |   0   |   3  
    4 | P2 Bob         | 7654  |   0   |   3  
    5 | P1 Alice       | 8901  |   0   |   1  
    6 | P2 Bob         | 9876  |   2   |   0  
    7 | P1 Alice       | 2345  |   1   |   1  
    8 | P2 Bob         | 5432  |   1   |   1  
----------------------------------------------------
 Score  P1 Alice: 4/10 attempts, 0 missed  |  P2 Bob: 4/10 attempts, 0 missed
 Leaderboard (session)
   #  Player               Wins  Guesses
   1  Bob                     1        4
   2  Alice                   0        4

Registered as Player 1 (Bob). Waiting for Player 2.
Waiting for Player 2...
```

## CLI help and argument validation

```text
$ python server.py -h
usage: server.py [-h] -p PORT [-t SECONDS]

Code-Breaker (Mastermind) game server. Listens on 0.0.0.0 for two players over
TCP.

options:
  -h, --help            show this help message and exit
  -p, --port PORT       listening port (1024-65535)
  -t, --turn-seconds SECONDS
                        seconds allowed per turn (default 120)

example: python3 server.py -p 8080

$ python client.py -h
usage: client.py [-h] -i HOSTNAME -p PORT [-a ALIAS]

Code-Breaker (Mastermind) console client.

options:
  -h, --help         show this help message and exit
  -i, --ip HOSTNAME  server DNS hostname (or IP), resolved via DNS
  -p, --port PORT    server port (1024-65535)
  -a, --alias ALIAS  player alias (prompted for if omitted)

examples:
  python3 client.py -i server.bowman.edu -p 8080
  python3 client.py -i localhost -p 8080 -a Alice

$ python server.py -p 80
usage: server.py [-h] -p PORT [-t SECONDS]
server.py: error: argument -p/--port: 80 is out of range (must be 1024-65535)
(exit code 2)

$ python client.py -i localhost -p abc
usage: client.py [-h] -i HOSTNAME -p PORT [-a ALIAS]
client.py: error: argument -p/--port: 'abc' is not a number
(exit code 2)

$ python client.py -p 5000
usage: client.py [-h] -i HOSTNAME -p PORT [-a ALIAS]
client.py: error: the following arguments are required: -i/--ip
(exit code 2)
```

## DNS failure handling

```text
$ python client.py -i server.bowman.invalid -p 5000
[ERROR] Unable to resolve DNS hostname 'server.bowman.invalid'.
Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.
(exit code 1)
```

## Connection refused (server not running)

```text
$ python client.py -i localhost -p 5999 -a Alice
Resolved localhost -> 127.0.0.1
[ERROR] Could not connect to 127.0.0.1:5999 ([WinError 10061] No connection could be made because the target machine actively refused it).
Is the server running and reachable?
(exit code 1)
```

## Automated test suite

```text
$ python -m unittest discover -s tests -v
test_both_exhausted (test_game.RoundTests.test_both_exhausted) ... ok
test_guess_counts_attempt_and_total (test_game.RoundTests.test_guess_counts_attempt_and_total) ... ok
test_leaderboard_order (test_game.RoundTests.test_leaderboard_order) ... ok
test_only_player_with_attempts_continues (test_game.RoundTests.test_only_player_with_attempts_continues) ... ok
test_timeouts (test_game.RoundTests.test_timeouts) ... ok
test_turns_alternate (test_game.RoundTests.test_turns_alternate) ... ok
test_guess_validation (test_game.RuleTests.test_guess_validation) ... ok
test_scoring (test_game.RuleTests.test_scoring) ... ok
test_secret_has_unique_digits (test_game.RuleTests.test_secret_has_unique_digits) ... ok
test_alias_rules (test_integration.GameFlowTests.test_alias_rules) ... ok
test_disconnect_forfeit_and_lobby_return (test_integration.GameFlowTests.test_disconnect_forfeit_and_lobby_return) ... ok
test_eof_is_connection_lost (test_integration.GameFlowTests.test_eof_is_connection_lost) ... ok
test_fragmented_frames_reach_server (test_integration.GameFlowTests.test_fragmented_frames_reach_server) ... ok
test_invalid_moves_do_not_change_turn (test_integration.GameFlowTests.test_invalid_moves_do_not_change_turn) ... ok
test_multi_turn_game_to_win (test_integration.GameFlowTests.test_multi_turn_game_to_win) ... ok
test_rematch_decline_returns_lobby (test_integration.GameFlowTests.test_rematch_decline_returns_lobby) ... ok
test_rematch_keeps_session_totals (test_integration.GameFlowTests.test_rematch_keeps_session_totals) ... ok
test_third_client_room_full (test_integration.GameFlowTests.test_third_client_room_full) ... ok
test_timeout_skip_then_forfeit (test_integration.GameFlowTests.test_timeout_skip_then_forfeit) ... ok
test_byte_by_byte_delivery (test_protocol.FramingTests.test_byte_by_byte_delivery) ... ok
test_header_is_big_endian_payload_length (test_protocol.FramingTests.test_header_is_big_endian_payload_length) ... ok
test_multiple_frames_in_one_chunk (test_protocol.FramingTests.test_multiple_frames_in_one_chunk) ... ok
test_oversize_length_rejected (test_protocol.FramingTests.test_oversize_length_rejected) ... ok
test_round_trip (test_protocol.FramingTests.test_round_trip) ... ok
test_split_header_and_payload (test_protocol.FramingTests.test_split_header_and_payload) ... ok
test_utf8_length_counts_bytes (test_protocol.FramingTests.test_utf8_length_counts_bytes) ... ok
test_zero_length_rejected (test_protocol.FramingTests.test_zero_length_rejected) ... ok
test_invalid (test_protocol.PortTypeTests.test_invalid) ... ok
test_valid (test_protocol.PortTypeTests.test_valid) ... ok
test_bad_json (test_protocol.SchemaTests.test_bad_json) ... ok
test_bad_utf8 (test_protocol.SchemaTests.test_bad_utf8) ... ok
test_bool_is_not_int (test_protocol.SchemaTests.test_bool_is_not_int) ... ok
test_disconnect_reason_must_be_quit (test_protocol.SchemaTests.test_disconnect_reason_must_be_quit) ... ok
test_missing_field (test_protocol.SchemaTests.test_missing_field) ... ok
test_rematch (test_protocol.SchemaTests.test_rematch) ... ok
test_server_message_from_client_is_unknown (test_protocol.SchemaTests.test_server_message_from_client_is_unknown) ... ok
test_unknown_type (test_protocol.SchemaTests.test_unknown_type) ... ok
test_wrong_type (test_protocol.SchemaTests.test_wrong_type) ... ok

----------------------------------------------------------------------
Ran 38 tests in 6.444s

OK
```
