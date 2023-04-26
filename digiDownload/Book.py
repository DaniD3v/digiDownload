from digiDownload.LTIParser import LTIForm

from httpx import AsyncClient, Response
from bs4 import BeautifulSoup
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.pdfgen.canvas import Canvas
from PyPDF2 import PdfMerger
from io import BytesIO

from base64 import encodebytes
import asyncio


def _increment_page(page: str or int):
    return page+1 if isinstance(page, int) else page


def get_digi4school_url(book_id: str, extra: str):
    return lambda page, ending: f"https://a.digi4school.at/ebook/{book_id}/{extra}{_increment_page(page)}{ending}"


def get_hpthek_url(book_id: str, extra: str):
    return lambda page, ending: f"https://a.hpthek.at/ebook/{book_id}/{_increment_page(page)}{'/' if page != '' else ''}{extra}{_increment_page(page)}{ending}"


class Book:
    urls = {
        "a.digi4school.at": get_digi4school_url,
        "a.hpthek.at": get_hpthek_url
    }

    def __init__(self, client: AsyncClient):
        self._client = client

        self.publisher = None
        self.title = None
        self.cover = None

        self._code = None
        self._id = None
        self._content_id = None

        self._url = None
        self._pages = None

    @classmethod
    async def create(cls, client: AsyncClient, html: BeautifulSoup) -> "Book" or list["Book"] or None:
        self = cls(client)

        self.publisher = html.find("span", {"class": "publisher"}).text
        self.title = html.find("h1").text
        self.cover = html.find("img")["src"]

        self._code = html["data-code"]
        self._id = html["data-id"]

        resp = LTIForm((await client.get(f"https://digi4school.at/ebook/{self._code}")).text)
        first_form = LTIForm((await resp.send(client)).text)
        second_form = (await first_form.send(client))

        self._content_id = first_form["resource_link_id"]

        try: self._url = Book.urls[second_form.url.host](self._content_id, "")
        except KeyError: print(f"Undocumented url: {second_form.url.host} (Book: {self.title})\nPlease open a Github issue with this url and the book title."); return None

        main_page = (await client.get(self._url("", ""))).text  # don't remove the / at the end of the url
        if main_page.split('\n')[0] == "<html>":  # checks if there are multiple volumes
            soup = BeautifulSoup(main_page, "html.parser")
            extra = '/'.join(soup.find("a")["href"].split("/")[:-1]) + '/'

            self._url = Book.urls[second_form.url.host](self._content_id, extra)
            main_page = (await client.get(self._url("", ""))).text

            # TODO actually make multiple volumes work instead of simply taking the first one

        soup = BeautifulSoup(main_page, "html.parser").find("meta", {"name": "pageLabels"})
        if soup is not None: self._pages = soup['content'].count(',')
        else:
            pos = main_page.find("IDRViewer.makeNavBar(")
            if pos == -1: print(f"Couldn't find the page count. (Book: {self.title})\nPlease open a Github issue with the book title."); return None
            self._pages = int(main_page[pos:].split('(')[1].split(',')[0])

        return self

    async def _get_page(self, page: int) -> Response:
        return await self._client.get(self._url(page, ".svg"))

    async def _get_images(self, page: int, svg: BeautifulSoup) -> [tuple[BeautifulSoup, Response], None, None]:
        queue = []
        images = svg.find_all("image")

        for image in images:
            url_ending = image["xlink:href"]
            if url_ending.count('/') == 2: url_ending = '/'.join(url_ending.split('/')[1:])

            url = self._url(page, '/' + url_ending)
            queue.append(asyncio.create_task(self._client.get(url, headers={"Content-Type": "image/avif,image/webp,*/*"})))

        for resp in queue:
            image = images[queue.index(resp)]
            resp = await resp
            if resp.headers["Content-Type"].startswith("image/"): yield image, resp

    async def get_page_svg(self, page: int) -> str:
        soup = BeautifulSoup((await self._get_page(page)).text, "xml")

        async for image, resp in self._get_images(page, soup):
            image["xlink:href"] = f"data:{resp.headers['Content-Type']};base64,{encodebytes(resp.content).decode('utf-8')}"

        return str(soup)

    async def get_page_pdf(self, page: int) -> BytesIO or None:
        svg = await self.get_page_svg(page)

        buffer = BytesIO()
        try:
            rlg = svg2rlg(BytesIO(svg.encode("utf-8")))
            renderPDF.drawToFile(rlg, buffer)

        except AttributeError:
            canvas = Canvas(buffer)
            canvas.save()

        return buffer

    async def get_pdf(self, show_progress: bool = False) -> BytesIO:
        merger = PdfMerger()
        queue = []

        async def progress_updater():
            while True:
                finished = 0
                for task in queue: finished += 1 if task.done() else 0

                print(f"Downloading {self.title}: {finished/(self._pages+1)*100:.2f}% ({finished}/{self._pages+1})", end='\r')
                if finished == self._pages: break
                await asyncio.sleep(1)

        if show_progress: asyncio.create_task(progress_updater())

        for page in range(self._pages): queue.append(asyncio.create_task(self.get_page_pdf(page)))
        for resp in queue:
            result = await resp
            if result is not None: merger.append(result)

        buffer = BytesIO()
        merger.write(buffer)
        return buffer
