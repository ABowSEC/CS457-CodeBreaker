# CS 457 Project Statement of Work (SOW) & Protocol Specification

**Student Name:** Andrew Bowman
**Date:** 2026-09-14  
**Course:** CS 457 - Computer Networks  
**Target Server Domain:** `server.bowman.edu`  

---

## 1. Game Selection & Scope (Sprint 0)

> Planning is going to be an iterative process through the sprints so you don't have to have all the details now. Focus on big overview concepts. You will be updating the SOW as we plan.
> You have a lot of freedom to choose a game. There are a couple caveats.  

> - It must run in the console. The lab nodes won't be able to handle extensive graphics.
> - It has to be self-contained. You can use a internet-connector to download you code, but because the architecture must run 5 nodes you won't be able to run 
> - You are encouraged to use python, but I'm not going to make it a strict requirement. The instructor and TA's ability to help with C or Rust, etc will be diminished in other languages.

### 1.1 Game Overview
- **Chosen Game:** Mastermind, Code-Breaker
- **Player Capacity:** 2 Players (Simulated via 2 CML Client nodes)
- **Game Summary:** The server comes up with a 4 digit random string of unique numbers. TWo clients connect and the clients will take turns guessing what the string is. After each guess, the server provides clues showing how many digits are correct and in the correct position, and how many digits are correct but in the wrong position. Players use this feedback to narrow down the possible code. The first player to correctly guess the entire secret code wins the game.


### 1.2 Core Game Rules & Win/Draw Conditions
- **Turn Mechanics:** Turn order can be dictated by connection order.
- **Victory Condition:** A player wins when they correctly guess all four digits of the secret code in the correct positions.
- **Draw/Tie Condition:** Each player is allowed a maximum of 10 guesses. If neither player correctly identifies the secret code after both players have used all 10 guesses, the game ends in a draw.

---

## 2. Application-Layer Messaging Protocol Blueprint (Sprint 1 Deliverable)

### 2.1 Message Transport & Serialization Format
- **Transport Protocol:** TCP
- **Serialization Format:** JSON (UTF-8)
- **Framing Mechanism:** 4-byte unsigned big-endian length prefix (payload 1–16,384 bytes), no newline terminator. Full detail is in `docs/protocol_blueprint.md`.

### 2.2 Message Schema Definitions

#### Message Types:
1. `CONNECT` (Client -> Server): Request to join the game room.
2. `LOBBY_WAIT` (Server -> Client): Notification that server is waiting for Player 2.
3. `GAME_START` (Server -> Clients): Game initiated, assigns roles (e.g. Player X vs Player O).
4. `MOVE` (Client -> Server): Player action (e.g., cell coordinates or answer choice).
5. `STATE_UPDATE` (Server -> Clients): Broadcast current game board / state and active player turn.
6. `GAME_OVER` (Server -> Clients): Victory / Draw notification with final scores.
7. `ERROR` (Server -> Client): Invalid move or malformed packet error.
8. `DISCONNECT` (Client -> Server): Intentional quit (forfeit during a game).
9. `REMATCH` (Client -> Server): Play-again choice after `GAME_OVER` (added in Sprint 3).

#### Example JSON Protocol Schema:
```json
{
  "msg_type": "MOVE",
  "payload": {
    "guess": "0123",
    "turn_id": 1
  }
}
```

---

### 2.3 Game State Machine (FSM) Design (Sprint 1 Deliverable)
- **State Transitions:** Detail state flow: `INIT` -> `WAITING_FOR_PLAYERS` -> `PLAYER_TURN` -> `EVALUATE_MOVE` -> `CHECK_WIN_DRAW` -> `GAME_OVER` -> `CLEANUP`.

---

## 3. Game Behavior & Server Concurrency Architecture (Sprint 2 Deliverable)

