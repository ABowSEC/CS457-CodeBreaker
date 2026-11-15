"""Unit tests for framing and schema validation (protocol.py)."""

import argparse
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import protocol as proto  # noqa: E402


def frames_of(buf):
    return list(buf.frames())


class FramingTests(unittest.TestCase):

    def test_header_is_big_endian_payload_length(self):
        data = proto.encode_message(proto.MOVE,
                                    {"guess": "0123", "turn_id": 1})
        (length,) = struct.unpack("!I", data[:4])
        self.assertEqual(length, len(data) - 4)
        # Matches the blueprint wire example: 58-byte payload -> 0x3A.
        self.assertEqual(data[:4], b"\x00\x00\x00\x3a")

    def test_round_trip(self):
        buf = proto.FrameBuffer()
        buf.feed(proto.encode_message(proto.CONNECT, {"alias": "Superman"}))
        [raw] = frames_of(buf)
        msg = proto.decode_payload(raw)
        self.assertEqual(proto.validate_message(msg, proto.CLIENT_MESSAGES),
                         (proto.CONNECT, {"alias": "Superman"}))

    def test_byte_by_byte_delivery(self):
        data = proto.encode_message(proto.CONNECT, {"alias": "A"})
        buf = proto.FrameBuffer()
        got = []
        for i in range(len(data)):
            buf.feed(data[i:i + 1])
            got.extend(buf.frames())
        self.assertEqual(len(got), 1)

    def test_split_header_and_payload(self):
        data = proto.encode_message(proto.CONNECT, {"alias": "Bob"})
        buf = proto.FrameBuffer()
        buf.feed(data[:2])                     # half a header
        self.assertEqual(frames_of(buf), [])
        buf.feed(data[2:10])                   # rest of header + some body
        self.assertEqual(frames_of(buf), [])
        self.assertTrue(buf.has_partial())
        buf.feed(data[10:])
        self.assertEqual(len(frames_of(buf)), 1)
        self.assertFalse(buf.has_partial())

    def test_multiple_frames_in_one_chunk(self):
        a = proto.encode_message(proto.MOVE, {"guess": "0123", "turn_id": 1})
        b = proto.encode_message(proto.MOVE, {"guess": "4567", "turn_id": 2})
        buf = proto.FrameBuffer()
        buf.feed(a + b + b[:3])                # two whole + a partial
        self.assertEqual(len(frames_of(buf)), 2)
        buf.feed(b[3:])
        self.assertEqual(len(frames_of(buf)), 1)

    def test_zero_length_rejected(self):
        buf = proto.FrameBuffer()
        buf.feed(b"\x00\x00\x00\x00")
        with self.assertRaises(proto.FrameError):
            frames_of(buf)

    def test_oversize_length_rejected(self):
        buf = proto.FrameBuffer()
        buf.feed(struct.pack("!I", proto.MAX_PAYLOAD + 1))
        with self.assertRaises(proto.FrameError):
            frames_of(buf)

    def test_utf8_length_counts_bytes(self):
        data = proto.encode_message(proto.ERROR, {"code": "X",
                                                  "message": "é",
                                                  "turn_id": None})
        (length,) = struct.unpack("!I", data[:4])
        self.assertEqual(length, len(data[4:]))


class SchemaTests(unittest.TestCase):

    def check(self, msg, allowed=proto.CLIENT_MESSAGES):
        return proto.validate_message(msg, allowed)

    def assertCode(self, code, msg, allowed=proto.CLIENT_MESSAGES):
        with self.assertRaises(proto.ProtocolError) as ctx:
            self.check(msg, allowed)
        self.assertEqual(ctx.exception.code, code)

    def test_bad_json(self):
        with self.assertRaises(proto.ProtocolError) as ctx:
            proto.decode_payload(b"{not json")
        self.assertEqual(ctx.exception.code, proto.E_MALFORMED)

    def test_bad_utf8(self):
        with self.assertRaises(proto.ProtocolError):
            proto.decode_payload(b"\xff\xfe")

    def test_unknown_type(self):
        self.assertCode(proto.E_UNKNOWN, {"msg_type": "HELLO", "payload": {}})

    def test_server_message_from_client_is_unknown(self):
        self.assertCode(proto.E_UNKNOWN,
                        {"msg_type": "GAME_OVER", "payload": {}})

    def test_missing_field(self):
        self.assertCode(proto.E_MALFORMED,
                        {"msg_type": "MOVE", "payload": {"guess": "0123"}})

    def test_wrong_type(self):
        self.assertCode(proto.E_MALFORMED,
                        {"msg_type": "MOVE",
                         "payload": {"guess": "0123", "turn_id": "1"}})

    def test_bool_is_not_int(self):
        self.assertCode(proto.E_MALFORMED,
                        {"msg_type": "MOVE",
                         "payload": {"guess": "0123", "turn_id": True}})

    def test_disconnect_reason_must_be_quit(self):
        self.assertCode(proto.E_MALFORMED,
                        {"msg_type": "DISCONNECT",
                         "payload": {"reason": "bye"}})

    def test_rematch(self):
        self.assertEqual(self.check({"msg_type": "REMATCH",
                                     "payload": {"play_again": True}})[0],
                         proto.REMATCH)
        self.assertCode(proto.E_MALFORMED,
                        {"msg_type": "REMATCH",
                         "payload": {"play_again": "yes"}})


class PortTypeTests(unittest.TestCase):

    def test_valid(self):
        self.assertEqual(proto.port_type("8080"), 8080)

    def test_invalid(self):
        for bad in ("80", "70000", "abc", "-1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                proto.port_type(bad)


if __name__ == "__main__":
    unittest.main()
