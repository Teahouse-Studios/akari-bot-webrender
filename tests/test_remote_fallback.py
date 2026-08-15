import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from akari_bot_webrender.functions.main import WebRender, remote_fallback_hop, webrender_fallback


class DummyOptions:
    def model_dump(self, mode="python", exclude_none=False):
        return {"content": "fallback test"}


class DummyBrowser:
    def __init__(self, initialized=True):
        self.check_status = AsyncMock(return_value=initialized)


class DummyWebRender:
    def __init__(self, *, initialized=True, remote_url="https://fallback.example/", remote_only=False):
        self.browser = DummyBrowser(initialized=initialized)
        self.remote_webrender_url = remote_url
        self.remote_only = remote_only
        self.logger = MagicMock()
        self._request_remote = AsyncMock(return_value=["remote-result"])
        self.local_calls = 0

    @webrender_fallback
    async def page_screenshot(self, options):
        self.local_calls += 1
        raise RuntimeError("local rendering failed")

    @webrender_fallback
    async def source(self, options):
        self.local_calls += 1


class RemoteFallbackTest(unittest.IsolatedAsyncioTestCase):
    def test_remote_url_normalization_preserves_encoded_path(self):
        renderer = WebRender(remote_webrender_url="https://fallback.example/a%2Fb")

        self.assertEqual(renderer.remote_webrender_url, "https://fallback.example/a%2Fb/")

    async def test_local_exception_uses_page_endpoint(self):
        renderer = DummyWebRender()
        options = DummyOptions()

        result = await renderer.page_screenshot(options)

        self.assertEqual(result, ["remote-result"])
        self.assertEqual(renderer.local_calls, 1)
        renderer._request_remote.assert_awaited_once_with("page", options)

    async def test_empty_local_result_uses_remote(self):
        renderer = DummyWebRender()
        options = DummyOptions()

        result = await renderer.source(options)

        self.assertEqual(result, ["remote-result"])
        renderer._request_remote.assert_awaited_once_with("source", options)

    async def test_uninitialized_browser_uses_remote(self):
        renderer = DummyWebRender(initialized=False)
        options = DummyOptions()

        result = await renderer.page_screenshot(options)

        self.assertEqual(result, ["remote-result"])
        self.assertEqual(renderer.local_calls, 0)
        renderer._request_remote.assert_awaited_once_with("page", options)

    async def test_remote_only_skips_local_browser(self):
        renderer = DummyWebRender(initialized=False, remote_only=True)
        options = DummyOptions()

        result = await renderer.page_screenshot(options)

        self.assertEqual(result, ["remote-result"])
        self.assertEqual(renderer.local_calls, 0)
        renderer.browser.check_status.assert_not_awaited()
        renderer._request_remote.assert_awaited_once_with("page", options)

    async def test_no_remote_keeps_failure_local(self):
        renderer = DummyWebRender(remote_url=None)

        result = await renderer.page_screenshot(DummyOptions())

        self.assertIsNone(result)
        renderer._request_remote.assert_not_awaited()

    async def test_remote_request_uses_json_and_supports_empty_status_options(self):
        response = MagicMock(status_code=200, text='{"browser_initialized":true}')
        response.read.return_value = b'{"browser_initialized":true}'
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=response)
        renderer = WebRender(remote_webrender_url="https://fallback.example/api", remote_timeout=12)

        with patch("akari_bot_webrender.functions.main.httpx.AsyncClient", return_value=client) as client_class:
            result = await renderer._request_remote("status", None)

        self.assertEqual(result, {"browser_initialized": True})
        client_class.assert_called_once_with(timeout=12, follow_redirects=True)
        client.post.assert_awaited_once_with(
            "https://fallback.example/api/status/",
            json={},
            headers={"X-WebRender-Fallback-Hop": "1"},
        )

    async def test_remote_request_is_not_forwarded_twice(self):
        renderer = WebRender(remote_webrender_url="https://fallback.example/")
        token = remote_fallback_hop.set(1)
        try:
            with patch("akari_bot_webrender.functions.main.httpx.AsyncClient") as client_class:
                result = await renderer._request_remote("page", DummyOptions())
        finally:
            remote_fallback_hop.reset(token)

        self.assertIsNone(result)
        client_class.assert_not_called()

    async def test_remote_request_log_redacts_url_credentials(self):
        response = MagicMock(status_code=200, text="[]")
        response.read.return_value = b"[]"
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(return_value=response)
        renderer = WebRender(remote_webrender_url="https://user:secret@fallback.example/api")
        renderer.logger = MagicMock()

        with patch("akari_bot_webrender.functions.main.httpx.AsyncClient", return_value=client):
            await renderer._request_remote("status", None)

        log_message = renderer.logger.info.call_args.args[0]
        self.assertNotIn("user", log_message)
        self.assertNotIn("secret", log_message)
        self.assertEqual(log_message, "Trying remote WebRender: https://fallback.example/api/status/")


if __name__ == "__main__":
    unittest.main()
