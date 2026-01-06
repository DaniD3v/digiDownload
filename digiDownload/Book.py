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
from asyncio import Semaphore


def _increment_page(page: str or int):
    return page+1 if isinstance(page, int) else page


def get_digi4school_url(book_id: str, extra: str):
    return lambda page, ending, _=False: f"https://a.digi4school.at/ebook/{book_id}/{extra}{_increment_page(page)}{ending}"


def get_hpthek_url(book_id: str, extra: str):
    return lambda page, ending, add_second_page=True: f"https://a.hpthek.at/ebook/{book_id}/{_increment_page(page)}{'/' if page != '' else ''}{extra}{_increment_page(page) if add_second_page else ''}{ending}"


class Book:
    urls = {
        "a.digi4school.at": get_digi4school_url,
        "a.hpthek.at": get_hpthek_url
    }

    def __init__(self, client: AsyncClient):
        self._client = client

        self.publisher = None
        self.title = None

        self._code = None
        self._id = None
        self._content_id = None

        self._url = None
        self._pages = None

    @classmethod
    async def create(cls, client: AsyncClient, data: dict) -> "Book" or list["Book"] or None:
        self = cls(client)

        self.publisher = data.get('publisher')
        self.title = data.get('title')

        self._code = data.get('code')
        self._id = data.get('id')

        resp = LTIForm((await client.get(f"https://digi4school.at/ebook/{self._code}")).text)
        first_form = LTIForm((await resp.send(client)).text)
        second_form = (await first_form.send(client))

        self._content_id = first_form["resource_link_id"]

        try: self._url = Book.urls[second_form.url.host](self._content_id, "")
        except KeyError: print(f"Undocumented url: {second_form.url.host} (Book: {self.title})\nPlease open a Github issue with this url and the book title."); return None

        main_page = (await client.get(self._url("", ""))).text
        if main_page.split('\n')[0] == "<html>":  # checks if there are multiple volumes
            soup = BeautifulSoup(main_page, "html.parser")
            extra = '/'.join(soup.find("a")["href"].split("/")[:-1]) + '/'
            self._url = Book.urls[second_form.url.host](self._content_id, extra)
            main_page = (await client.get(self._url("", ""))).text

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

        img_sem = Semaphore(5)

        async def fetch_image(img_tag):
            url_ending = img_tag["xlink:href"]
            if url_ending.count('/') == 2: url_ending = '/'.join(url_ending.split('/')[1:])

            url = self._url(page, '/' + url_ending, False)

            async with img_sem:
                resp = await self._client.get(url, headers={"Content-Type": "image/avif,image/webp,*/*"}, timeout=60.0)
                return img_tag, resp

        for image in images:
            queue.append(asyncio.create_task(fetch_image(image)))

        for task in queue:
            try:
                image_tag, response = await task
                if response.headers["Content-Type"].startswith("image/"): yield image_tag, response
            except Exception as e:
                print(f"Warning: Image download failed: {e}")

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
            print(f"Couldn't render page {page} of {self.title}. (Book: {self.title})\nPlease open a Github issue with the book title.")
            canvas = Canvas(buffer)
            canvas.save()

        return buffer

    async def get_pdf(self, show_progress: bool = False) -> BytesIO:
        merger = PdfMerger()
        queue = []

        page_sem = Semaphore(5)

        async def fetch_page_safe(p):
            async with page_sem:
                return await self.get_page_pdf(p)

        async def progress_updater():
            while True:
                finished = sum(1 for t in queue if t.done())
                total = len(queue) if len(queue) > 0 else 1

                print(f"Downloading {self.title}: {finished / total * 100:.2f}% ({finished}/{total})", end='\r')
                if finished == total and total > 0: break
                await asyncio.sleep(1)

        for page in range(self._pages):
            queue.append(asyncio.create_task(fetch_page_safe(page)))

        if show_progress: asyncio.create_task(progress_updater())

        for resp in queue:
            result = await resp
            if result is not None: merger.append(result)

        buffer = BytesIO()
        merger.write(buffer)
        return buffer