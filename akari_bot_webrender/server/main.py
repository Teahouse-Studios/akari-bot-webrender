import os
from contextlib import asynccontextmanager
from pathlib import Path

import orjson as json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, ORJSONResponse

from ..functions.exceptions import ElementNotFound, RequiredURL
from ..functions.main import WebRender, remote_fallback_header, remote_fallback_hop
from ..functions.options import (
    ElementScreenshotOptions,
    LegacyScreenshotOptions,
    PageScreenshotOptions,
    RawOptions,
    SectionScreenshotOptions,
    SourceOptions,
    StatusOptions,
)

with open("config.json", "r") as f:
    config = json.loads(f.read())["server"]


def env_bool(name: str, default: bool | None = None) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of: 1/0, true/false, yes/no, on/off")


def env_value(name: str, default=None):
    value = os.getenv(name)
    return default if value is None else value


config["host"] = env_value("WEBRENDER_HOST", config.get("host", "127.0.0.1"))
config["port"] = int(env_value("WEBRENDER_PORT", config.get("port", 15551)))
config["debug"] = env_bool("WEBRENDER_DEBUG", config.get("debug", False))
config["headless"] = env_bool("WEBRENDER_HEADLESS", config.get("headless"))
config["keep_pages_open"] = env_bool("WEBRENDER_KEEP_PAGES_OPEN", config.get("keep_pages_open"))
config["export_logs"] = env_bool("WEBRENDER_EXPORT_LOGS", config.get("export_logs", False))
config["browser_type"] = env_value("WEBRENDER_BROWSER_TYPE", config.get("browser_type", "chromium"))
config["executable_path"] = env_value("WEBRENDER_EXECUTABLE_PATH", config.get("executable_path")) or None
remote_webrender_url = env_value("WEBRENDER_REMOTE_URL", config.get("remote_webrender_url"))
config["remote_webrender_url"] = remote_webrender_url.strip() if remote_webrender_url else None
config["remote_only"] = env_bool("WEBRENDER_REMOTE_ONLY", config.get("remote_only", False))
config["remote_timeout"] = float(env_value("WEBRENDER_REMOTE_TIMEOUT", config.get("remote_timeout", 30)))

if config["remote_only"] and not config["remote_webrender_url"]:
    raise ValueError("remote_only requires remote_webrender_url or WEBRENDER_REMOTE_URL")


webrender = WebRender(
    debug=config["debug"],
    headless=config["headless"],
    keep_pages_open=config["keep_pages_open"],
    export_logs=config["export_logs"],
    remote_webrender_url=config["remote_webrender_url"],
    remote_only=config["remote_only"],
    remote_timeout=config["remote_timeout"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config["remote_only"]:
        webrender.logger.info("Remote-only mode enabled; skipping local browser initialization.")
    else:
        initialized = await webrender.browser_init(
            browser_type=config["browser_type"], executable_path=config["executable_path"]
        )
        if not initialized:
            if config["remote_webrender_url"]:
                webrender.logger.warning("Local browser initialization failed; continuing with remote fallback only.")
            else:
                raise RuntimeError("Failed to initialize WebRender browser")
    try:
        yield
    finally:
        await webrender.browser_close()


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def remote_fallback_hop_middleware(request: Request, call_next):
    try:
        hop = max(0, int(request.headers.get(remote_fallback_header, "0")))
    except ValueError:
        hop = 0
    token = remote_fallback_hop.set(hop)
    try:
        return await call_next(request)
    finally:
        remote_fallback_hop.reset(token)


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
        source_content = await webrender.source(options)
    except RequiredURL:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    return ORJSONResponse(content=source_content)


@app.post("/get_raw/")
async def get_raw(options: RawOptions):
    try:
        result = await webrender.get_raw(options)
    except RequiredURL:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    return ORJSONResponse(content=result)


@app.get("/status/")
@app.post("/status/")
async def status(options: StatusOptions | None = None):
    return ORJSONResponse(content=await webrender.status(options))


@app.get("/favicon.ico")
async def favicon():
    return FileResponse((Path(__file__).parent / "favicon.ico").resolve())


def run():
    import uvicorn

    try:
        webrender.logger.info(f"Server starting on {config['host']}:{config['port']}")
        uvicorn.run(app, host=config["host"], port=config["port"])
    except KeyboardInterrupt:
        webrender.logger.info("Server stopped")
