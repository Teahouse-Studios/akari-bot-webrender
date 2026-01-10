import asyncio
from pathlib import Path
from typing import Literal

from playwright import async_api
from playwright.async_api import Playwright, Browser as BrowserProcess, BrowserContext, ViewportSize
from playwright_stealth import stealth_async

from ..constants import browser_user_agent, base_user_agent, base_width, base_height
from .logger import LoggingLogger


class Browser:
    playwright: Playwright | None = None
    browser: BrowserProcess | None = None
    contexts: dict[str, BrowserContext] = {}
    debug: bool = False
    export_logs: bool = False
    logs_path = None
    logger: LoggingLogger

    def __init__(self, debug: bool = False, export_logs: bool = False, logs_path: str | Path = None):
        self.debug = debug
        if export_logs:
            self.logs_path = logs_path
        self.logger = LoggingLogger(debug=debug, logs_path=logs_path)

    async def browser_init(self,
                           browse_type: Literal["chrome",
                                                "chromium", "firefox"] = "chromium",
                           width: int = base_width,
                           height: int = base_height,
                           locale: str = "zh_cn",
                           executable_path: str | Path | None = None):
        if not self.playwright and not self.browser:
            self.logger.info("Launching browser...")
            try:
                _p = async_api.async_playwright()
                self.playwright = await _p.start()
                _b = None
                if browse_type in ["chrome", "chromium"]:
                    _b = self.playwright.chromium
                elif browse_type == "firefox":
                    _b = self.playwright.firefox
                else:
                    raise ValueError(
                        "Unsupported browser type. Use \"chromium\" or \"firefox\".")
                self.browser = await _b.launch(headless=not self.debug,
                                               executable_path=executable_path)
                while not self.browser:
                    self.logger.info("Waiting for browser to launch...")
                    await asyncio.sleep(1)
                ctx_key = f"{width}x{height}_{locale}"
                self.contexts[ctx_key] = await self.browser.new_context(
                    user_agent=base_user_agent,
                    viewport=ViewportSize(width=width, height=height),
                    locale=locale)
                self.logger.success("Successfully launched browser.")
                return True
            except Exception:
                self.logger.exception("Failed to launch browser.")
                return False
        else:
            self.logger.info("Browser is already initialized.")
            return True

    async def close(self):
        for context in self.contexts.values():
            await context.close()
        self.contexts = {}
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = None
        self.playwright = None
        self.logger.info("Browser closed.")
        return True

    async def new_page(self,
                       width: int = base_width,
                       height: int = base_height,
                       locale: str = "zh_cn",
                       stealth: bool = True):
        ctx_key = f"{width}x{height}_{locale}{"_stealth" if stealth else ""}"
        if ctx_key not in self.contexts:
            self.contexts[ctx_key] = await self.browser.new_context(
                user_agent=browser_user_agent if stealth else base_user_agent,
                viewport=ViewportSize(width=width, height=height),
                locale=locale
            )
        page = await self.contexts[ctx_key].new_page()
        if stealth:
            await stealth_async(page)
        return page

    async def check_status(self):
        if self.playwright and self.browser:
            return True
        return False
