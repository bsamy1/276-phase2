from collections import defaultdict
from datetime import timedelta


class UserStats:
    def __init__(self):
        self.daily_streak = 0
        self.longest_daily_streak = 0
        self.average_daily_guesses = 0.0
        self.average_daily_time = timedelta(seconds=0)
        self.longest_survival_streak = 0
        self.score = 0

class LocalStatisticsRepo:
    """
    A local statistics repository to replace RoundStatisticsRepository.
    """

    def __init__(self):
        # store stats per user_id
        self.stats = defaultdict(UserStats)

    def get_leaderboard_stats_for_user(self, user_id: int) -> UserStats | None:
        """
        Returns the UserStats object for the given user_id.
        """
        return self.stats.get(user_id, None)

    def add_round_stats(
        self, 
        user_id: int, 
        daily_streak: int, 
        guesses: int, 
        time_seconds: int, 
        survival_streak: int, 
        score: int,
    ):
        """
        Update the stats for a user.
        """
        s = self.stats[user_id]
        s.daily_streak = daily_streak
        s.longest_daily_streak = max(s.longest_daily_streak, daily_streak)
        if s.average_daily_guesses == 0:
            s.average_daily_guesses = guesses
        else:
            s.average_daily_guesses = (s.average_daily_guesses + guesses) / 2
        s.average_daily_time = timedelta(
            seconds=((s.average_daily_time.total_seconds() + time_seconds) / 2)
        )
        s.longest_survival_streak = max(s.longest_survival_streak, survival_streak)
        s.score += score