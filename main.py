import asyncio
import base64
import logging

import orjson as json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse
from playwright import async_api
from playwright.async_api import Playwright, Browser as BrowserProcess, Page
from pydantic import BaseModel

with open('config.json', 'r') as f:
    config = json.loads(f.read())

app = FastAPI()
logger = logging.getLogger("uvicorn")

class ScreenshotOptions(BaseModel):
    url: str = None
    css: str = None
    width: int = 1280
    height: int = 720


class ElementScreenshotOptions(ScreenshotOptions):
    element: str | list = None
    content: str = None
    counttime: bool = False
    tracing: bool = False


class SectionScreenshotOptions(ScreenshotOptions):
    section: str | list = None
    content: str = None
    counttime: bool = False
    tracing: bool = False


# 自定义CSS
custom_css = """
span.heimu a.external, span.heimu a.external:visited, span.heimu a.extiw, span.heimu a.extiw:visited {
  color: #252525;}
.heimu, .heimu a, a .heimu, .heimu a.new {
  background-color: #cccccc;
  text-shadow: none;
}
.tabber-container-infobox ul.tabbernav {
  display: none;
}
.tabber-container-infobox .tabber .tabbertab {
  display: unset !important;
}
"""


class Browser:
    playwright: Playwright = None
    browser: BrowserProcess = None

    @classmethod
    async def browser_init(cls):
        if not cls.playwright and not cls.browser:
            logger.info('Launching browser...')
            cls.playwright = await async_api.async_playwright().start()
            cls.browser = await cls.playwright.firefox.launch(headless=True)
            while not cls.browser:
                await asyncio.sleep(1)
            logger.info('Successfully launched browser.')

    @classmethod
    async def close(cls):
        await cls.browser.close()


async def is_avail(el: int | list, pg: Page):
    if isinstance(el, str):
        return el
    else:
        for obj in el:
            rtn = await pg.query_selector(str(obj))
            if rtn:
                return str(obj)
            break


async def makeScreenshot(page: Page, el: Page.query_selector):
    await page.evaluate("window.scroll(0, 0)")
    images = []
    img = await el.screenshot(type='png')
    images.append(base64.b64encode(img).decode())
    return images


@app.post("/page/")
async def page_screenshot(options: ScreenshotOptions):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    await page.goto(options.url, wait_until="networkidle")
    if options.css:
        await page.add_style_tag(content=options.css + custom_css)
    screenshot = await makeScreenshot(page, await page.query_selector("body"))
    await page.close()
    return ORJSONResponse(content=screenshot)


@app.post("/element_screenshot/")
async def element_screenshot(options: ElementScreenshotOptions):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    if options.content:
        await page.set_content(options.content)
    else:
        await page.goto(options.url, wait_until="networkidle")
    if options.css:
        await page.add_style_tag(content=options.css + custom_css)
    el = await page.query_selector(await is_avail(options.element, page))
    if not el:
        raise HTTPException(status_code=404, detail="Element not found")
    images = await makeScreenshot(page, el)
    await page.close()
    return ORJSONResponse(content=images)


@app.post("/section_screenshot/")
async def section_screenshot(options: SectionScreenshotOptions):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    if options.content:
        await page.set_content(options.content)
    else:
        await page.goto(options.url, wait_until="networkidle")
    if options.css:
        await page.add_style_tag(content=options.css + custom_css)
    section = await page.query_selector(await is_avail(options.section, page))
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    images = await makeScreenshot(page, section)
    await page.close()
    return ORJSONResponse(content=images)


@app.get("/source/")
async def source(request: Request):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    try:
        url = request.query_params.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required")

        await page.goto(url, wait_until="networkidle")
        _source = await page.content()

        return ORJSONResponse(content={"source": _source})
    finally:
        await page.close()


if __name__ == "__main__":
    import uvicorn

    try:
        loop = asyncio.new_event_loop()
        logger.info(f"Server starting on {config['server']['host']}:{config['server']['port']}")
        loop.run_until_complete(uvicorn.run(app, host=config["server"]["host"], port=config["server"]["port"]))
    except KeyboardInterrupt:
        logger.info("Server stopped")
        asyncio.run(Browser.close())
