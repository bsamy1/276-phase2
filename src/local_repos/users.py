from dataclasses import dataclass
from typing import Dict, List, Optional

import bcrypt


@dataclass
class LocalUser:
    id: int
    name: str
    email: str
    password: str
    tier: int = 1
    avatar_url: Optional[str] = None


class LocalUserRepo:
    def __init__(self):
        self.users: Dict[int, LocalUser] = {}
        self.next_id: int = 1

    async def create(
            self, 
            name: str, 
            email: str, 
            password: str, 
            tier: int = 1
        ) -> Optional[LocalUser]:
        # Check duplicates
        if any(u.name == name or u.email == email for u in self.users.values()):
            return None

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = LocalUser(id=self.next_id, name=name, email=email, password=hashed_pw, tier=tier)
        self.users[self.next_id] = user
        self.next_id += 1
        return user

    async def get_by_name(self, name: str) -> Optional[LocalUser]:
        return next((u for u in self.users.values() if u.name == name), None)

    async def get_by_id(self, id: int) -> Optional[LocalUser]:
        return self.users.get(id)

    async def update_user(self, id: int, **fields) -> Optional[LocalUser]:
        user = self.users.get(id)
        if not user:
            return None
        for k, v in fields.items():
            if k == "tier" and v < 1:
                v = 1
            setattr(user, k, v)
        return user

    async def change_password(self, id: int, curr_password: str, new_password: str) -> bool:
        user = self.users.get(id)
        if not user or not bcrypt.checkpw(curr_password.encode(), user.password.encode()):
            return False
        user.password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        return True

    async def get_all(self) -> List[LocalUser]:
        return list(self.users.values())
