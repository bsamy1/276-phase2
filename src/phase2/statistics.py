from datetime import date


class RoundStatistics:
    __tablename__ = "round_statistics"

    id: int
    user_id: int  # (foreign key to users table)
    time_to_complete: int  # seconds it took to finish the round
    won: bool
    guesses: int  # number of guesses made
    mode: str  # survival or daily

    daily_date: date  # the day this daily took place

    survival_streak: int  # number of survival rounds completed


class RoundStatisticsRepository:
    def add_round():
        """
        Receives statistics for a round from the game and
        updates the user's stats table accordingly
        """

    def get_daily_round(day: date) -> RoundStatistics:
        """
        Get a daily round's stats by the date
        """
