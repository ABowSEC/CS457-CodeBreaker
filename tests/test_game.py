"""Unit tests for game rules (game.py)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import game  # noqa: E402


class RuleTests(unittest.TestCase):

    def test_secret_has_unique_digits(self):
        for _ in range(200):
            secret = game.generate_secret()
            self.assertTrue(game.is_valid_guess(secret))

    def test_guess_validation(self):
        self.assertTrue(game.is_valid_guess("0123"))
        for bad in ("012", "01234", "0012", "abcd", "12 3", "", None, 1234):
            self.assertFalse(game.is_valid_guess(bad), bad)

    def test_scoring(self):
        self.assertEqual(game.score_guess("5072", "5072"), (4, 0))
        self.assertEqual(game.score_guess("5072", "2705"), (0, 4))
        self.assertEqual(game.score_guess("5072", "0123"), (0, 2))
        self.assertEqual(game.score_guess("5072", "5341"), (1, 0))
        self.assertEqual(game.score_guess("5072", "1346"), (0, 0))


class RoundTests(unittest.TestCase):

    def make_round(self):
        players = {1: game.Player("A", 1), 2: game.Player("B", 2)}
        rnd = game.Round(players)
        rnd.secret = "5072"
        return rnd

    def test_guess_counts_attempt_and_total(self):
        rnd = self.make_round()
        rnd.apply_guess("0123")
        p1 = rnd.players[1]
        self.assertEqual((p1.attempt_count, p1.total_guesses), (1, 1))
        self.assertEqual(rnd.final_guess, "0123")

    def test_turns_alternate(self):
        rnd = self.make_round()
        rnd.apply_guess("0123")
        rnd.advance_turn(rnd.next_eligible_player())
        self.assertEqual((rnd.active_player, rnd.turn_id), (2, 2))

    def test_only_player_with_attempts_continues(self):
        rnd = self.make_round()
        rnd.players[2].attempt_count = game.ATTEMPT_LIMIT
        self.assertEqual(rnd.next_eligible_player(), 1)

    def test_both_exhausted(self):
        rnd = self.make_round()
        for p in rnd.players.values():
            p.attempt_count = game.ATTEMPT_LIMIT
        self.assertTrue(rnd.both_exhausted())
        self.assertIsNone(rnd.next_eligible_player())

    def test_timeouts(self):
        rnd = self.make_round()
        self.assertFalse(rnd.apply_timeout())     # first: skip + attempt
        p1 = rnd.players[1]
        self.assertEqual((p1.miss_turn, p1.attempt_count,
                          p1.total_guesses), (1, 1, 0))
        self.assertTrue(rnd.apply_timeout())      # second: forfeit

    def test_leaderboard_order(self):
        a, b = game.Player("A", 1), game.Player("B", 2)
        b.rounds_won = 1
        board = game.leaderboard([a, b])
        self.assertEqual([e["alias"] for e in board], ["B", "A"])


if __name__ == "__main__":
    unittest.main()
