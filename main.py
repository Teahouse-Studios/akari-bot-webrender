import asyncio
import base64
import datetime
import logging
from contextlib import asynccontextmanager

import orjson as json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse
from playwright import async_api
from playwright.async_api import Playwright, Browser as BrowserProcess, Page, ElementHandle, BrowserContext
from playwright_stealth import Stealth
from pydantic import BaseModel

with open('config.json', 'r') as f:
    config = json.loads(f.read())

debug = False

logger = logging.getLogger("uvicorn")
user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
base_width = 720
base_height = 1280


class ScreenshotOptions(BaseModel):
    content: str = None
    width: int = base_width
    height: int = base_height
    mw: bool = False
    tracing: bool = False
    counttime: bool = True


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


class Browser:
    playwright: Playwright = None
    browser: BrowserProcess = None
    contexts: dict[str, BrowserContext] = {}
    stealth = Stealth(
        init_scripts_only=True
    )

    @classmethod
    async def browser_init(cls):
        if not cls.playwright and not cls.browser:
            logger.info('Launching browser...')
            cls.playwright = await async_api.async_playwright().start()
            cls.browser = await cls.playwright.firefox.launch(headless=not debug)
            while not cls.browser:
                await asyncio.sleep(1)
            cls.contexts[f'{base_width}x{base_height}'] = await cls.browser.new_context(user_agent=user_agent,
                                                                                        viewport={'width': base_width,
                                                                                                  'height': base_height})
            await cls.stealth.apply_stealth_async(cls.contexts[f'{base_width}x{base_height}'])
            logger.info('Successfully launched browser.')

    @classmethod
    async def close(cls):
        await cls.browser.close()

    @classmethod
    async def new_page(cls, width=base_width, height=base_height):
        if f'{width}x{height}' not in cls.contexts:
            cls.contexts[f'{width}x{height}'] = await cls.browser.new_context(user_agent=user_agent,
                                                                            viewport={'width': width, 'height': height})
            await cls.stealth.apply_stealth_async(cls.contexts[f'{width}x{height}'])

        return await cls.contexts[f'{width}x{height}'].new_page()


class Templates():
    @staticmethod
    def content(contents: str):
        content_plate = f"""<link rel="preconnect" href="https://fonts.googleapis.com">
              <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
              <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK&family=Noto+Sans+JP&family=Noto+Sans+KR&family=Noto+Sans+SC&family=Noto+Sans+TC&display=swap" rel="stylesheet"><style>html body {{
                margin-top: 0px !important;
                font-family: 'Noto Sans SC', sans-serif;
            }}

            :lang(ko) {{
                font-family: 'Noto Sans KR', 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', sans-serif;
            }}

            :lang(ja) {{
                font-family: 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
            }}

            :lang(zh-TW) {{
                font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
            }}

            :lang(zh-HK) {{
                font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
            }}

            :lang(zh-Hans), :lang(zh-CN), :lang(zh) {{
                font-family:  'Noto Sans SC', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans KR', sans-serif;
            }}

            div.infobox div.notaninfobox{{
                width: 100%!important;
                float: none!important;
                margin: 0 0 0 0!important;
            }}

            table.infobox, table.infoboxSpecial, table.moe-infobox {{
                width: 100%!important;
                float: unset!important;
                margin: 0 0 0 0!important;
            }}</style>
            <meta charset="UTF-8">
            <body>
            {contents}
            </body>
            """
        return content_plate

    @staticmethod
    def custom_css():
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
        return custom_css

    @staticmethod
    def elements_to_disable():
        elements_to_disable = ['.notifications-placeholder', '.top-ads-container', '.fandom-sticky-header',
                               'div#WikiaBar', 'aside.page__right-rail',
                               '.n-modal-container', 'div#moe-float-toc-container', 'div#moe-draw-float-button',
                               'div#moe-global-header', '.mys-wrapper',
                               'div#moe-open-in-app', 'div#age-gate', ".va-variant-prompt", ".va-variant-prompt-mobile"]
        return elements_to_disable


