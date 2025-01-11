"""
A minimal working example on how to use this package
"""

import asyncio
from pathlib import Path

from edi_energy_scraper.scraper import EdiEnergyScraper

my_target_dir = Path(__file__).parent / "foo"


async def mirror():
    scraper = EdiEnergyScraper(path_to_mirror_directory=my_target_dir)
    await scraper.mirror()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(mirror())
