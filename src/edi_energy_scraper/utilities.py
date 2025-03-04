"""
helper functions
"""

from datetime import date
from pathlib import Path

from efoli import EdifactFormatVersion, get_edifact_format_version
from pypdf import PdfReader


def _have_different_metadata(path_new_file: Path, path_to_old_file: Path) -> bool:
    """
    Compares the metadata of two pdf files.
    :return: bool, if metadata of the two pdf files are different or if at least one of the files is encrypted.
    """
    pdf_new = PdfReader(path_new_file)
    if pdf_new.is_encrypted:
        return True
    pdf_new_metadata = pdf_new.metadata

    with open(path_to_old_file, "rb") as file_old:
        pdf_old = PdfReader(file_old)
        if pdf_old.is_encrypted:
            return True
        pdf_old_metadata = pdf_old.metadata

    metadata_has_changed: bool = pdf_new_metadata != pdf_old_metadata

    return metadata_has_changed


def _get_valid_format_versions(valid_from: date, valid_to: date | None) -> list[EdifactFormatVersion]:
    """
    Returns a list of EdifactFormatVersions that are valid between the given dates.
    """
    valid_from_fv = get_edifact_format_version(valid_from)
    valid_to_fv = (
        max(EdifactFormatVersion)
        if valid_to is None
        else get_edifact_format_version(valid_from) if valid_to <= valid_from else get_edifact_format_version(valid_to)
    )
    return [
        format_version
        for format_version in EdifactFormatVersion
        if format_version >= valid_from_fv and format_version <= valid_to_fv
    ]


__all__ = ["_have_different_metadata", "_get_valid_format_versions"]
