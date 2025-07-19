from contextlib import asynccontextmanager

import orjson as json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse

from ..functions.exceptions import ElementNotFound, RequiredURL
from ..functions.main import WebRender
from ..functions.options import LegacyScreenshotOptions, PageScreenshotOptions, ElementScreenshotOptions, \
    SectionScreenshotOptions, SourceOptions

with open('config.json', 'r') as f:
    config = json.loads(f.read())['server']


webrender = WebRender(debug=config['debug'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await webrender.browser_init(browse_type=config["browser_type"], executable_path=config["executable_path"] if config["executable_path"] else None)
        yield
    finally:
        await webrender.browser_close()

app = FastAPI(lifespan=lifespan)


@app.post("/legacy_screenshot/")
async def legacy_screenshot(options: LegacyScreenshotOptions):
    try:
        images = await webrender.legacy_screenshot(options)
    except ElementNotFound:
        raise HTTPException(status_code=404, detail="Element not found")
    return ORJSONResponse(content=images)


@app.post("/page/")
async def page_screenshot(options: PageScreenshotOptions):
    screenshot = await webrender.page_screenshot(options)
    return ORJSONResponse(content=screenshot)


@app.post("/element_screenshot/")
async def element_screenshot(options: ElementScreenshotOptions):
    try:
        images = await webrender.element_screenshot(options)
    except ElementNotFound:
        raise HTTPException(status_code=404, detail="Element not found")
    return ORJSONResponse(content=images)


@app.post("/section_screenshot/")
async def section_screenshot(options: SectionScreenshotOptions):
    try:
        images = await webrender.section_screenshot(options)
    except ElementNotFound:
        raise HTTPException(status_code=404, detail="Section not found")
    return ORJSONResponse(content=images)


@app.post("/source/")
async def source(options: SourceOptions):
    try:
        source = await webrender.source(options)
    except RequiredURL:
        raise HTTPException(
            status_code=400, detail="URL parameter is required")
    return ORJSONResponse(content=source)


def run():
    import uvicorn  # noqa

    try:
        webrender.logger.info(f"Server starting on {
                              config['host']}:{config['port']}")
        uvicorn.run(app, host=config["host"], port=config["port"])
    except KeyboardInterrupt:
        webrender.logger.info("Server stopped")
