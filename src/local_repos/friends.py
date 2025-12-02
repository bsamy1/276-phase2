# phase2/local_repos/friends.py
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LocalFriendRequest:
    id: int
    requestor_id: int
    requestee_id: int
    status: str = "pending"

# revolves around friend requests
# doesnt actually store friends, just lists friend requests that have been accepted
class LocalFriendsRepo:
    def __init__(self, user_repo):
        self.user_repo = user_repo
        self.requests: List[LocalFriendRequest] = []
        self.next_id: int = 1

    async def send_request(
            self, 
            requestor_id: int, 
            requestee_id: int, 
        ) -> Optional[LocalFriendRequest]:
        # Prevent duplicates
        if any(
            (r.requestor_id == requestor_id and r.requestee_id == requestee_id)
            or (r.requestor_id == requestee_id and r.requestee_id == requestor_id)
            for r in self.requests
        ):
            return None

        fr = LocalFriendRequest(
            id=self.next_id, 
            requestor_id=requestor_id, 
            requestee_id=requestee_id, 
        )
        self.requests.append(fr)
        self.next_id += 1
        return fr

    async def accept_request(self, request_id: int):
        fr = next((r for r in self.requests if r.id == request_id), None)
        if fr:
            fr.status = "accepted"

    async def reject_request(self, request_id: int) -> bool:
        fr = next((r for r in self.requests if r.id == request_id), None)
        if fr and fr.status == "pending":
            self.requests.remove(fr)
            return True
        return False

    async def get_requests(self, user_id: int):
        return [r for r in self.requests if r.requestee_id == user_id and r.status == "pending"]

    async def get_unanswered_requests(self, user_id: int):
        return [r for r in self.requests if r.requestor_id == user_id and r.status == "pending"]

    async def list_friends(self, user_id: int):
        friends = []
        for r in self.requests:
            if r.status == "accepted":
                if r.requestor_id == user_id:
                    friend = await self.user_repo.get_by_id(r.requestee_id)
                    if friend:
                        friends.append(friend)
                elif r.requestee_id == user_id:
                    friend = await self.user_repo.get_by_id(r.requestor_id)
                    if friend:
                        friends.append(friend)
        return friends

    async def delete_friendship(self, user_id: int, friend_id: int):
        fr = next(
            (r for r in self.requests if r.status == "accepted" and
             ((r.requestor_id == user_id and r.requestee_id == friend_id) or
              (r.requestor_id == friend_id and r.requestee_id == user_id))),
            None
        )
        if fr:
            self.requests.remove(fr)
            return True
        return False