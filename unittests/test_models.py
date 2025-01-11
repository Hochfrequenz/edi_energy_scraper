from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from edi_energy_scraper.apidocument import ResponseModel
from edi_energy_scraper.documentmetadata import DocumentMetadata


def test_api_models() -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        actual = ResponseModel.model_validate_json(f.read())
    assert any(actual)


@pytest.mark.snapshot
def test_api_filenames(snapshot: SnapshotAssertion) -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        documents = ResponseModel.model_validate_json(f.read())
    actual_file_names = [x.get_meaningful_file_name() for x in documents.data]
    snapshot.assert_match(actual_file_names)


def test_api_filenames_parsing() -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        documents = ResponseModel.model_validate_json(f.read())
    file_names = [x.get_meaningful_file_name() for x in documents.data]
    parsed_file_information = [DocumentMetadata.from_filename(fn) for fn in file_names]
    assert all(isinstance(x, DocumentMetadata) for x in parsed_file_information)
