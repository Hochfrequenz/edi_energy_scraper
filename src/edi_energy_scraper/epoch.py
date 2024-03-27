"""
this module contains the epoch enum
"""

from enum import StrEnum


class Epoch(StrEnum):  # pylint: disable=too-few-public-methods
    """
    An Epoch describes the time range in which documents are valid.
    It's relative to the current time, meaning that CURRENT documents are valid now, PAST documents are not valid
    anymore, and FUTURE documents will become valid in the future.
    But running the script at a different time may change the Epoch of a document.
    """

    PAST = "past"  #: documents that are not valid anymore and have been archived
    CURRENT = "current"  #: documents that are currently valid valid_from <= now < valid_to
    FUTURE = "future"  #: documents that will become valid in the future (most likely with the next format version)
