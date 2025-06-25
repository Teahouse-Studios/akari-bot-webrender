import asyncio
import traceback
from typing import Literal

from playwright import async_api
from playwright.async_api import Playwright, Browser as BrowserProcess, BrowserContext, ViewportSize
from playwright_stealth import Stealth
from ..constants import base_user_agent, base_width, base_height

from .logger import LoggingLogger


class Browser:
    playwright: Playwright = None
    browser: BrowserProcess = None
    contexts: dict[str, BrowserContext] = {}
    stealth = Stealth(
        init_scripts_only=True
    )
    debug: bool = False
    logger: LoggingLogger
    user_agent = base_user_agent


    def __init__(self, debug: bool = False, log_path: str=None):
        self.debug = debug
        self.logger = LoggingLogger(debug=debug, logs_path=log_path)


    async def browser_init(self, browse_type: Literal["chrome", "firefox"]='chrome',
                           width: int = base_width,
                           height: int = base_height,
                           user_agent: str = user_agent):
        if not self.playwright and not self.browser:
            self.logger.info('Launching browser...')
            try:
                self.playwright = await async_api.async_playwright().start()
                _b = None
                if browse_type == "chrome":
                    _b = self.playwright.chromium
                elif browse_type == "firefox":
                    _b = self.playwright.firefox
                else:
                    raise ValueError("Unsupported browser type. Use 'chrome' or 'firefox'.")
                self.browser = await _b.launch(headless=not self.debug)
                while not self.browser:
                    await asyncio.sleep(1)
                self.contexts[f'{width}x{height}'] = await self.browser.new_context(user_agent=user_agent,
                                                                                    viewport=ViewportSize(width=width, height=height))
                await self.stealth.apply_stealth_async(self.contexts[f'{width}x{height}'])
                self.logger.info('Successfully launched browser.')
            except Exception as e:
                self.logger.error("Falied to launch browser.")
                self.logger.error(traceback.format_exc())


    async def close(self):
        await self.browser.close()


    async def new_page(self, width: int = base_width, height: int = base_height):
        if f'{width}x{height}' not in self.contexts:
            self.contexts[f'{width}x{height}'] = await self.browser.new_context(user_agent=self.user_agent,
                                                                                viewport=ViewportSize(width=width, height=height))
            await self.stealth.apply_stealth_async(self.contexts[f'{width}x{height}'])

        return await self.contexts[f'{width}x{height}'].new_page()