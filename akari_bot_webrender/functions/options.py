from typing import Literal

from pydantic import BaseModel

from ..constants import base_width, base_height


class BaseOptions(BaseModel):
    locale: str = "zh_cn"
    output_type: Literal["png", "jpeg"] = "jpeg"
    output_quality: int = 90
    counttime: bool = True
    width: int = base_width
    height: int = base_height
    url: str | None = None
    content: str | None = None
    css: str | None = None
    stealth: bool = True


class LegacyScreenshotOptions(BaseOptions):
    mw: bool = False


class PageScreenshotOptions(BaseOptions):
    pass


class ElementScreenshotOptions(BaseOptions):
    element: str | list | None = None
    elements_to_disable: list | None = None


class SectionScreenshotOptions(BaseOptions):
    section: str | list | None = None
    elements_to_disable: list | None = None


class SourceOptions(BaseModel):
    url: str | None = None
    raw_text: bool = False
    locale: str = "zh_cn"
    stealth: bool = True


class StatusOptions(BaseModel):
    pass
