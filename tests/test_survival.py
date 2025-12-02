

from unittest.mock import patch

from game.survival import STARTING_LIVES, SurvivalStats, survival_mode
from phase2.round import RoundStats


class TestSurvivalMode:
    @patch("game.survival.get_random_country")
    def test_survival_mode(self, mock_get_random):
        """Test that survival_mode initializes correctly"""
        mock_country = mock_get_random.return_value
        
        survival_stats, round_stats = survival_mode()
        
        # Check survival_stats
        assert isinstance(survival_stats, SurvivalStats)
        assert survival_stats.lives == STARTING_LIVES
        assert survival_stats.streak == 0
        assert survival_stats.total_countries_guessed == 0
        assert survival_stats.current_country == mock_country
        
        # Check round_stats
        assert isinstance(round_stats, RoundStats)
        assert round_stats.mode == "survival"
        
        # Verify get_random_country was called
        mock_get_random.assert_called_once()