"""
Type definitions for CDVL crawler
"""

from typing import Literal, TypedDict


class LinkDict(TypedDict):
    """A link with text and href"""

    text: str
    href: str


class MediaDict(TypedDict):
    """A media element with type and source"""

    type: str
    src: str


class _RequiredContentFields(TypedDict):
    """Required fields for content data"""

    paragraphs: list[str]
    extracted_at: str
    content_type: Literal["video", "dataset"]


class _OptionalContentFields(TypedDict, total=False):
    """Optional fields for content data"""

    title: str
    links: list[LinkDict]
    tables_count: int
    media: list[MediaDict]
    filename: str
    file_size: str


class PartialContentData(_RequiredContentFields, _OptionalContentFields):
    """
    Content data without id and url (used during parsing)
    """

    pass


class ContentData(PartialContentData):
    """
    Complete content data structure for videos and datasets.
    Includes all required fields.
    """

    id: int
    url: str


# Type aliases for clarity
VideoData = ContentData
DatasetData = ContentData
