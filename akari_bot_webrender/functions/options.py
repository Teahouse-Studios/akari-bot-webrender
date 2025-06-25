from pydantic import BaseModel

from ..constants import base_width, base_height


class ScreenshotOptions(BaseModel):
    content: str = None
    width: int = base_width
    height: int = base_height
    mw: bool = False
    tracing: bool = False
    counttime: bool = True

class PageScreenshotOptions(BaseModel):
    url: str = None
    css: str = None

class ElementScreenshotOptions(BaseModel):
    element: str | list = None
    content: str = None
    url: str = None
    css: str = None
    width: int = base_width
    height: int = base_height
    counttime: bool = True
    tracing: bool = False


class SectionScreenshotOptions(BaseModel):
    section: str | list = None
    content: str = None
    url: str = None
    css: str = None
    width: int = base_width
    height: int = base_height
    counttime: bool = True
    tracing: bool = False