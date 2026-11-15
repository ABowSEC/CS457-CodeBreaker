"""Pure game logic for Code-Breaker (no sockets, no I/O).

Kept separate from server.py so the rules can be unit tested on their own
and so the network layer never decides game outcomes by itself.
"""

import random

CODE_LENGTH = 4        # digits in the secret
ATTEMPT_LIMIT = 10     # attempts per player per round
TURN_SECONDS = 120     # default seconds per turn
MAX_MISSED_TURNS = 2   # a second timeout forfeits the round

DRAW_MESSAGE = "You both lose."


def generate_secret():
    """Return a random code of CODE_LENGTH unique digits, e.g. '5072'."""
    return "".join(random.sample("0123456789", CODE_LENGTH))


def is_valid_guess(guess):
    """A guess is exactly four unique ASCII digits (leading zeros allowed)."""
    return (isinstance(guess, str)
            and len(guess) == CODE_LENGTH
            and all(ch in "0123456789" for ch in guess)
            and len(set(guess)) == CODE_LENGTH)


def score_guess(secret, guess):
    """Return (correct_position, wrong_position) for a valid guess.

    Because digits are unique, "wrong position" is simply the number of
    shared digits minus the ones that are already in the right place.
    """
    correct = sum(1 for s, g in zip(secret, guess) if s == g)
    shared = len(set(secret) & set(guess))
    return correct, shared - correct


class Player:
    """One connected player: per-round counters plus session totals."""

    def __init__(self, alias, player_number):
        self.alias = alias
        self.player_number = player_number
        # Per-round counters (reset at every GAME_START).
        self.attempt_count = 0
        self.miss_turn = 0
        # Session totals (kept across rematches while connected).
        self.rounds_won = 0
        self.total_guesses = 0

    def reset_round(self):
        self.attempt_count = 0
        self.miss_turn = 0

    def has_attempts(self):
        return self.attempt_count < ATTEMPT_LIMIT

    def counters(self):
        """Player-counter object used in STATE_UPDATE / GAME_OVER."""
        return {"player_number": self.player_number,
                "attempt_count": self.attempt_count,
                "miss_turn": self.miss_turn}


class Round:
    """State for one game round between two players."""

    def __init__(self, players, turn_seconds=TURN_SECONDS):
        # players: dict {1: Player, 2: Player}
        self.players = players
        self.turn_seconds = turn_seconds
        self.secret = generate_secret()
        self.turn_id = 1
        self.active_player = 1
        self.final_guess = None
        for p in players.values():
            p.reset_round()

    def opponent_of(self, number):
        return 2 if number == 1 else 1

    def next_eligible_player(self):
        """Who plays next: the opponent if they still have attempts, else
        the same player; None when both are out of attempts (draw)."""
        other = self.opponent_of(self.active_player)
        if self.players[other].has_attempts():
            return other
        if self.players[self.active_player].has_attempts():
            return self.active_player
        return None

    def both_exhausted(self):
        return all(not p.has_attempts() for p in self.players.values())

    def counters(self):
        return [self.players[1].counters(), self.players[2].counters()]

    def apply_guess(self, guess):
        """Record a valid guess by the active player.

        Returns (correct_position, wrong_position).  Caller decides what
        happens next (win / draw / next turn).
        """
        player = self.players[self.active_player]
        player.attempt_count += 1
        player.total_guesses += 1
        self.final_guess = guess
        return score_guess(self.secret, guess)

    def apply_timeout(self):
        """Record a missed turn for the active player.

        Returns True if this was that player's second timeout (forfeit).
        A timeout consumes an attempt but is not a submitted guess.
        """
        player = self.players[self.active_player]
        player.miss_turn += 1
        if player.miss_turn >= MAX_MISSED_TURNS:
            return True
        player.attempt_count = min(player.attempt_count + 1, ATTEMPT_LIMIT)
        return False

    def advance_turn(self, next_player):
        """Move to the next turn: new active player and turn_id + 1."""
        self.active_player = next_player
        self.turn_id += 1


def leaderboard(players):
    """Rank players by rounds won (desc), then fewest total guesses."""
    ranked = sorted(players, key=lambda p: (-p.rounds_won, p.total_guesses,
                                            p.player_number))
    return [{"player_number": p.player_number, "alias": p.alias,
             "rounds_won": p.rounds_won, "total_guesses": p.total_guesses}
            for p in ranked]
