"""
A minimal working example on how to use this package
"""

import asyncio

from edi_energy_scraper import EdiEnergyScraper


async def mirror():
    scraper = EdiEnergyScraper(path_to_mirror_directory="edi_energy_de")
    await scraper.mirror()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(mirror())
