import json
from pathlib import Path

import pytest
from aioresponses import aioresponses
from efoli import EdifactFormatVersion
from more_itertools import last

from edi_energy_scraper import DocumentMetadata
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
            actual = await client.download_document_per_fv(example_document)
    assert actual.is_file()
    assert actual.suffix == ".pdf"


async def test_cleanup(tmp_path: Path) -> None:  # test is async to avoid RuntimeError: no running event loop
    test_folder = tmp_path / "test"
    test_folder.mkdir()
    a_directory = test_folder / "adir"
    a_directory.mkdir()
    outdated_file_path = test_folder / "MIG_IFTSTA_2.0e_20231001_20250605_20231001_ooox_9321.docx"
    outdated_file_path.touch()
    recent_file_path = test_folder / "MIG_IFTSTA_2.0e_20240311_20250605_20240311_oxoo_9318.pdf"
    recent_file_path.touch()
    recent_file_path_with_different_name = test_folder / "MIG_ORDERS_2.0e_20240311_20250605_20240311_oxoo_9318.pdf"
    recent_file_path_with_different_name.touch()
    # note that recent_file_path_with_different_name has the same ID but a different name
    recent_file_path2 = test_folder / "MIG_IFTSTA_2.0e_20240311_20250605_20240311_oxox_9323.docx"
    recent_file_path2.touch()
    document_9318 = Document.model_validate(
        {
            "userId": 0,
            "id": 7442,
            "fileId": 9318,
            "title": "IFTSTA MIG 2.0e -  außerordentliche Veröffentlichung ",
            "version": None,
            "topicId": 116,
            "topicGroupId": 17,
            "isFree": True,
            "publicationDate": None,
            "validFrom": "2024-03-11",
            "validTo": "2025-06-05",
            "isConsolidatedReadingVersion": False,
            "isExtraordinaryPublication": False,
            "isErrorCorrection": False,
            "correctionDate": None,
            "isInformationalReadingVersion": False,
            "fileType": "application/pdf",
            "topicGroupSortNr": 1,
            "topicSortNr": 1,
        }
    )
    document_9323 = Document.model_validate(
        {
            "userId": 0,
            "id": 7443,
            "fileId": 9323,
            "title": "IFTSTA MIG - informatorische Lesefassung 2.0e -  außerordentliche Veröffentlichung ",
            "version": None,
            "topicId": 116,
            "topicGroupId": 17,
            "isFree": True,
            "publicationDate": None,
            "validFrom": "2024-03-11",
            "validTo": "2025-06-05",
            "isConsolidatedReadingVersion": False,
            "isExtraordinaryPublication": False,
            "isErrorCorrection": False,
            "correctionDate": None,
            "isInformationalReadingVersion": False,
            "fileType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "topicGroupSortNr": 1,
            "topicSortNr": 1,
        }
    )
    client = EdiEnergyScraper("https://bdew-mako.inv", test_folder)
    client._remove_old_files([document_9318, document_9323])
    assert not outdated_file_path.exists()
    assert not recent_file_path_with_different_name.exists()
    assert recent_file_path.exists()
    assert recent_file_path2.exists()
    assert a_directory.exists()


@pytest.mark.parametrize("with_own_path", [True, False])
async def test_best_match(tmp_path: Path, with_own_path: bool) -> None:
    test_folder = tmp_path / "test"
    test_folder.mkdir()
    path123 = test_folder / "foo_123.pdf"
    path456 = test_folder / "foo_456.docx"
    path789 = test_folder / "foo_bar_xyzadsiadakdslaskmd_1.4a_789.docx"
    client = EdiEnergyScraper("https://bdew-mako.inv", test_folder)

    async def get_fake_documents() -> list[Document]:
        return [
            Document.model_construct(fileId=123),
            Document.model_construct(fileId=456),
            Document.model_construct(fileId=789),
        ]

    async def download_fake_document(document: Document, format_version: EdifactFormatVersion | None = None) -> Path:
        if document.fileId == 123:
            path123.touch()
            return path123
        if document.fileId == 456:
            path456.touch()
            return path456
        if document.fileId == 789:
            path789.touch()
            return path789
        raise NotImplementedError()

    client.get_documents_overview = get_fake_documents  # type:ignore[method-assign]
    client.download_document_per_fv = download_fake_document  # type:ignore[method-assign]
    if with_own_path:
        own_path = tmp_path / "my_document"
        actual = await client.get_best_match(lambda ds: last(sorted(ds, key=lambda d: d.fileId)), own_path)
        assert actual == own_path
        assert actual.exists()
        assert not path123.exists() and not path456.exists() and not path789.exists()
    else:
        actual = await client.get_best_match(lambda ds: last(sorted(ds, key=lambda d: d.fileId)))
        assert actual is not None and actual.exists() and actual.is_file()
        assert actual == path789
        assert not path123.exists() and not path456.exists() and path789.exists()
