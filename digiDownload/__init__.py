
if __name__ == "__main__":
    from digiDownload.cli_tool import run
    from asyncio import run as run_async
    run_async(run())
    exit(0)

import digiDownload.Session
import digiDownload.exceptions
