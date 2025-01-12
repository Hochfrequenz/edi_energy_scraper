from datetime import date
from pathlib import Path
from typing import Callable

import pytest
from efoli import EdifactFormat
from syrupy.assertion import SnapshotAssertion

from edi_energy_scraper.apidocument import Document, ResponseModel
from edi_energy_scraper.documentmetadata import DocumentMetadata


def test_api_models() -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        actual = ResponseModel.model_validate_json(f.read())
    assert any(actual)


example_response = Path(__file__).parent / "get_documents_response_body.json"


@pytest.mark.parametrize(
    "json_file, expected_document_predicate",
    [
        pytest.param(example_response, lambda d: d.edifact_format == EdifactFormat.IFTSTA),
        pytest.param(
            example_response,
            lambda d: d.edifact_format == EdifactFormat.IFTSTA
            and d.id == 7316
            and d.file_kind == "MIG"
            and d.document_version == "2.0f"
            and d.gueltig_ab == date(2025, 6, 6),
            id="IFTSTA MIG - informatorische Lesefassung 2.0f",
        ),
    ],
)
def test_single_documents(json_file: Path, expected_document_predicate: Callable[[Document], bool]) -> None:
    with open(example_response, "r", encoding="utf-8") as f:
        documents = ResponseModel.model_validate_json(f.read()).data
    assert any(d for d in documents if expected_document_predicate(d))


@pytest.mark.snapshot
def test_api_filenames(snapshot: SnapshotAssertion) -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        documents = ResponseModel.model_validate_json(f.read())
    actual_file_names = [x.get_meaningful_file_name() for x in documents.data]
    snapshot.assert_match(actual_file_names)


def test_api_filenames_parsing() -> None:
    with open(Path(__file__).parent / "get_documents_response_body.json", "r", encoding="utf-8") as f:
        documents = ResponseModel.model_validate_json(f.read()).data
    file_names = [x.get_meaningful_file_name() for x in documents]
    parsed_file_information: list[DocumentMetadata] = [DocumentMetadata.from_filename(fn) for fn in file_names]
    assert all(isinstance(x, DocumentMetadata) for x in parsed_file_information)
    for document, rescraped in zip(documents, parsed_file_information):
        assert document.fileId == rescraped.id
        if rescraped.edifact_format:
            assert str(rescraped.edifact_format) in document.title
        assert document.gueltig_ab == rescraped.valid_from
        assert document.gueltig_bis == rescraped.valid_until
        assert document.is_extraordinary_publication == rescraped.is_extraordinary_publication
        assert document.is_error_correction == rescraped.is_error_correction
        assert document.is_consolidated_reading_version == rescraped.is_consolidated_reading_version
        assert document.is_informational_reading_version == rescraped.is_informational_reading_version
