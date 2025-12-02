import secrets
from dataclasses import dataclass
from typing import Dict


@dataclass
class LocalAuth:
    user_id: int
    token: str


class LocalAuthRepo:
    def __init__(self):
        self.tokens: Dict[int, LocalAuth] = {}

    async def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens[user_id] = LocalAuth(user_id=user_id, token=token)
        return token

    async def delete(self, user_id: int):
        if user_id in self.tokens:
            del self.tokens[user_id]

    async def get_by_id(self, user_id: int):
        return self.tokens.get(user_id)

    async def validate(self, token: str) -> bool:
        return any(auth.token == token for auth in self.tokens.values())
