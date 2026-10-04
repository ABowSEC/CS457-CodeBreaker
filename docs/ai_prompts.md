Documented system prompts used to force AI coding tools to implement parser/serialization functions matching your exact schema.

FOR my FSM I need assitance structuring clear DISCONNECT flag from client. Additionaly help me understand what I should do in the case of Transport-Layer Teardown (TCP FIN / Clean Closure)  which will  initiate the TCP 4-way FIN handshake. We need to ensure we handle these know possibilities gracefully and have a standard for silent dissconnects as well.

Implement only the requested part of my game. Treat docs/protocol_blueprint.md and docs/fsm_specifications.md as the authoritative specifications.

Use TCP with UTF-8 JSON serialization and a 4-byte unsigned big-endian length prefix. The prefix must contain the byte length of the JSON payload, excluding the header. Match the exact message names, required fields, data types, allowed values, and payload-size limits defined in my protocol blueprint.  Do not invent messages, fields, defaults, or game behavior.

Do not assume one recv() call returns one complete message. Handle fragmented headers, fragmented payloads, and multiple messages arriving together. Preserve incomplete data until the remaining bytes arrive.Handle recv() returning b"" as EOF. Stop reading that socket and trigger the specified departure handling. Discard incomplete frames when the connection ends. Handle ConnectionResetError, BrokenPipeError, ConnectionAbortedError, and applicable socket timeouts without crashing the server.

Validate the frame length before accepting the payload. Validate decoded messages against the blueprint before dispatching them to the game engine. 

Follow the FSM exactly. Invalid or out of turn moves must not consume an attempt, change the active player, or reset the turn deadline. Each player’s departure must be handled only once. Keep framing and schema validation separate from game state validation. Do not add reconnection support.

Implement only the serializer and stream parser for this task. Calculate the payload length after UTF-8 encoding. If my specifications are incomplete or inconsistent, identify the issue before generating the affected code and always refer to me about anything that would need further decisions I have not specified during build process.