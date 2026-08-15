import base64
import math
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Literal

import httpx
import orjson as json
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import ElementHandle, FloatRect, Page

from ..constants import base_height, base_width, elements_to_disable, max_screenshot_height, templates_path
from .browser import Browser
from .exceptions import ElementNotFound, RequiredURL
from .options import (
    ElementScreenshotOptions,
    LegacyScreenshotOptions,
    PageScreenshotOptions,
    RawOptions,
    SectionScreenshotOptions,
    SourceOptions,
    StatusOptions,
)

env = Environment(loader=FileSystemLoader(templates_path), autoescape=True, enable_async=True)
custom_css = (templates_path / "custom.css").read_text(encoding="utf-8")
add_count_box_script = (templates_path / "add_count_box.js").read_text(encoding="utf-8")
element_screenshot_script = (templates_path / "element_screenshot_evaluate.js").read_text(encoding="utf-8")
section_screenshot_script = (templates_path / "section_screenshot_evaluate.js").read_text(encoding="utf-8")

remote_endpoints = {
    "legacy_screenshot": "legacy_screenshot",
    "page_screenshot": "page",
    "element_screenshot": "element_screenshot",
    "section_screenshot": "section_screenshot",
    "source": "source",
    "get_raw": "get_raw",
    "status": "status",
}
remote_fallback_hop = ContextVar("remote_fallback_hop", default=0)
remote_fallback_header = "X-WebRender-Fallback-Hop"


def webrender_fallback(func):
    @wraps(func)
    async def wrapper(self, options=None):
        remote_endpoint = remote_endpoints.get(func.__name__, func.__name__)

        if self.remote_only:
            if not self.remote_webrender_url:
                self.logger.error("Remote-only mode is enabled, but no remote WebRender URL is configured.")
                return None
            self.logger.info("Local WebRender is disabled, using remote WebRender only.")
            return await self._request_remote(remote_endpoint, options)

        if not await self.browser.check_status():
            self.logger.warning("WebRender browser is not initialized.")
            if self.remote_webrender_url:
                return await self._request_remote(remote_endpoint, options)
            return None

        try:
            self.logger.info(func.__name__ + " function called with options: " + str(options))
            result = await func(self, options)
            if result is not None:
                return result
            self.logger.warning(f"Local WebRender returned no result for {func.__name__}.")
        except Exception:
            self.logger.exception(f"WebRender processing failed with options: {options}:")

        if self.remote_webrender_url:
            return await self._request_remote(remote_endpoint, options)
        return None

    return wrapper


