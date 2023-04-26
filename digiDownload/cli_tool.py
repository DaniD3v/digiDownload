from digiDownload.Session import Session

import os
from getpass import getpass


async def run():
    try: session = await Session.create(os.environ["email"], os.environ["password"])
    except KeyError: session = await Session.create(input("EMail: "), getpass("Password: "))
    books = [(b, False) async for b in session.get_books()]

    path = f"{os.getcwd()}"
    if not os.path.exists(path): os.mkdir(path)

    def menu(books: list) -> bool:  # False -> continue, True -> finish
        print("\nSelect the books you want to download:")
        for i, (b, s) in enumerate(books): print(f"{i + 1}: [{'x' if s else ' '}] {b.title}")
        print("R: Register new book.")
        print("F: Finish selection.")
        print("Q: Exit")

        selection = input(": ")
        if selection.isnumeric():
            selection = int(selection) - 1

            try: books[selection] = (books[selection][0], not books[selection][1])
            except IndexError: return False

        else:
            match selection.lower():
                case 'r':
                    err = session.redeem_code(input("code: "))
                    if err is not None: print(err)
                    # noinspection PyUnusedLocal
                    books = [(b, False) for b in session.get_books()]
                case 'f': return True
                case 'q': exit(0)

        return False

    while not menu(books): pass

    for book in [b for b, s in books if s]:
        book_content = (await book.get_pdf(True)).getbuffer().tobytes()

        with open(os.path.join(path, f"{book.title.replace('/', '')}.pdf"), "w+b") as f:
            f.write(book_content)

        print(f"\nDownloaded {book.title}")
