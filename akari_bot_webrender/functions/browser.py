from pathlib import Path
from typing import Literal

from playwright import async_api
from playwright.async_api import Browser as BrowserProcess
from playwright.async_api import BrowserContext, Playwright, ViewportSize
from playwright_stealth import stealth_async

from ..constants import base_height, base_width, browser_user_agent
from .logger import LoggingLogger


def normalize_locale(locale: str) -> str:
    parts = locale.replace("_", "-").split("-")
    normalized = []
    for index, part in enumerate(parts):
        if index == 0:
            normalized.append(part.lower())
        elif len(part) == 4 and part.isalpha():
            normalized.append(part.title())
        elif len(part) == 2 and part.isalpha():
            normalized.append(part.upper())
        else:
            normalized.append(part)
    return "-".join(normalized)


class Browser:
    def __init__(
        self,
        debug: bool = False,
        export_logs: bool = False,
        logs_path: str | Path | None = None,
        headless: bool | None = None,
    ):
        self.playwright: Playwright | None = None
        self.browser: BrowserProcess | None = None
        self.contexts: dict[str, BrowserContext] = {}
        self.debug = debug
        # Before ``headless`` was configurable, debug mode also selected headed mode.
        self.headless = not debug if headless is None else headless
        self.export_logs = export_logs
        self.logs_path = None
        if export_logs:
            self.logs_path = logs_path
        self.logger = LoggingLogger(debug=debug, logs_path=logs_path)

    async def browser_init(
        self,
        browser_type: Literal["chrome", "chromium", "firefox"] = "chromium",
        width: int = base_width,
        height: int = base_height,
        locale: str = "zh_cn",
        executable_path: str | Path | None = None,
    ):
        if self.browser and self.browser.is_connected():
            self.logger.info("Browser is already initialized.")
            return True

        if self.playwright or self.browser:
            self.logger.warning("Cleaning up stale browser state before relaunching.")
            await self.close()

        self.logger.info("Launching browser...")
        try:
            _p = async_api.async_playwright()
            self.playwright = await _p.start()
            _b = None
            if browser_type in ["chrome", "chromium"]:
                _b = self.playwright.chromium
            elif browser_type == "firefox":
                _b = self.playwright.firefox
            else:
                raise ValueError('Unsupported browser type. Use "chromium" or "firefox".')
            self.browser = await _b.launch(headless=self.headless, executable_path=executable_path)
            self.logger.success("Successfully launched browser.")
            return True
        except Exception:
            self.logger.exception("Failed to launch browser.")
            await self.close()
            return False

    async def close(self):
        for context in list(self.contexts.values()):
            try:
                await context.close()
            except Exception:
                self.logger.exception("Failed to close browser context.")
        self.contexts = {}
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                self.logger.exception("Failed to close browser process.")
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                self.logger.exception("Failed to stop Playwright.")
        self.browser = None
        self.playwright = None
        self.logger.info("Browser closed.")
        return True

    async def new_page(
        self, width: int = base_width, height: int = base_height, locale: str = "zh_cn", stealth: bool = True
    ):
        normalized_locale = normalize_locale(locale)
        ctx_key = f"{width}x{height}_{normalized_locale}{'_stealth' if stealth else ''}"
        if self.browser and ctx_key not in self.contexts:
            context_options = {
                "viewport": ViewportSize(width=width, height=height),
                "locale": normalized_locale,
            }
            if stealth:
                context_options["user_agent"] = browser_user_agent
            self.contexts[ctx_key] = await self.browser.new_context(**context_options)
        page = await self.contexts[ctx_key].new_page()
        if stealth:
            await stealth_async(page)
        return page

    async def check_status(self):
        return bool(self.playwright and self.browser and self.browser.is_connected())
