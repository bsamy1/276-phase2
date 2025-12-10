import httpx  # HTTP requests


class FriendsAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base = base_url                      # store backend URL


    # send friend request
    async def create_request(self, sender_id: int, receiver_id: int, jwt: str):

        body = {                                  # backend requires this structure
            "requestor": sender_id,               # who is sending
            "requestee": receiver_id,             # who receives
            "auth": {                             # auth model for the request
                "user_id": sender_id,
                "jwt": jwt,
            },
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base}/v2/users/{receiver_id}/friend-requests/",
                json=body
            )
            return r.json()                       


    # list incoming friend requests
    async def incoming(self, user_id: int):
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base}/v2/users/{user_id}/friend-requests/?q=incoming"
            )
            return r.json()["requests"]        


    # accept friend requests
    async def accept(self, user_id: int, other_id: int, jwt: str):

        body = {                                  # required: decision + auth
            "decision": "accept",
            "auth": {
                "user_id": user_id,
                "jwt": jwt,
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{self.base}/v2/users/{user_id}/friend-requests/{other_id}",
                json=body
            )
            return r.json()

    # Delete friend request
    async def reject(self, user_id: int, other_id: int, jwt: str):

        body = {
            "decision": "reject",
            "auth": {
                "user_id": user_id,
                "jwt": jwt,
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{self.base}/v2/users/{user_id}/friend-requests/{other_id}",
                json=body
            )
            return r.json()

    # Reject friend request
    async def reject(self, user_id: int, other_id: int, jwt: str):

        body = {
            "decision": "reject",
            "auth": {
                "user_id": user_id,
                "jwt": jwt,
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{self.base}/v2/users/{user_id}/friend-requests/{other_id}",
                json=body
            )
            return r.json()


    
    async def list_friends(self, user_id: int):
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base}/v2/users/{user_id}/friends/")
            return r.json()["friends"]            # list of friend user objects


    async def delete_friend(self, user_id: int, friend_id: int, jwt: str):

        body = {                                
            "auth": {
                "user_id": user_id,
                "jwt": jwt,
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{self.base}/v2/users/{user_id}/friends/id/{friend_id}",
                json=body
            )
            return r.json()
