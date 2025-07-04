from pydantic import BaseModel

from ..constants import base_width, base_height


class LegacyScreenshotOptions(BaseModel):
    content: str = None
    width: int = base_width
    height: int = base_height
    mw: bool = False
    tracing: bool = False
    counttime: bool = True
    locale: str = "zh_cn"


class PageScreenshotOptions(BaseModel):
    url: str = None
    css: str = None
    locale: str = "zh_cn"


class ElementScreenshotOptions(BaseModel):
    element: str | list = None
    content: str = None
    url: str = None
    css: str = None
    width: int = base_width
    height: int = base_height
    counttime: bool = True
    tracing: bool = False
    locale: str = "zh_cn"


class SectionScreenshotOptions(BaseModel):
    section: str | list = None
    content: str = None
    url: str = None
    css: str = None
    width: int = base_width
    height: int = base_height
    counttime: bool = True
    tracing: bool = False
    locale: str = "zh_cn"


class SourceOptions(BaseModel):
    url: str = None
    raw_text: bool = False
    locale: str = "zh_cn"
