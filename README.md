# CS457 Code-Breaker (Mastermind)

A two-player networked Mastermind game for the console. The server picks a secret code of 4 unique digits. Players take turns guessing, and after each guess the server reports how many digits are in the right place and how many are right but in the wrong place. The first player to crack the code wins. If both players use all 10 attempts, the game is a draw.

Requires Python 3.8+ and the standard library only.

## Running

```text
# Server: binds 0.0.0.0, port 1024-65535 required
python3 server.py -p 8080
python3 server.py -p 8080 -t 30      # optional: 30-second turns (default 120)

# Clients: the hostname is resolved through DNS
python3 client.py -i server.bowman.edu -p 8080
python3 client.py -i localhost -p 8080 -a Alice   # -a skips the alias prompt
```

During your turn, type 4 unique digits (for example `0123`), or type `quit` to leave (your opponent wins by forfeit). After a game, both players are asked `Play again? (y/n)`. Session wins and guesses carry over into rematches.

If the hostname cannot be resolved, the client prints a DNS troubleshooting hint and exits with status 1.

## Files

| File | Purpose |
|---|---|
| `server.py` | Single-threaded `selectors` event loop with the game FSM |
| `client.py` | Console client: argument parsing, DNS resolution, receiver thread, UI |
| `protocol.py` | 4-byte length-prefix framing, JSON serialization, schema validation |
| `game.py` | Pure game rules (secret, scoring, turns, timeouts, leaderboard) |
| `tests/` | Unit and integration tests |
| `docs/` | Protocol blueprint, FSM, concurrency design, sequence diagram, execution log |

## Tests

```text
python3 -m unittest discover -s tests -v
```

The integration tests start a real `server.py` on a free localhost port and script two clients through wins, invalid moves, fragmented frames, timeouts, forfeits and rematches.