async def select_element(el: str | list, pg: Page) -> (ElementHandle, str):
    if isinstance(el, str):
        return (await pg.query_selector(el)), el
    else:
        for obj in el:
            rtn = await pg.query_selector(obj)
            if rtn is not None:
                return rtn, obj


async def make_screenshot(page: Page, el: ElementHandle) -> list:
    await page.evaluate("window.scroll(0, 0)")
    await page.route('**/*', lambda route: route.abort())
    images = []
    img = await el.screenshot(type='png')
    images.append(base64.b64encode(img).decode())
    return images


async def add_count_box(page: Page, element: str, start_time: float=datetime.datetime.now().timestamp()):
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



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await Browser.browser_init()
        yield
    finally:
        await Browser.close()

app = FastAPI(lifespan=lifespan)


@app.post("/")
async def _screenshot(options: ScreenshotOptions):
    start_time = datetime.datetime.now().timestamp()
    page = await Browser.new_page(width=options.width, height=options.height)
    await page.set_content(Templates().content(options.content), wait_until='networkidle')
    if options.mw:
        selector = 'body > .mw-parser-output > *:not(script):not(style):not(link):not(meta)'
    else:
        selector = 'body > *:not(script):not(style):not(link):not(meta)'
    element_ = await page.query_selector(selector)
    if not element_:
        raise HTTPException(status_code=404, detail="Element not found")
    if options.counttime:
        await add_count_box(page, selector, start_time)
    images = await make_screenshot(page, element_)
    if not debug:
        await page.close()
    return ORJSONResponse(content=images)


@app.post("/page/")
async def page_screenshot(url: str = None, css: str = None):
    page = await Browser.new_page()
    await page.goto(url, wait_until="networkidle")
    if css:
        await page.add_style_tag(content=css + Templates().custom_css())
    screenshot = await make_screenshot(page, await page.query_selector("body"))
    if not debug:
        await page.close()
    return ORJSONResponse(content=screenshot)


@app.post("/element_screenshot/")
async def element_screenshot(options: ElementScreenshotOptions):
    start_time = datetime.datetime.now().timestamp()
    page = await Browser.new_page(width=options.width, height=options.height)
    if options.content:
        await page.set_content(options.content)
    else:
        await page.goto(options.url, wait_until="networkidle")
    await page.add_style_tag(content=Templates().custom_css())
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
          }""", Templates().elements_to_disable())
    el, selected_ = await select_element(options.element, page)
    if not el:
        raise HTTPException(status_code=404, detail="Element not found")
    if options.counttime:
        await add_count_box(page, selected_, start_time)
    images = await make_screenshot(page, el)
    if not debug:
        await page.close()
    return ORJSONResponse(content=images)


@app.post("/section_screenshot/")
async def section_screenshot(options: SectionScreenshotOptions):
    start_time = datetime.datetime.now().timestamp()
    page = await Browser.new_page(width=options.width, height=options.height)
    if options.content:
        await page.set_content(options.content)
    else:
        await page.goto(options.url, wait_until="networkidle")
    if options.css:
        await page.add_style_tag(content=options.css + Templates().custom_css())
    section, selected_ = await select_element(options.section, page)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    if options.counttime:
        await add_count_box(page, selected_, start_time)
    images = await make_screenshot(page, section)
    if not debug:
        await page.close()
    return ORJSONResponse(content=images)


@app.get("/source/")
async def source(request: Request):
    page = await Browser.new_page()
    try:
        url = request.query_params.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required")

        await page.goto(url, wait_until="networkidle")

        if url.endswith('.json'):
            _source = json.loads(await (await page.query_selector('pre')).inner_text())
        else:
            _source = await page.content()

        return ORJSONResponse(content=_source)
    finally:
        if not debug:
            await page.close()


if __name__ == "__main__":
    import uvicorn

    try:
        loop = asyncio.new_event_loop()
        logger.info(f"Server starting on {config['server']['host']}:{config['server']['port']}")
        loop.run_until_complete(uvicorn.run(app, host=config["server"]["host"], port=config["server"]["port"]))
    except KeyboardInterrupt:
        logger.info("Server stopped")
