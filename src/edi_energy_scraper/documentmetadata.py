"""utility to derive structured information from a filename"""

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from efoli import EdifactFormat
from pydantic import BaseModel, StringConstraints

from .apidocument import _FileKind

_filename_pattern = re.compile("")

_logger = logging.getLogger(__name__)


class DocumentMetadata(BaseModel):
    """
    hochfrequenz internal metadata about a file downloaded by the edi-energy/bdew-mako scraper
    """

    kind: _FileKind | None
    edifact_format: EdifactFormat | None  # only set for kind in (AHB, MIG)
    valid_from: date
    valid_until: date
    publication_date: date | None
    version: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d+\.\d+[a-z]?$")] | None
    is_consolidated_reading_version: bool
    is_extraordinary_publication: bool
    is_error_correction: bool
    is_informational_reading_version: bool
    additional_text: str | None
    id: int

    # pylint:disable=too-many-locals
    @classmethod
    def from_filename(cls, file: Path | str) -> "DocumentMetadata":
        """extract metadata which have been encoded into a filename (by the scraper class)"""
        filename: str
        if isinstance(file, str):
            filename = file
        elif isinstance(file, Path):
            filename = file.name
        else:
            raise ValueError("Argument must be either a filename or a path")
        filename_mod = ".".join(filename.split(".")[:-1])  # now
        filename_parts = filename_mod.split("_")
        _id: int = int(filename_parts[-1])
        (
            is_error_correction,
            is_extraordinary_publication,
            is_consolidated_reading_version,
            is_informational_reading_version,
        ) = [x.lower() == "x" for x in filename_parts[-2]]
        valid_from, valid_to, publ_date = [
            datetime.strptime(fp, "%Y%m%d") for fp in [filename_parts[-5], filename_parts[-4], filename_parts[-3]]
        ]
        version = None if filename_parts[-6] == "NV" else filename_parts[-6]
        edifact_format: EdifactFormat | None = None
        kind: _FileKind | None = None
        additional_text: str | None = None
        if filename.startswith("MIG_") or filename.startswith("AHB_"):
            try:
                edifact_format = EdifactFormat(filename_parts[-7])
            except ValueError:
                # happens, e.g. for the AHB
                # "Beschreibung der mit dem Herkunftsnachweisregister (HKN-R) des Umweltbundesamts (UBA)
                # auszutauschenden Daten" which contains UTILMD, ORDERS, ORDRSP and MSCONS.
                # without checking the actual file content we have no chance to derive this information.
                _logger.warning("Could not derive EdifactFormat for %s", filename)
            kind = filename.split("_")[0]  # type:ignore[assignment]
        elif filename.startswith("EBD_"):
            kind = "EBD"
        elif filename.endswith("xsd"):
            kind = "XSD"
        elif filename.endswith("xlsx"):
            kind = "EXCEL"
        else:
            additional_text = filename_parts[0]
        return DocumentMetadata(
            kind=kind,
            edifact_format=edifact_format,
            valid_from=valid_from,
            valid_until=valid_to,
            publication_date=publ_date,
            version=version,
            is_consolidated_reading_version=is_consolidated_reading_version,
            is_extraordinary_publication=is_extraordinary_publication,
            is_error_correction=is_error_correction,
            is_informational_reading_version=is_informational_reading_version,
            id=_id,
            additional_text=additional_text,
        )


__all__ = ["DocumentMetadata"]
