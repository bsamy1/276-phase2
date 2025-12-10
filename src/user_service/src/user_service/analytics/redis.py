import os

from redis import asyncio as aioredis

AUTH_TTL_SECONDS = int(os.getenv("AUTH_TTL_SECONDS", "300"))


# Redis connection
def get_redis() -> aioredis.Redis:
    host = os.getenv("REDIS_HOST", "redis")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")

    url = os.getenv("REDIS_URL", f"redis://{host}:{port}/{db}")
    return aioredis.from_url(url, decode_responses=True)


# Activity tracking helpers
async def mark_event(user_id: int, r: aioredis.Redis):
    """
    Refreshes a user's activity timer and tracks them in the active set.
    """
    key = f"user:{user_id}:active"

    # Check if already marked active
    is_active = await r.sismember("active_users", user_id)

    # If first event since inactivity, add to active_users set
    if not is_active:
        await r.sadd("active_users", user_id)

    # Refresh their TTL in set of active_users
    await r.setex(key, AUTH_TTL_SECONDS, 1)


# Checks if user is active
async def is_active(user_id: int, r: aioredis.Redis) -> bool:
    key = f"user:{user_id}:active"
    alive = bool(await r.exists(key))
    if not alive:
        # cleanup the index so counts don’t drift
        await r.srem("active_users", str(user_id))
    return alive
