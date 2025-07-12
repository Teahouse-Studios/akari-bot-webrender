import asyncio
from typing import Literal

from playwright import async_api
from playwright.async_api import Playwright, Browser as BrowserProcess, BrowserContext, ViewportSize
from playwright_stealth import stealth_async

from ..constants import base_user_agent, base_width, base_height
from .logger import LoggingLogger


class Browser:
    playwright: Playwright = None
    browser: BrowserProcess = None
    contexts: dict[str, BrowserContext] = {}
    debug: bool = False
    logger: LoggingLogger
    user_agent = base_user_agent

    def __init__(self, debug: bool = False, log_path: str = None):
        self.debug = debug
        self.logger = LoggingLogger(debug=debug, logs_path=log_path)

    async def browser_init(self, browse_type: Literal["chrome", "firefox"] = "chrome",
                           width: int = base_width,
                           height: int = base_height,
                           user_agent: str = user_agent,
                           locale: str = "zh_cn"):
        if not self.playwright and not self.browser:
            self.logger.info("Launching browser...")
            try:
                self.playwright = await async_api.async_playwright().start()
                _b = None
                if browse_type == "chrome":
                    _b = self.playwright.chromium
                elif browse_type == "firefox":
                    _b = self.playwright.firefox
                else:
                    raise ValueError(
                        "Unsupported browser type. Use \"chrome\" or \"firefox\".")
                self.browser = await _b.launch(headless=not self.debug)
                while not self.browser:
                    self.logger.info("Waiting for browser to launch...")
                    await asyncio.sleep(1)
                self.contexts[f"{width}x{height}_{locale}"] = await self.browser.new_context(user_agent=user_agent,
                                                                                             viewport=ViewportSize(
                                                                                                 width=width, height=height),
                                                                                             locale=locale)
                self.logger.success("Successfully launched browser.")
            except Exception:
                self.logger.exception("Failed to launch browser.")

    async def close(self):
        await self.browser.close()

    async def new_page(self, width: int = base_width, height: int = base_height, locale: str = "zh_cn"):
        if f"{width}x{height}" not in self.contexts:
            self.contexts[f"{width}x{height}_{locale}"] = await self.browser.new_context(user_agent=self.user_agent,
                                                                                         viewport=ViewportSize(
                                                                                             width=width, height=height),
                                                                                         locale=locale)
        page = await self.contexts[f"{width}x{height}_{locale}"].new_page()
        await stealth_async(page)
        return page
