"""
helper functions
"""

from pathlib import Path

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
