from datetime import date
from pathlib import Path

import pytest
from efoli import EdifactFormatVersion

from edi_energy_scraper import DocumentMetadata
from edi_energy_scraper.utilities import _get_valid_format_versions, _have_different_metadata


def test_have_different_metadata() -> None:
    """Tests the function _have_different_metadata."""
    test_file = Path(__file__).parent / "example_ahb.pdf"
    same_pdf = Path(__file__).parent / "example_ahb_2.pdf"
    assert _have_different_metadata(test_file, same_pdf)
    assert not _have_different_metadata(test_file, test_file)


def test_extraction() -> None:
    structured_information = DocumentMetadata.from_filename("MIG_REQOTE_1.3_20250604_20230930_20230930_oxox_10071.docx")
    print(structured_information)


@pytest.mark.parametrize(
    "valid_from, valid_to, expected_versions",
    [
        pytest.param(
            date(2023, 10, 30),
            None,
            [
                edifact_format_version
                for edifact_format_version in EdifactFormatVersion
                if edifact_format_version >= EdifactFormatVersion.FV2310
            ],
        ),
        pytest.param(date(2021, 9, 30), date(2021, 9, 29), [EdifactFormatVersion.FV2104]),
        pytest.param(date(2021, 9, 30), date(2021, 9, 30), [EdifactFormatVersion.FV2104]),
        pytest.param(date(2021, 9, 30), date(2021, 10, 1), [EdifactFormatVersion.FV2104], id="exclusive valid_to"),
        pytest.param(date(2023, 9, 30), date(2024, 4, 1), [EdifactFormatVersion.FV2304, EdifactFormatVersion.FV2310]),
        pytest.param(date(2023, 4, 1), date(2023, 4, 1), [EdifactFormatVersion.FV2304]),
    ],
)
def test_get_formatversions(valid_from: date, valid_to: date, expected_versions: list[EdifactFormatVersion]) -> None:
    """Tests the function _get_valid_format_versions."""
    assert _get_valid_format_versions(valid_from, valid_to) == expected_versions