class WebRender:
    name = "AkariBot WebRender™"

    def __init__(
        self,
        debug: bool = False,
        remote_webrender_url: str | None = None,
        remote_only: bool = False,
        export_logs=False,
        logs_path=None,
        name: str | None = None,
        headless: bool | None = None,
        keep_pages_open: bool | None = None,
        remote_timeout: float = 30,
    ):
        """
        :param debug: Enable debug logging. For backward compatibility, it also enables headed mode and keeps pages open
            unless ``headless`` and ``keep_pages_open`` are explicitly set.
        :param headless: Run the browser without a visible window. Defaults to the inverse of ``debug``.
        :param keep_pages_open: Keep rendered pages open after requests. Defaults to ``debug``.
        :param remote_timeout: Timeout in seconds for requests to the remote WebRender service.
        """
        self.debug = debug
        self.headless = not debug if headless is None else headless
        self.keep_pages_open = debug if keep_pages_open is None else keep_pages_open
        self.remote_webrender_url = None
        if remote_webrender_url and remote_webrender_url.strip():
            parsed_remote_url = httpx.URL(remote_webrender_url.strip())
            if parsed_remote_url.scheme not in {"http", "https"} or not parsed_remote_url.host:
                raise ValueError("remote_webrender_url must be an HTTP or HTTPS URL")
            if parsed_remote_url.query or parsed_remote_url.fragment:
                raise ValueError("remote_webrender_url must not contain a query string or fragment")
            remote_raw_path = parsed_remote_url.raw_path.rstrip(b"/") + b"/"
            self.remote_webrender_url = str(parsed_remote_url.copy_with(raw_path=remote_raw_path))
        self.remote_only = remote_only
        self.remote_timeout = float(remote_timeout)
        if not math.isfinite(self.remote_timeout) or self.remote_timeout <= 0:
            raise ValueError("remote_timeout must be a finite number greater than zero")
        self.export_logs = export_logs
        self.logs_path = None
        if export_logs:
            if logs_path:
                self.logs_path = Path(logs_path)
            else:
                self.logs_path = (Path(__file__).parent.parent.parent / "logs").resolve()
        if name:
            self.name = name

        self.browser = Browser(
            debug=debug,
            export_logs=export_logs,
            logs_path=self.logs_path,
            headless=self.headless,
        )
        self.browser_init = self.browser.browser_init
        self.browser_close = self.browser.close
        self.logger = self.browser.logger

    async def _request_remote(self, endpoint: str, options=None):
        if not self.remote_webrender_url:
            return None

        current_hop = remote_fallback_hop.get()
        if current_hop >= 1:
            self.logger.error("Remote WebRender fallback limit reached; refusing to forward the request again.")
            return None

        remote_url = f"{self.remote_webrender_url}{endpoint}/"
        payload = options.model_dump(mode="json", exclude_none=True) if options is not None else {}
        try:
            safe_remote_url = httpx.URL(remote_url).copy_with(
                username=None,
                password=None,
                query=None,
                fragment=None,
            )
            self.logger.info(f"Trying remote WebRender: {safe_remote_url}")
            async with httpx.AsyncClient(timeout=self.remote_timeout, follow_redirects=True) as client:
                resp = await client.post(
                    remote_url,
                    json=payload,
                    headers={remote_fallback_header: str(current_hop + 1)},
                )
            if resp.status_code != 200:
                self.logger.error(f"Remote WebRender failed: {resp.text}, status code: {resp.status_code}")
                return None
            return json.loads(resp.read())
        except Exception:
            self.logger.exception("Remote WebRender processing failed:")
            return None

    @asynccontextmanager
    async def render_page(
        self,
        width=base_width,
        height=base_height,
        locale="zh_cn",
        content=None,
        url=None,
        css=None,
        stealth=True,
        wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "networkidle",
        wait_after_load: int = 0,
    ):
        page = None
        if self.browser:
            try:
                start_time = time.time()
                page = await self.browser.new_page(width=width, height=height, locale=locale, stealth=stealth)
                if content:
                    await page.set_content(content, wait_until=wait_until)
                if url:
                    await page.goto(url, wait_until=wait_until)
                if content or url:
                    await page.add_style_tag(content=custom_css)
                    if css:
                        await page.add_style_tag(content=css)
                    if wait_after_load:
                        await page.wait_for_timeout(wait_after_load)
                yield page, start_time
            finally:
                if not self.keep_pages_open and page:
                    await page.close()

    @staticmethod
    async def select_element(el: str | list, pg: Page) -> tuple[ElementHandle | None, str | None]:
        if isinstance(el, str):
            return (await pg.query_selector(el)), el
        for obj in el:
            rtn = await pg.query_selector(obj)
            if rtn is not None:
                return rtn, obj
        return None, None

    async def make_screenshot(
        self,
        page: Page,
        el: ElementHandle,
        screenshot_height: int = max_screenshot_height,
        output_type: Literal["png", "jpeg"] = "jpeg",
        output_quality: int = 90,
    ) -> list[str]:
        await page.evaluate("window.scroll(0, 0)")
        content_size = await el.bounding_box()
        dpr = page.viewport_size.get("deviceScaleFactor", 1)
        screenshot_height = math.floor(screenshot_height / dpr)
        self.logger.info(f"Content size: {content_size}, DPR: {dpr}, Screenshot height: {screenshot_height}")

        # If content height is less than max screenshot height, take a single screenshot and return as a list with one item

        if content_size.get("height") < max_screenshot_height:
            self.logger.info("Content height is less than max screenshot height, taking single screenshot.")
            img = await el.screenshot(type=output_type, quality=output_quality if output_type == "jpeg" else None)
            return [base64.b64encode(img).decode()]

        # Otherwise, take multiple screenshots and return as a list with multiple items

        y_pos = content_size.get("y")
        total_content_height = content_size.get("y")
        images = []
        while y_pos < content_size.get("height") + content_size.get("y"):
            total_content_height += max_screenshot_height
            content_height = max_screenshot_height
            if total_content_height > content_size.get("height") + content_size.get("y"):
                content_height = (
                    content_size.get("height") + content_size.get("y") - total_content_height + max_screenshot_height
                )
            await page.evaluate(f"window.scroll({content_size.get('x')}, {y_pos})")
            self.logger.info(
                "X:"
                + str(content_size.get("x"))
                + " Y:"
                + str(y_pos)
                + " Width:"
                + str(content_size.get("width"))
                + " Height:"
                + str(content_height)
            )

            img = await page.screenshot(
                type=output_type,
                quality=output_quality if output_type == "jpeg" else None,
                clip=FloatRect(
                    x=content_size.get("x"), y=y_pos, width=content_size.get("width"), height=content_height
                ),
                full_page=True,
            )
            images.append(base64.b64encode(img).decode())
            y_pos += screenshot_height
        return images

    @classmethod
    async def add_count_box(cls, page: Page, element: str, start_time: float = time.time()):
        return await page.evaluate(
            add_count_box_script,
            {"selected_element": element, "start_time": int(start_time * 1000), "name": cls.name},
        )

    async def select_element_and_screenshot(
        self,
        elements: str | list,
        page: Page,
        start_time: float,
        count_time=True,
        output_type: Literal["png", "jpeg"] = "jpeg",
        output_quality: int = 90,
    ):
        el, selected_ = await self.select_element(elements, page)
        if not el:
            raise ElementNotFound
        if count_time:
            await self.add_count_box(page, selected_, start_time)
        images = await self.make_screenshot(page, el, output_type=output_type, output_quality=output_quality)
        return images

    @webrender_fallback
    async def legacy_screenshot(self, options: LegacyScreenshotOptions):
        async with self.render_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=await env.get_template("content.html").render_async(language="zh-CN", contents=options.content),
            url=options.url,
            css=options.css,
            stealth=options.stealth,
            wait_until=options.wait_until,
            wait_after_load=options.wait_after_load,
        ) as (page, start_time):
            images = await self.select_element_and_screenshot(
                elements=[
                    "body > .mw-parser-output > *:not(script):not(style):not(link):not(meta)"
                    if options.mw
                    else "body > *:not(script):not(style):not(link):not(meta)"
                ],
                page=page,
                start_time=start_time,
                count_time=options.counttime,
                output_type=options.output_type,
                output_quality=options.output_quality,
            )
            return images

    @webrender_fallback
    async def page_screenshot(self, options: PageScreenshotOptions):

        async with self.render_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=options.content,
            url=options.url,
            css=options.css,
            stealth=options.stealth,
            wait_until=options.wait_until,
            wait_after_load=options.wait_after_load,
        ) as (page, start_time):
            images = await self.select_element_and_screenshot(
                elements=["body"],
                page=page,
                start_time=start_time,
                count_time=options.counttime,
                output_type=options.output_type,
                output_quality=options.output_quality,
            )
            return images

    @webrender_fallback
    async def element_screenshot(self, options: ElementScreenshotOptions):
        async with self.render_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=options.content,
            url=options.url,
            css=options.css,
            stealth=options.stealth,
            wait_until=options.wait_until,
            wait_after_load=options.wait_after_load,
        ) as (page, start_time):
            await page.evaluate(element_screenshot_script, elements_to_disable)
            images = await self.select_element_and_screenshot(
                elements=options.element,
                page=page,
                start_time=start_time,
                count_time=options.counttime,
                output_type=options.output_type,
                output_quality=options.output_quality,
            )
            return images

    @webrender_fallback
    async def section_screenshot(self, options: SectionScreenshotOptions):
        async with self.render_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=options.content,
            url=options.url,
            css=options.css,
            stealth=options.stealth,
            wait_until=options.wait_until,
            wait_after_load=options.wait_after_load,
        ) as (page, start_time):
            await page.evaluate(
                section_screenshot_script,
                {"section": options.section, "elements_to_disable": elements_to_disable},
            )
            images = await self.select_element_and_screenshot(
                elements=".bot-sectionbox",
                page=page,
                start_time=start_time,
                count_time=options.counttime,
                output_type=options.output_type,
                output_quality=options.output_quality,
            )
            return images

    @webrender_fallback
    async def source(self, options: SourceOptions):
        url = options.url
        if not url:
            raise RequiredURL
        async with self.render_page(locale=options.locale, stealth=options.stealth) as (page, _start_time):
            resp = await page.goto(url, wait_until=options.wait_until)
            if options.wait_after_load:
                await page.wait_for_timeout(options.wait_after_load)
            if resp.status != 200:  # attempt to fetch the url content using fetch
                get = await page.request.fetch(url)
                if get.status == 200:
                    return get.text()
                self.logger.error(f"Failed to fetch URL: {url}, status code: {get.status}")
                return None

            _source = await page.content()
            if options.raw_text:
                _source = await page.query_selector("pre")
                return await _source.inner_text()

            return _source

    @webrender_fallback
    async def get_raw(self, options: RawOptions):
        url = options.url
        if not url:
            raise RequiredURL
        async with self.render_page(locale=options.locale, stealth=options.stealth) as (page, _start_time):
            resp = await page.request.fetch(url)
            body = await resp.body()
            return {
                "status": resp.status,
                "content_type": resp.headers.get("content-type", "application/octet-stream"),
                "data": base64.b64encode(body).decode(),
            }

    @webrender_fallback
    async def status(self, options: StatusOptions | None = None):
        contexts_open = {}
        if self.browser:
            for context in self.browser.contexts:
                contexts_open[context] = []
                for page in self.browser.contexts[context].pages:
                    contexts_open[context].append(page.url)

            contexts_total = 0
            if self.browser.browser:
                contexts_total = len(self.browser.browser.contexts)

            return {
                "browser_initialized": await self.browser.check_status(),
                "debug_mode": self.debug,
                "headless": self.headless,
                "browser_mode": "headless" if self.headless else "headed",
                "keep_pages_open": self.keep_pages_open,
                "remote_only": self.remote_only,
                "remote_configured": bool(self.remote_webrender_url),
                "remote_timeout": self.remote_timeout,
                "export_logs": self.export_logs,
                "logs_path": str(self.logs_path) if self.logs_path else None,
                "name": self.name,
                "contexts_open_sorted": contexts_open,
                "contexts_total": contexts_total,
                "leaked": len(contexts_open) != contexts_total,
            }
