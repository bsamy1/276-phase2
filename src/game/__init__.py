from fastapi import Depends
from shared.database import get_db
from sqlalchemy.orm import Session
from user_service.models import auth, friends, session_analytics, user

from phase2 import leaderboard, statistics

repos = {}


def init_repos(db: Session = Depends(get_db)):
    global repos

    repos["user_repo"] = user.get_user_repository(db)
    repos["friendship_repo"] = friends.get_friendship_repository(db)
    repos["auth_repo"] = auth.get_auth_repository(db)
    repos["analytics_repo"] = session_analytics.get_session_analytics_repository(db)
    repos["stats_repo"] = statistics.get_statistics_repository(db)
    repos["leaderboard_repo"] = leaderboard.get_leaderboard_repository(db, repos["stats_repo"])
