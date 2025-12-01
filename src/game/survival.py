import logging

from phase2.country import Country, get_country, get_random_country
from phase2.daily import compare_countries
from phase2.round import GuessFeedback, RoundStats
from phase2.statistics import get_statistics_repository

logger = logging.getLogger("phase2.survival")

# Survival mode configuration
STARTING_LIVES = 3
MAX_LIVES = 5


class SurvivalStats:
    """
    Extended stats class specifically for survival mode
    """
    def __init__(self):
        self.lives = STARTING_LIVES
        self.streak = 0  # Number of consecutive correct guesses
        self.current_country = None
        self.total_countries_guessed = 0
        
    def lose_life(self):
        """Decrease lives by 1"""
        self.lives = max(0, self.lives - 1)
        
    def gain_life(self):
        """Increase lives by 1, up to maximum"""
        self.lives = min(MAX_LIVES, self.lives + 1)
        
    def increment_streak(self):
        """Increment the survival streak"""
        self.streak += 1
        self.total_countries_guessed += 1
        
    def reset_streak(self):
        """Reset streak to 0 (game over)"""
        self.streak = 0
        
    def is_game_over(self) -> bool:
        """Check if the game is over (no lives left)"""
        return self.lives <= 0


def survival_mode():
    """
    Run the core gameplay loop, as well
    as any survival-specific features
    (lives count + stats, generating new country)
    """
    survival_stats = SurvivalStats()
    round_stats = RoundStats(mode="survival")
    
    # Generate the first country
    current_country = get_random_country()
    survival_stats.current_country = current_country
    
    logger.info(f"Survival mode started with {STARTING_LIVES} lives")
    
    return survival_stats, round_stats


async def handle_survival_guess(input: str, round_stats: RoundStats, survival_stats: SurvivalStats):
    """
    Handle a guess in survival mode. Similar to daily mode but with lives system
    and continuous country generation.
    
    Args:
        input: The country name guessed by the user
        round_stats: The current round statistics
        survival_stats: The survival-specific statistics
    """
    country = get_country(input)
    
    if country is None:
        logger.warning(f"Invalid country guess: {input}")
        round_stats.guess_error.emit()
        return
    
    # Start the round if it isn't started already
    if not round_stats.start_time:
        round_stats.start_round()
    
    # Error handling in case the countryinfo API isn't able to serve info we need
    try:
        feedback: GuessFeedback = compare_countries(country, survival_stats.current_country)
    except AttributeError:
        logger.error("Error comparing countries")
        round_stats.guess_error.emit()
        return
    
    round_stats.guessed_names.append(country.name)
    round_stats.guesses += 1
    
    if feedback.name:  # Correct guess
        await handle_correct_guess(round_stats, survival_stats)
    elif round_stats.guesses >= round_stats.max_guesses:  # Out of guesses for this country
        await handle_incorrect_guess(round_stats, survival_stats)
    
    round_stats.guess_graded.emit(country, feedback)


async def handle_correct_guess(round_stats: RoundStats, survival_stats: SurvivalStats):
    """
    Handle a correct guess in survival mode:
    - Increment streak
    - Award bonus life every 5 correct guesses
    - Generate new country
    - Reset guess counter
    """
    survival_stats.increment_streak()
    
    # Award bonus life every 5 correct guesses
    if survival_stats.streak % 5 == 0:
        survival_stats.gain_life()
        logger.info(f"Bonus life awarded! Lives: {survival_stats.lives}")
    
    # Generate new country for next round
    survival_stats.current_country = get_random_country()
    
    # Reset guesses for the new country
    round_stats.guesses = 0
    round_stats.guessed_names = []
    
    logger.info(f"Correct guess! Streak: {survival_stats.streak}, Lives: {survival_stats.lives}")


async def handle_incorrect_guess(round_stats: RoundStats, survival_stats: SurvivalStats):
    """
    Handle running out of guesses in survival mode:
    - Lose a life
    - Check if game is over
    - If not over, generate new country and continue
    """
    survival_stats.lose_life()
    
    logger.info(f"Out of guesses. Lives remaining: {survival_stats.lives}")
    
    if survival_stats.is_game_over():
        await end_survival_game(round_stats, survival_stats)
    else:
        # Generate new country and continue
        survival_stats.current_country = get_random_country()
        round_stats.guesses = 0
        round_stats.guessed_names = []


async def end_survival_game(round_stats: RoundStats, survival_stats: SurvivalStats):
    """
    End the survival game and process final statistics
    """
    stats_repo = get_statistics_repository()
    
    round_stats.end_round()
    round_stats.won = False  # Survival mode always ends in "loss"
    
    logger.info(f"Survival game ended. Final streak: {survival_stats.streak}")
    logger.info("Round stats:")
    logger.info(vars(round_stats))
    
    # TODO (milestone 2): Get the user id of the currently playing user, if there is one
    round_stats.user_id = 0
    
    # Add round to the rounds database with survival streak
    await stats_repo.add_round(round_stats, survival_streak=survival_stats.streak)
    
    # Emit game ended event with final stats
    round_stats.game_ended.emit(False)
    
    survival_stats.reset_streak()