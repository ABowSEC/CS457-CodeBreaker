I will be going to use Option B: Non-Blocking I/O Multiplexing (selectors / select.select)
    The server sets client sockets to non-blocking mode (sock.setblocking(False)).
    An OS event loop monitors read/write availability across all sockets within a single thread.

This keeps clean states and lets us easily handle player 1 and 2. There is no need to have a thread for each client in this type of game since only one player can make a valid guess at a time. The game is turn based with 2 players so the work is directed towards simply being one at a time. Threads would add races that would then need locks to handle it.

**Synchronization Logic**

No threading.Lock is needed because one thread handles all changes to game state, player information, and client connections. The server validates the active player, turn_id, and guess format before updating game state. Invalid or out-of-turn guesses receive an ERROR without changing the game.

**General Event Loop**

The listening socket and both client sockets are registered with the selector.

- When the listening socket is readable the server accepts the connection, sets it to non-blocking, and registers it. A third client receives ROOM_FULL and is closed after the response is sent.
- When a client socket is readable, incoming bytes enter that client’s receive buffer. Complete length-prefixed frames are validated and passed to the FSM. Incomplete frames stay buffered until more data arrives.
- Invalid payload lengths or malformed messages are rejected
- BlockingIOError means try again later. An empty receive result or connection error triggers my departure handling.
**Turn Timeout**

Each turn lasts 120 seconds. The selector waits for either socket activity or the turn deadline. The server checks the deadline before processing a guess and after handling events. In the lobby there will be no active turn deadline .

**Sending**

Each client should have an outgoing byte buffer. The selector monitors write availability when that buffer contains data. The server sends what it can and keeps any remaining bytes for the next writable event. After a valid guess, the server queues the same STATE_UPDATE for both players. Both updates come from the same server state

**Score Sync and leaderboard*

The server stores each player’s attempt count, guess results, total guesses, and rounds won in session memory. After a valid guess, it updates the values and queues the same STATE_UPDATE for both players. When the game finishes, it updates the leaderboard and queues GAME_OVER with the outcome, final attempt counts, and updated leaderboard for both clients. The leaderboard ranks players by rounds won and also displays total guesses.

**Cleanup plan and rematch**

After GAME_OVER, both clients remain connected and can choose to play again. If both agree, the server generates a new secret code and resets attempts, missed turns, turn_id, and turn timers. Session totals for wins and guesses are preserved.
If a player declines or disconnects, the server handles their departure and returns the remaining player to WAITING_FOR_PLAYERS. Departing clients are marked disconnected so cleanup only happens once, and their sockets are unregistered before being fully closed

