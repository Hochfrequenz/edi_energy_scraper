"""
A minimal working example on how to use this package
"""

import asyncio
from pathlib import Path

from edi_energy_scraper.scraper import EdiEnergyScraper


async def mirror():
    scraper = EdiEnergyScraper(path_to_mirror_directory=Path(__file__).parent / "foo")
    await scraper.mirror()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(mirror())
