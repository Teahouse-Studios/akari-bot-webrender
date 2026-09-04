import unittest

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from akari_bot_webrender.functions.main import section_screenshot_script


class SectionScreenshotEvaluateTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        try:
            self.browser = await self.playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            await self.playwright.stop()
            self.playwright = None
            self.skipTest(f"Chromium is unavailable: {exc}")
        self.page = await self.browser.new_page()

    async def asyncTearDown(self):
        if hasattr(self, "browser"):
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def evaluate_section(self, content: str, section: str):
        await self.page.set_content(content)
        await self.page.evaluate(
            section_screenshot_script,
            {"section": section, "elements_to_disable": []},
        )
        section_box = await self.page.query_selector(".bot-sectionbox")
        return await section_box.inner_text() if section_box else None

    async def test_manual_anchor_before_heading_selects_following_section(self):
        text = await self.evaluate_section(
            """
            <main>
              <div class="mw-heading"><h2 id="previous">Previous</h2></div>
              <p>Previous body</p>
              <p><span class="anchor" id="manual"></span></p>
              <div class="mw-heading"><h2 id="target">Target</h2></div>
              <p>Target body</p>
              <div class="mw-heading"><h2 id="next">Next</h2></div>
              <p>Next body</p>
            </main>
            """,
            "manual",
        )

        self.assertIn("Target", text)
        self.assertIn("Target body", text)
        self.assertNotIn("Previous body", text)
        self.assertNotIn("Next", text)

    async def test_manual_anchor_inside_heading_selects_that_section(self):
        text = await self.evaluate_section(
            """
            <main>
              <h2><span class="anchor" id="manual"></span>Target</h2>
              <p>Target body</p>
              <h2>Next</h2>
              <p>Next body</p>
            </main>
            """,
            "manual",
        )

        self.assertIn("Target", text)
        self.assertIn("Target body", text)
        self.assertNotIn("Next", text)

    async def test_manual_anchor_in_section_body_selects_containing_section(self):
        text = await self.evaluate_section(
            """
            <main>
              <h2 id="target">Target</h2>
              <p>Before anchor</p>
              <p><span class="anchor" id="manual"></span>After anchor</p>
              <h2 id="next">Next</h2>
              <p>Next body</p>
            </main>
            """,
            "manual",
        )

        self.assertIn("Target", text)
        self.assertIn("Before anchor", text)
        self.assertIn("After anchor", text)
        self.assertNotIn("Next", text)

    async def test_non_anchor_span_does_not_select_a_section(self):
        text = await self.evaluate_section(
            """
            <main>
              <span class="not-anchor" id="manual"></span>
              <h2>Target</h2>
              <p>Target body</p>
            </main>
            """,
            "manual",
        )

        self.assertIsNone(text)


if __name__ == "__main__":
    unittest.main()
