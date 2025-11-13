class LeaderboardEntry:
    __tablename__ = "leaderboard_entry"

    user_id: int  # foreign key to users table

    daily_streak: int  # current streak of dailies completed
    longest_daily_streak: int  # highest daily streak ever recorded
    average_daily_guesses: int
    average_daily_time: float  # average time to complete the daily in seconds
    longest_survival_streak: int


class Leaderboard:
    def create_user_entry(user_id: int):
        """
        Creates a new LeaderboardEntry for the given user,
        if one doesn't already exit
        """
        pass

    def update_user_entry(user_id: int):
        """
        Updates a user's leaderboard stats based on their statistics
        from StatisticsRepository
        """
        pass

    def get_entry(user_id: int) -> LeaderboardEntry:
        """
        Get a leaderboard entry by user id
        """
        pass

    def get_250_entries(position: int) -> [LeaderboardEntry]:
        """
        Get 250 leaderboard entries from the given position (from the top)
        """
        pass

    def get_friend_entries(user_id: int) -> [LeaderboardEntry]:
        """
        Get all leaderboard entries for the given user's friends only
        (including the given user)
        """
        pass
