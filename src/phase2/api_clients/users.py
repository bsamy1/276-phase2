import httpx

class UserAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def create(self, name: str, email: str, password: str):
        payload = {
            "name": name,
            "email": email,
            "password": password
        }

        r = await self.client.post("/v2/users/", json=payload)
        return r

    async def get_by_name(self, username: str):
        r = await self.client.get(f"/v2/users/name/{username}")
        if r.status_code == 404:
            return None
        return r.json()["user"]

    async def get_by_id(self, user_id: int):
        r = await self.client.get(f"/v2/users/id/{user_id}")
        if r.status_code == 404:
            return None
        return r.json()["user"]
