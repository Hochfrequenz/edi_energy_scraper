from pathlib import Path

from edi_energy_scraper.utilities import _have_different_metadata


def test_have_different_metadata() -> None:
    """Tests the function _have_different_metadata."""
    test_file = Path(__file__).parent / "example_ahb.pdf"
    same_pdf = Path(__file__).parent / "example_ahb_2.pdf"
    assert _have_different_metadata(test_file, same_pdf)
    assert not _have_different_metadata(test_file, test_file)
