import asyncio
import base64
import datetime
import math
from typing import Optional

import httpx
import orjson as json
from jinja2 import Environment, FileSystemLoader
from typing import Literal
from playwright.async_api import Page, ElementHandle, FloatRect

from .browser import Browser
from .exceptions import ElementNotFound, RequiredURL
from .options import LegacyScreenshotOptions, PageScreenshotOptions, ElementScreenshotOptions, SectionScreenshotOptions, \
    SourceOptions
from ..constants import templates_path, elements_to_disable, max_screenshot_height, base_width, base_height

env = Environment(loader=FileSystemLoader(templates_path), autoescape=True, enable_async=True)


def webrender_fallback(func):
    async def wrapper(self, options):
        if not self.browser.browser and not self.remote_only:
            self.logger.warning("WebRender browser is not initialized.")
            return None
        request_remote = False
        if self.remote_webrender_url and self.remote_only:
            self.logger.warning(
                "Local WebRender is disabled, using remote WebRender only.")
            request_remote = True
        else:
            try:
                self.logger.info(func.__name__ +
                            "function called with options: " + str(options))
                return await func(self, options)
            except Exception:
                self.logger.exception(f"WebRender processing failed with options: {options}:")
                if self.remote_webrender_url:
                    request_remote = True
        if request_remote:
            try:
                if self.remote_webrender_url:
                    self.logger.info(
                        f"Trying get content from remote web render...")
                    remote_url = self.remote_webrender_url + func.__name__ + "/"
                    data = options.model_dump_json(exclude_none=True)
                    self.logger.info(f"Remote URL: {remote_url}, Options: {data}")
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            remote_url,
                            data=data,
                            timeout=30,
                            follow_redirects=True
                        )
                        if resp.status_code != 200:
                            self.logger.error(f"Failed to render: {
                                         resp.text}, status code: {resp.status_code}")
                            return None
                        return json.loads(resp.read())
            except Exception:
                self.logger.exception(f"Remote WebRender processing failed: ")
        return None

    return wrapper


