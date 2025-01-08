import json
from pathlib import Path

from aioresponses import aioresponses

from edi_energy_scraper.apidocument import Document
from edi_energy_scraper.scraper import EdiEnergyScraper


async def test_download_overview() -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        response_body = json.loads(f.read())
    client = EdiEnergyScraper("https://bdew-mako.inv")
    with aioresponses() as mocked_tmds:
        mocked_get_url = f"https://bdew-mako.inv/api/documents"
        mocked_tmds.get(
            mocked_get_url,
            status=200,
            payload=response_body,
        )
        actual = await client.get_documents_overview()
    assert any(actual)
    assert all(isinstance(x, Document) for x in actual)
