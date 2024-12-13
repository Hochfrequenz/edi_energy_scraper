"""
this module contains the epoch enum
"""

import sys

if sys.version_info.major == 3 and sys.version_info.minor >= 11:
    from enum import StrEnum

    # We have to use the builtin / std lib enum.StrEnum in Python >= 3.11, because the behaviour of (str,Enum) changed:
    # class Foo(str, Enum):
    #     MEMBER = "MEMBER"
    # f"{a_str_enum_member}" results in "MEMBER" for Python < v3.11 but "Foo.MEMBER" in Python >= v3.11
else:
    from enum import Enum

    class StrEnum(str, Enum):  # type:ignore[no-redef]
        """
        An enum class of which each member has a string representation.
        This is a workaround for Python <v3.11 because enum.StrEnum was introduced in Python 3.11.
        """

        # We'll live with this class for Python <v3.11. The unit test for python 3.9-3.11 ensure that this works.


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
