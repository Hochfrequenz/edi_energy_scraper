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


async def test_download_file(tmp_path: Path) -> None:
    test_folder = tmp_path / "test"
    client = EdiEnergyScraper("https://bdew-mako.inv", test_folder)
    example_document = Document.model_validate_json(
        """
    {
      "userId": 0,
      "id": 6288,
      "fileId": 8545,
      "title": "Acknowledgement 1.0a - konsolidierte Lesefassung mit Fehlerkorrekturen Stand: 03.03.2015",
      "version": null,
      "topicId": 157,
      "topicGroupId": 23,
      "isFree": true,
      "publicationDate": null,
      "validFrom": "2024-10-23T00:00:00",
      "validTo": "2024-10-23T00:00:00",
      "isConsolidatedReadingVersion": false,
      "isExtraordinaryPublication": false,
      "isErrorCorrection": false,
      "correctionDate": null,
      "isInformationalReadingVersion": false,
      "fileType": "application/pdf",
      "topicGroupSortNr": 7,
      "topicSortNr": 1
    }
    """
    )
    with open(Path(__file__).parent / "example_file.pdf", "rb") as example_pdf:
        with aioresponses() as mocked_tmds:
            mocked_get_url = f"https://bdew-mako.inv/api/downloadFile/8545"
            mocked_tmds.get(
                mocked_get_url,
                status=200,
                body=example_pdf.read(),
            )
            actual = await client.download_document(example_document)
    assert actual.is_file()
    assert actual.suffix == ".pdf"


async def test_cleanup(tmp_path: Path) -> None:  # test is async to avoid RuntimeError: no running event loop
    test_folder = tmp_path / "test"
    test_folder.mkdir()
    a_directory = test_folder / "adir"
    a_directory.mkdir()
    outdated_file_path = test_folder / "foo_123.pdf"
    outdated_file_path.touch()
    recent_file_path = test_folder / "foo_456.docx"
    recent_file_path.touch()
    recent_file_path2 = test_folder / "foo_bar_xyzadsiadakdslaskmd_1.4a_789.docx"
    recent_file_path2.touch()
    client = EdiEnergyScraper("https://bdew-mako.inv", test_folder)
    client._remove_old_files([Document.model_construct(fileId=456), Document.model_construct(fileId=789)])
    assert not outdated_file_path.exists()
    assert recent_file_path.exists()
    assert recent_file_path2.exists()