class WebRender:
    browser: Browser = None
    debug: bool = False
    custom_css = open(templates_path + "/custom.css",
                      "r", encoding="utf-8").read()
    remote_webrender_url = None
    remote_only = False

    def __init__(self, debug: bool = False, remote_webrender_url: Optional[str] = None, remote_only: bool = False):
        """
        :param debug: If True, the browser will run on non-headless mode, the page will not be closed after the screenshot is taken.
        """
        self.debug = debug
        self.remote_webrender_url = remote_webrender_url
        if self.remote_webrender_url and self.remote_webrender_url[-1] != "/":
            self.remote_webrender_url += "/"
        self.remote_only = remote_only

        if not WebRender.browser:
            self.browser = Browser(debug=debug)
            self.browser_init = self.browser.browser_init
            self.browser_close = self.browser.close
            self.logger = self.browser.logger

    @staticmethod
    async def select_element(el: str | list, pg: Page) -> (ElementHandle, str):
        if isinstance(el, str):
            return (await pg.query_selector(el)), el
        else:
            for obj in el:
                rtn = await pg.query_selector(obj)
                if rtn is not None:
                    return rtn, obj
        return None, None

    async def make_screenshot(self, page: Page, el: ElementHandle, screenshot_height: int = max_screenshot_height,
                              output_type: Literal['png', 'jpeg'] = 'jpeg', output_quality: int = 90) -> list[str]:
        await page.evaluate("window.scroll(0, 0)")
        await page.route("**/*", lambda route: route.abort())
        content_size = await el.bounding_box()
        dpr = page.viewport_size.get("deviceScaleFactor", 1)
        screenshot_height = math.floor(screenshot_height / dpr)
        self.logger.info(f"Content size: {content_size}, DPR: {
                         dpr}, Screenshot height: {screenshot_height}")

        y_pos = content_size.get("y")
        total_content_height = content_size.get("y")
        images = []
        while True:
            if y_pos > content_size.get("height") + content_size.get("y"):
                break
            total_content_height += max_screenshot_height
            content_height = max_screenshot_height
            if (total_content_height > content_size.get("height") + content_size.get("y")):
                content_height = content_size.get(
                    "height") + content_size.get("y") - total_content_height + max_screenshot_height
            await page.evaluate(f"window.scroll({content_size.get("x")}, {y_pos})")
            await asyncio.sleep(3)
            self.logger.info("X:" + str(content_size.get("x")) + " Y:" + str(y_pos) +
                             " Width:" + str(content_size.get("width")) + " Height:" + str(content_height))

            img = await page.screenshot(type=output_type,
                                        quality=output_quality if output_type == 'jpeg' else None,
                                        clip=FloatRect(x=content_size.get("x"),
                                                       y=y_pos,
                                                       width=content_size.get(
                                                           "width"),
                                                       height=content_height), full_page=True)
            images.append(base64.b64encode(img).decode())
            y_pos += screenshot_height
        return images

    @staticmethod
    async def add_count_box(page: Page, element: str, start_time: float = datetime.datetime.now().timestamp()):
        return await page.evaluate("""
            ({selected_element, start_time}) => {
                t = document.createElement('span')
                t.className = 'bot-countbox'
                t.style = 'position: absolute;opacity: 0.2;'
                document.querySelector(selected_element).insertBefore(t, document.querySelector(selected_element).firstChild)
                document.querySelector(selected_element).classList.add('webrender-selected-element')
                countTime();
                function countTime() {
                    var nowtime = new Date();
                    var lefttime = parseInt((nowtime.getTime() - start_time) / 1000);
                    document.querySelector(".bot-countbox").innerHTML = `Generated by akaribot in ${lefttime}s`;
                    if (lefttime <= 0) {
                        return;
                    }
                setTimeout(countTime, 1000);
                }
            }""", {"selected_element": element, "start_time": int(start_time * 1000)})


    async def init_page(self, width=base_width, height=base_height, locale='zh_cn', content=None, url=None, css=None):
        start_time = datetime.datetime.now().timestamp()
        page = await self.browser.new_page(width=width, height=height, locale=locale)
        if content:
            await page.set_content(content, wait_until="networkidle")
        else:
            await page.goto(url, wait_until="networkidle")
        custom_css = self.custom_css
        await page.add_style_tag(content=custom_css)
        if css:
            await page.add_style_tag(content=css)
        return page, start_time

    async def select_element_and_screenshot(self,
                                            elements: str | list,
                                            page: Page,
                                            start_time: float,
                                            count_time=True,
                                            output_type: Literal['png', 'jpeg'] = 'jpeg',
                                            output_quality: int = 90):
        el, selected_ = await self.select_element(elements, page)
        if not el:
            raise ElementNotFound
        if count_time:
            await self.add_count_box(page, selected_, start_time)
        images = await self.make_screenshot(page, el, output_type=output_type,
                                            output_quality=output_quality)
        if not self.debug:
            await page.close()
        return images


    @webrender_fallback
    async def legacy_screenshot(self, options: LegacyScreenshotOptions):
        page, start_time = await self.init_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=await env.get_template("content.html").render_async(language='zh-CN', contents=options.content),
            url=options.url,
            css=options.css
        )
        images = await self.select_element_and_screenshot(
            elements=["body > .mw-parser-output > *:not(script):not(style):not(link):not(meta)" if options.mw
                      else "body > *:not(script):not(style):not(link):not(meta)"],
            page=page,
            start_time=start_time,
            count_time=options.counttime,
            output_type=options.output_type,
            output_quality=options.output_quality
        )
        return images

    @webrender_fallback
    async def page_screenshot(self, options: PageScreenshotOptions):
        page, start_time = await self.init_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=options.content,
            url=options.url,
            css=options.css
        )
        images = await self.select_element_and_screenshot(
            elements=['body'],
            page=page,
            start_time=start_time,
            count_time=options.counttime,
            output_type=options.output_type,
            output_quality=options.output_quality
        )
        return images

    @webrender_fallback
    async def element_screenshot(self, options: ElementScreenshotOptions):
        page, start_time = await self.init_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=options.content,
            url=options.url,
            css=options.css
        )

        # :rina: :rina: :rina: :rina:
        await page.evaluate("""(elements_to_disable) => {
                const images = document.querySelectorAll("img")
                images.forEach(image => {
                  image.removeAttribute('loading');
                })
                const animated = document.querySelectorAll(".animated")
                for (var i = 0; i < animated.length; i++) {
                  b = animated[i].querySelectorAll('img')
                  for (ii = 0; ii < b.length; ii++) {
                    b[ii].width = b[ii].getAttribute('width') / (b.length / 2)
                    b[ii].height = b[ii].getAttribute('height') / (b.length / 2)
                  }
                  animated[i].className = 'nolongeranimatebaka'
                }
                for (var i = 0; i < elements_to_disable.length; i++) {
                  const element_to_boom = document.querySelector(elements_to_disable[i])// :rina: :rina: :rina: :rina:
                  if (element_to_boom != null) {
                    element_to_boom.style = 'display: none'
                  }
                }
                document.querySelectorAll('*').forEach(element => {
                  element.parentNode.replaceChild(element.cloneNode(true), element);
                });
                window.scroll(0, 0)
              }""", elements_to_disable)
        images = await self.select_element_and_screenshot(
            elements=options.element,
            page=page,
            start_time=start_time,
            count_time=options.counttime,
            output_type=options.output_type,
            output_quality=options.output_quality
        )
        return images

    @webrender_fallback
    async def section_screenshot(self, options: SectionScreenshotOptions):
        page, start_time = await self.init_page(
            width=options.width,
            height=options.height,
            locale=options.locale,
            content=options.content,
            url=options.url,
            css=options.css
        )
        images = await self.select_element_and_screenshot(
            elements=options.section,
            page=page,
            start_time=start_time,
            count_time=options.counttime,
            output_type=options.output_type,
            output_quality=options.output_quality
        )
        return images

    @webrender_fallback
    async def source(self, options: SourceOptions):
        page = await self.browser.new_page(locale=options.locale)
        try:
            url = options.url
            if not url:
                raise RequiredURL

            await page.goto(url, wait_until="networkidle")
            _source = await page.content()
            if options.raw_text:
                _source = await page.query_selector("pre")
                return await _source.inner_text()

            return _source
        finally:
            if not self.debug:
                await page.close()
