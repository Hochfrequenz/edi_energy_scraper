"""
model classes for the bdew-mako API
"""
import re
from datetime import date, datetime, timezone
from typing import Literal, Optional, TypeAlias

import pytz
from efoli import EdifactFormat
from pydantic import BaseModel, field_validator

_berlin_time = pytz.timezone("Europe/Berlin")

_FileExtension :TypeAlias = Literal["pdf", "docx", "xml", "xlsx", "xsd"]
_FileKind :TypeAlias = Literal["MIG", "AHB", "EBD", "XSD", "EXCEL", "OTHER"]
_MigPattern = re.compile(r".*\b[A-Z]{6}\sMIG\b.*")
_AhbPattern = re.compile(r".*\bAHB\b.*")
_FormatPattern = re.compile(r".*\b(?P<format>[A-Z]{6})\b.*")
_VersionPattern = re.compile(r".*\b(?P<version>\d+\.\d+[a-z]?)\b.*")

class Document(BaseModel):
    """single document from the API"""

    userId: int
    id: int
    fileId: int
    title: str
    version: Optional[str]
    topicId: int
    topicGroupId: int
    isFree: bool
    publicationDate: Optional[date]  # informatorische lesefassungen don't have a publication date yet
    validFrom: date
    validTo: Optional[date]
    isConsolidatedReadingVersion: bool
    isExtraordinaryPublication: bool
    isErrorCorrection: bool
    correctionDate: Optional[date]
    isInformationalReadingVersion: bool
    fileType: str
    topicGroupSortNr: int
    topicSortNr: int

    @field_validator("publicationDate", "validFrom", "validTo", "correctionDate", mode="before")
    def _parse_datetime(cls, value: str | datetime) -> date:
        """
        Some datetimes from the API are returned as '2024-10-23T00:00:00' so they are obviously meant as UTC,
        but the offset is not given. Others are returned as '2025-06-06T00:00:00' so they are obviously meant as German
        local time, but the offset is not given. Einmal mit Profis arbeiten.
        Sometimes the offset is correct, sometimes it's wrong. You can't do it right, that's why we just convert it to
        dates in German local time.
        """
        if isinstance(value, str):
            naive_datetime = datetime.fromisoformat(value)
            is_probably_utc = naive_datetime.hour == 23 or naive_datetime.hour == 22
            if is_probably_utc:
                utc_datetime = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
            else:
                berlin_datetime = datetime.fromisoformat(value).replace(tzinfo=_berlin_time)
                utc_datetime = berlin_datetime.astimezone(timezone.utc)
            return utc_datetime.date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

    @property
    def gueltig_bis(self) -> date:
        return self.validTo or date(9999, 12, 31)

    @property
    def gueltig_ab(self) -> date:
        return self.validFrom

    @property
    def file_extension(self)->_FileExtension:
        if self.fileType=="application/pdf":
            return "pdf"
        if self.fileType=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return "docx"
        if self.fileType=="XSD":
            return "xsd"
        if self.fileType=="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            return "xlsx"
        return "pdf"

    @property
    def file_kind(self)->_FileKind:
        if _MigPattern.match(self.title):
            return "MIG"
        if _AhbPattern.match(self.title):
            return "AHB"
        return "OTHER"
    @property
    def edifact_format(self)->EdifactFormat|None:
        match = _FormatPattern.match(self.title)
        if match:
            return EdifactFormat(match.group("format"))
        return None

    @property
    def version(self)->str|None:
        match = _VersionPattern.match(self.title)
        if not match:
            return None
        return match.group("version")

    def get_meaningful_file_name(self) -> str:
        """
        Generates a meaningful file name from the metadata (the attributes of this document instance).
        Ideally, the returned filename is built such, that when sorting naturally ASC, the oldest documents occur first.
        So that any program or human scanning the files can just access, e.g. the last file containing "AHB and MSCONS"
        to get the latest/most relevant MSCONS AHB.
        The file name returned does _not_ include any directory or such.
        The file name returned does have an extension, e.g. it ends with ".pdf".
        The file name returned is unique (as long as the file id is unique).
        """

        placeholder_values= {
            "publication_date": (self.publicationDate or self.gueltig_ab).strftime("%Y%m%d"),
            "from_date": self.gueltig_ab.strftime("%Y%m%d"),
            "to_date": self.gueltig_bis.strftime("%Y%m%d"),
            "extension": self.file_extension,
            "id": str(self.fileId),
            "kind": self.file_kind,
            "edifact_format": (self.edifact_format+"_" if self.edifact_format else ""),
            "version": self.version or "NV"
        }
        return "{kind}_{edifact_format}{version}_{to_date}_{from_date}_{publication_date}_{kind}_{id}.{extension}".format(**placeholder_values)


class ResponseModel(BaseModel):
    """
    Model class for the response of
    curl 'https://bdew-mako.de/api/documents'
    """

    data: list[Document]


__all__ = ["ResponseModel", "Document"]