### 3.1 Server Concurrency Strategy
- **Architecture Choice:** Non-blocking I/O multiplexing with `selectors` (see `docs/concurrency_design.md`).
- **Synchronization Logic:** A single thread owns all game state, the player table and every socket, so no `threading.Lock` is needed. Each client has its own receive `FrameBuffer` and outgoing byte buffer. The selector watches for writability only while a buffer has data.

### 3.2 State & Score Synchronization Across Clients
- **Turn Enforcement:** Before processing a `MOVE`, the server checks the game state, the sender against `active_player`, `turn_id` against the current turn, and the guess format. Any failure returns `ERROR` and changes nothing.
- **Score & Board Synchronization:** After each valid guess or timeout, one `STATE_UPDATE` built from a single server state is queued for both players. Clients redraw the guess board, the score line and the turn status from it.

---

## 4. Coding & AI Implementation Plan (Sprint 3)

- **Permitted AI Tools:** Claude (Claude Code)
- **AI Prompting & Constraint Strategy:** The prompts in `docs/ai_prompts.md` name `docs/protocol_blueprint.md` and `docs/fsm_specifications.md` as the authoritative specs. They forbid inventing messages, fields or behavior, and require the AI to stop and ask when the specs are incomplete. That rule caught a real gap: the FSM's REMATCH_WAIT and leaderboard had no protocol message. It was resolved by adding `REMATCH` and the `leaderboard` field to the blueprint before any code was written.
- **Implementation Risk Management:** The code is split into small modules so each part can be tested on its own:
  - `protocol.py`: framing and schema
  - `game.py`: pure rules
  - `server.py`: selectors event loop and FSM
  - `client.py`: console UI

  Unit tests cover framing edge cases and rules. Integration tests start the real server and script two clients through wins, timeouts, forfeits and rematches. A localhost execution log is submitted separately.

### 4.1 How to Run (Sprint 3)
```text
python3 server.py -p 8080
python3 client.py -i server.bowman.edu -p 8080      # CML (Sprint 4)
python3 client.py -i localhost -p 8080              # local testing
python3 -m unittest discover -s tests -v
```

---

## 5. CML Multi-Subnet Topology & Wireshark Deployment Plan (Sprint 4 & 5 Deliverable)

> For now you can use the topology below. We may update this when we get to defining subnets.

### 5.1 Subnet & Router Design
- **Subnet A (Client 1):** `192.168.10.0/24` (Interface `Gi0/1` on Router R1)
- **Subnet B (Client 2):** `192.168.11.0/24` (Interface `Gi0/2` on Router R1)
- **Subnet C (Game Server):** `192.168.20.0/24` (Interface `Gi0/1` on Router R2)
- **Router Backbone:** `10.0.0.0/30` (Interface `Gi0/0` on R1 <-> `Gi0/0` on R2)

### 5.2 DHCP Pools & DNS Configuration Plan
- **Router R1 DHCP Pool 1 (`CLIENT1_POOL`):** Leases `192.168.10.10` - `192.168.10.50`, gateway `192.168.10.1`, DNS `10.0.0.2`.
- **Router R1 DHCP Pool 2 (`CLIENT2_POOL`):** Leases `192.168.11.10` - `192.168.11.50`, gateway `192.168.11.1`, DNS `10.0.0.2`.
- **Router R2 Authoritative DNS:** Configured with `ip dns server` and static host mapping `server.[yourlastname].edu` -> `192.168.20.100`.

### 5.3 Deployment Strategy & Wireshark Trace Capture
- **CML Deployment Strategy:** Deploy `server.py` onto Subnet C node (`192.168.20.100`) behind Router R2, and `client.py` onto Subnet A and Subnet B nodes behind Router R1.
- **Cisco Infrastructure Configuration:** Router R1 DHCP pools (`CLIENT1_POOL`, `CLIENT2_POOL`) and Router R2 authoritative DNS (`ip host server.[lastname].edu 192.168.20.100`).
- **Wireshark Trace Capture Plan:** Capture DHCP DORA exchange (`dhcp_negotiation.pcap`) and DNS query/response resolution (`dns_lookup.pcap`).
