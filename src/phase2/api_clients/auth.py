from datetime import datetime, timedelta  # for expiry calculation

import httpx  # HTTP requests


class AuthAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base = base_url                        # backend base URL


    # LOGIN (returns JWT)
    async def login(self, user_id: int, password: str):
        expiry = (datetime.utc() + timedelta(minutes=45))     # expiry timestamp

        expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")        # format required by API

        body = {                                                 # login body
            "id": user_id,
            "password": password,
            "expiry": expiry_str,
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base}/v2/authentications", json=body)
            if r.status_code != 200:                            
                return None
            return r.json()["jwt"]                              # return token


    # LOGOUT (delete JWT)
    async def logout(self, jwt: str):
        async with httpx.AsyncClient() as client:
            await client.delete(f"{self.base}/v2/authentications", json={"jwt": jwt})
