import asyncio
import base64
import datetime
import math
import traceback

from jinja2 import Environment, FileSystemLoader
from playwright.async_api import Page, ElementHandle, FloatRect

from ..constants import templates_path, elements_to_disable, max_screenshot_height
from .browser import Browser
from .exceptions import ElementNotFound, RequiredURL
from .options import LegacyScreenshotOptions, PageScreenshotOptions, ElementScreenshotOptions, SectionScreenshotOptions, \
    SourceOptions

import httpx

import orjson as json

from loguru import logger


env = Environment(loader=FileSystemLoader(templates_path), autoescape=True)

_remote_webrender_url: str = None


def webrender_fallback(func):
    async def wrapper(self, options):

        try:
            return await func(self, options)
        except Exception as e:
            logger.error(f"WebRender processing failed: {e}")
            logger.error(traceback.format_exc())
            try:
                if _remote_webrender_url is not None:
                    logger.info(f"Trying get content from remote web render...")
                    remote_url = _remote_webrender_url + func.__name__ + '/'
                    data = options.model_dump_json(exclude_none=True)
                    logger.info(f"Remote URL: {remote_url}, Options: {data}")
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            remote_url,
                            data=data,
                            timeout=30
                        )
                        if resp.status_code != 200:
                            logger.error(f"Failed to render: {resp.text}, status code: {resp.status_code}")
                            return None
                        return json.loads(resp.read())
            except Exception as e:
                logger.error(f"Remote WebRender processing failed: {e}")
                logger.error(traceback.format_exc())
                return None

    return wrapper

class WebRender:
    browser: Browser = None
    debug: bool = False
    custom_css = open(templates_path + '/custom.css', 'r', encoding='utf-8').read()
    remote_webrender_url = None

    def __init__(self, debug: bool = False, remote_webrender_url=None):
        """
        :param debug: If True, the browser will run on non-headless mode, the page will not be closed after the screenshot is taken.
        """
        self.debug = debug
        self.remote_webrender_url = remote_webrender_url
        if self.remote_webrender_url and self.remote_webrender_url[-1] != '/':
            self.remote_webrender_url += '/'
        global _remote_webrender_url
        _remote_webrender_url = self.remote_webrender_url

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


    async def make_screenshot(self, page: Page, el: ElementHandle, screenshot_height=max_screenshot_height) -> list:
        await page.evaluate("window.scroll(0, 0)")
        await page.route('**/*', lambda route: route.abort())
        await page.wait_for_load_state("networkidle")
        content_size = await el.bounding_box()
        dpr = page.viewport_size.get("deviceScaleFactor", 1)
        screenshot_height = math.floor(screenshot_height / dpr)
        self.logger.info(f"Content size: {content_size}, DPR: {dpr}, Screenshot height: {screenshot_height}")

        y_pos = content_size.get("y")
        total_content_height = content_size.get("y")
        images = []
        while True:
            if y_pos > content_size.get("height") + content_size.get("y"):
                break
            total_content_height += max_screenshot_height
            content_height = max_screenshot_height
            if (total_content_height > content_size.get("height") + content_size.get("y")):
                content_height = content_size.get("height") + content_size.get("y") - total_content_height + max_screenshot_height
            await page.evaluate(f"window.scroll({content_size.get("x")}, {y_pos})")
            await asyncio.sleep(3)
            self.logger.info("X:" + str(content_size.get("x")) + " Y:" + str(y_pos)+ " Width:" + str(content_size.get("width")) + " Height:" + str(content_height))

            img = await page.screenshot(type='png',
                                        clip=FloatRect(x=content_size.get("x"),
                                                       y=y_pos,
                                                       width=content_size.get("width"),
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
            }""", {'selected_element': element, 'start_time': int(start_time * 1000)})


    @webrender_fallback
    async def legacy_screenshot(self, options: LegacyScreenshotOptions):
        start_time = datetime.datetime.now().timestamp()
        page = await self.browser.new_page(width=options.width, height=options.height)
        rendered_html = env.get_template("content.html").render(language='zh-CN', content=options.content)
        await page.set_content(rendered_html, wait_until='networkidle')
        if options.mw:
            selector = 'body > .mw-parser-output > *:not(script):not(style):not(link):not(meta)'
        else:
            selector = 'body > *:not(script):not(style):not(link):not(meta)'
        element_ = await page.query_selector(selector)
        if not element_:
            raise ElementNotFound
        if options.counttime:
            await self.add_count_box(page, selector, start_time)
        images = await self.make_screenshot(page, element_)
        if not self.debug:
            await page.close()
        return images

    @webrender_fallback
    async def page_screenshot(self, options: PageScreenshotOptions):
        page = await self.browser.new_page()
        await page.goto(options.url, wait_until="networkidle")
        custom_css = self.custom_css
        await page.add_style_tag(content=custom_css)
        if options.css:
            await page.add_style_tag(content=options.css)
        screenshot = await self.make_screenshot(page, await page.query_selector("body"))
        if not self.debug:
            await page.close()
        return screenshot

    @webrender_fallback
    async def element_screenshot(self, options: ElementScreenshotOptions):
        start_time = datetime.datetime.now().timestamp()
        page = await self.browser.new_page(width=options.width, height=options.height)
        if options.content:
            await page.set_content(options.content)
        else:
            await page.goto(options.url, wait_until="networkidle")
        custom_css = self.custom_css
        await page.add_style_tag(content=custom_css)
        if options.css:
            await page.add_style_tag(content=options.css)
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
        el, selected_ = await self.select_element(options.element, page)
        if not el:
            raise ElementNotFound
        if options.counttime:
            await self.add_count_box(page, selected_, start_time)
        images = await self.make_screenshot(page, el)
        if not self.debug:
            await page.close()
        return images

    @webrender_fallback
    async def section_screenshot(self, options: SectionScreenshotOptions):
        start_time = datetime.datetime.now().timestamp()
        page = await self.browser.new_page(width=options.width, height=options.height)
        if options.content:
            await page.set_content(options.content)
        else:
            await page.goto(options.url, wait_until="networkidle")
        if options.css:
            await page.add_style_tag(content=options.css + self.custom_css)
        section, selected_ = await self.select_element(options.section, page)
        if not section:
            raise ElementNotFound
        if options.counttime:
            await self.add_count_box(page, selected_, start_time)
        images = await self.make_screenshot(page, section)
        if not self.debug:
            await page.close()
        return images

    @webrender_fallback
    async def source(self, options: SourceOptions):
        page = await self.browser.new_page()
        try:
            url = options.url
            if not url:
                raise RequiredURL

            await page.goto(url, wait_until="networkidle")
            _source = await page.content()

            return _source
        finally:
            if not self.debug:
                await page.close()