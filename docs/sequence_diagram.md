
***NEED TO UPDATE TO MY SPECS***

```mermaid
sequenceDiagram
    autonumber
    actor Client1 as Client 1 (Player X)
    participant Server as Game Server
    actor Client2 as Client 2 (Player O)

    Client1->>Server: Guess
    Note over Server: Server validates: Is it Client 1's turn?<br>Is String length correct?
    alt Valid Move
        Note over Server: Update Game Board<br>Switch Active Turn to Player 2
        Server-->>Client1: STATE_UPDATE (Guess result, Turn: Player 2)
        Server-->>Client2: STATE_UPDATE (Guess result, Turn: Player 2)
    else Invalid / Out of Turn Move
        Server-->>Client1: ERROR ("Invalid Guess" or "Not Your Turn")
    end
```

I think im going to use Option B: Non-Blocking I/O Multiplexing (selectors / select.select)
    The server sets client sockets to non-blocking mode (sock.setblocking(False)).
    An OS event loop monitors read/write availability across all sockets within a single thread.

This may keep clean states and ensure we easily handle player 1 and 2 no need to have a thread for this type of game need to confirm still.