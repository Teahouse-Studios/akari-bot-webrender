from typing import Literal

from pydantic import BaseModel

from ..constants import base_width, base_height


class BaseOptions(BaseModel):
    locale: str = "zh_cn"
    output_type: Literal["png", "jpeg"] = "png"
    output_quality: int = 90
    counttime: bool = True
    width: int = base_width
    height: int = base_height
    url: str = None
    content: str = None
    css: str = None


class LegacyScreenshotOptions(BaseOptions):
    mw: bool = False

class PageScreenshotOptions(BaseOptions):
    pass

class ElementScreenshotOptions(BaseOptions):
    element: str | list = None

class SectionScreenshotOptions(BaseOptions):
    section: str | list = None


class SourceOptions(BaseModel):
    url: str = None
    raw_text: bool = False
    locale: str = "zh_cn"
