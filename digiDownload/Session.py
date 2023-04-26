from digiDownload.AdBlockCookiePolicy import AdBlockPolicy
from digiDownload.exceptions import InvalidCredentials
from digiDownload.Book import Book

import httpx
from bs4 import BeautifulSoup

import asyncio
from http import cookiejar


class Session:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    @classmethod
    async def create(cls, email: str, password: str, remember_login: bool = False):
        client = httpx.AsyncClient(cookies=cookiejar.CookieJar(policy=AdBlockPolicy()), timeout=15)
        resp = await client.post("https://digi4school.at/br/xhr/login",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 data={"email": email, "password": password, "indefinite": int(remember_login)})

        if resp.status_code != 200 or resp.content != b"OK":
            raise InvalidCredentials(f"Login failed. Are you sure you entered the correct credentials? {resp.status_code}: {resp.reason_phrase}")

        return cls(client)

    async def get_books(self) -> list[Book]:
        resp = await self._client.get("https://digi4school.at/ebooks")
        soup = BeautifulSoup(resp.text, "html.parser")

        queue = []

        for book in soup.find("div", {"id": "shelf"}):
            queue.append(asyncio.create_task(Book.create(self._client, book)))

        for result in queue:
            result = await result
            if isinstance(result, list):
                for volume in result: yield volume
            elif result is not None: yield result

    async def redeem_code(self, code: str) -> str:
        resp = (await self._client.post("https://digi4school.at/br/xhr/einloesen",
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        data={"code": code})).json()

        if resp["err"] != 0:
            if "msg" not in resp: return "Unknown Error"
            return resp["msg"].split(':')[1][1:]

        return f"Successfully redeemed {code[:4]}-{code[4:8]}-{code[8:12]}-{code[12:16]}"
