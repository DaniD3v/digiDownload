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

    async def get_books(self):
        response = await self._client.get("https://digi4school.at/br/xhr/v2/synch")

        if response.status_code != 200:
            return

        data = response.json()
        book_list = data.get('books', [])

        tasks = []
        for book_data in book_list:
            print(f"Found: {book_data.get('title')}")
            tasks.append(Book.create(self._client, book_data))

        books = await asyncio.gather(*tasks)

        for book in books:
            if book:
                yield book

    async def redeem_code(self, code: str) -> str:
        resp = (await self._client.post("https://digi4school.at/br/xhr/einloesen",
                                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                                        data={"code": code})).json()

        if resp["err"] != 0:
            if "msg" not in resp: return "Unknown Error"
            return resp["msg"].split(':')[1][1:]

        return f"Successfully redeemed {code[:4]}-{code[4:8]}-{code[8:12]}-{code[12:16]}"
