from digiDownload.exceptions import NotAnLtiLaunchForm

from httpx import AsyncClient, Response
from bs4 import BeautifulSoup


class LTIForm:
    def __init__(self, content: str):
        soup = BeautifulSoup(content, "html.parser")

        if soup.form["name"] != "ltiLaunchForm": raise NotAnLtiLaunchForm("Not a lti launch form.")

        self.url = soup.form["action"]
        self.method = soup.form["method"]
        self.content_type = soup.form["enctype"]

        self.data = {s['name']: s['value'] for s in soup.find_all("input")}

    def __getitem__(self, item: str) -> str:
        return self.data[item]

    async def send(self, client: AsyncClient) -> Response:
        return await client.request(self.method, self.url, headers={"Content-Type": self.content_type}, data=self.data)
