Detailed state transition diagram created strictly using Mermaid (stateDiagram-v2) syntax and state handling logic, explicitly addressing valid moves, invalid moves, and unexpected client disconnections.


```mermaid
stateDiagram-v2
    [*] --> Init
    Init --> Wait_For_Conn
    Wait_For_Conn --> Start_Game
    Start_Game --> Player_Turn
    Player_Turn --> Eval_Move
    Eval_Move --> Player_Turn : invalid_Move
    Eval_Move --> End_Game
    End_Game --> CLEANUP : client disconnect
    CLEANUP --> Wait_For_Conn
```