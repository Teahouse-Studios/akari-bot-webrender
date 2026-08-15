import base64
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError

from akari_bot_webrender.constants import browser_user_agent
from akari_bot_webrender.functions.browser import Browser
from akari_bot_webrender.functions.main import WebRender
from akari_bot_webrender.functions.options import (
    ElementScreenshotOptions,
    LegacyScreenshotOptions,
    PageScreenshotOptions,
    SectionScreenshotOptions,
    SourceOptions,
)


class BrowserCompatibilityTest(unittest.IsolatedAsyncioTestCase):
    async def test_native_user_agent_and_normalized_locale_when_stealth_is_disabled(self):
        browser = Browser()
        page = MagicMock()
        context = MagicMock()
        context.new_page = AsyncMock(return_value=page)
        browser_process = MagicMock()
        browser_process.new_context = AsyncMock(return_value=context)
        browser.browser = browser_process

        result = await browser.new_page(width=800, height=600, locale="zh_cn", stealth=False)

        self.assertIs(result, page)
        context_options = browser_process.new_context.await_args.kwargs
        self.assertEqual(context_options["locale"], "zh-CN")
        self.assertEqual(context_options["viewport"], {"width": 800, "height": 600})
        self.assertNotIn("user_agent", context_options)

    async def test_stealth_context_preserves_existing_user_agent_behavior(self):
        browser = Browser()
        context = MagicMock()
        context.new_page = AsyncMock(return_value=MagicMock())
        browser_process = MagicMock()
        browser_process.new_context = AsyncMock(return_value=context)
        browser.browser = browser_process

        with patch("akari_bot_webrender.functions.browser.stealth_async", AsyncMock()):
            await browser.new_page(stealth=True)

        context_options = browser_process.new_context.await_args.kwargs
        self.assertEqual(context_options["user_agent"], browser_user_agent)

    async def test_make_screenshot_does_not_abort_late_network_requests(self):
        renderer = WebRender()
        page = MagicMock()
        page.evaluate = AsyncMock()
        page.route = AsyncMock()
        page.viewport_size = {"width": 720, "height": 1280}
        element = MagicMock()
        element.bounding_box = AsyncMock(return_value={"x": 0, "y": 0, "width": 100, "height": 100})
        element.screenshot = AsyncMock(return_value=b"image")

        result = await renderer.make_screenshot(page, element, output_type="png")

        self.assertEqual(result, [base64.b64encode(b"image").decode()])
        page.route.assert_not_awaited()


class PageLoadControlTest(unittest.IsolatedAsyncioTestCase):
    async def test_render_page_uses_configured_load_state_and_delay(self):
        renderer = WebRender()
        page = MagicMock()
        page.set_content = AsyncMock()
        page.add_style_tag = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.close = AsyncMock()
        renderer.browser.new_page = AsyncMock(return_value=page)

        async with renderer.render_page(
            content="<p>dynamic page</p>",
            wait_until="domcontentloaded",
            wait_after_load=2500,
        ):
            pass

        page.set_content.assert_awaited_once_with("<p>dynamic page</p>", wait_until="domcontentloaded")
        page.wait_for_timeout.assert_awaited_once_with(2500)

    async def test_screenshot_endpoints_forward_load_controls(self):
        def make_render_context(current_page):
            @asynccontextmanager
            async def render_context():
                yield current_page, 0.0

            return render_context()

        cases = [
            ("legacy_screenshot", LegacyScreenshotOptions(content="legacy")),
            ("page_screenshot", PageScreenshotOptions(content="page")),
            ("element_screenshot", ElementScreenshotOptions(content="element", element="body")),
            ("section_screenshot", SectionScreenshotOptions(content="section", section="body")),
        ]

        for method_name, options in cases:
            with self.subTest(method=method_name):
                options.wait_until = "domcontentloaded"
                options.wait_after_load = 4321
                renderer = WebRender()
                renderer.browser.check_status = AsyncMock(return_value=True)
                page = MagicMock()
                page.evaluate = AsyncMock()
                renderer.render_page = MagicMock(return_value=make_render_context(page))
                renderer.select_element_and_screenshot = AsyncMock(return_value=["image"])

                result = await getattr(renderer, method_name)(options)

                self.assertEqual(result, ["image"])
                render_options = renderer.render_page.call_args.kwargs
                self.assertEqual(render_options["wait_until"], "domcontentloaded")
                self.assertEqual(render_options["wait_after_load"], 4321)

    async def test_source_navigates_once_with_load_controls(self):
        renderer = WebRender()
        renderer.browser.check_status = AsyncMock(return_value=True)
        page = MagicMock()
        response = MagicMock(status=200)
        page.goto = AsyncMock(return_value=response)
        page.wait_for_timeout = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")

        @asynccontextmanager
        async def render_context():
            yield page, 0.0

        renderer.render_page = MagicMock(return_value=render_context())
        options = SourceOptions(
            url="https://example.com/",
            wait_until="load",
            wait_after_load=3000,
        )

        result = await renderer.source(options)

        self.assertEqual(result, "<html></html>")
        page.goto.assert_awaited_once_with("https://example.com/", wait_until="load")
        page.wait_for_timeout.assert_awaited_once_with(3000)

    def test_wait_after_load_is_bounded(self):
        with self.assertRaises(ValidationError):
            PageScreenshotOptions(wait_after_load=60001)


if __name__ == "__main__":
    unittest.main()
