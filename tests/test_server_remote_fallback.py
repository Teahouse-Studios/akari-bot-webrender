import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from akari_bot_webrender.server import main as server_main


class ServerRemoteFallbackTest(unittest.TestCase):
    def setUp(self):
        self.original_config = server_main.config.copy()
        self.original_remote_url = server_main.webrender.remote_webrender_url
        self.original_remote_only = server_main.webrender.remote_only

    def tearDown(self):
        server_main.config.clear()
        server_main.config.update(self.original_config)
        server_main.webrender.remote_webrender_url = self.original_remote_url
        server_main.webrender.remote_only = self.original_remote_only

    def test_local_browser_init_failure_still_serves_remote_fallback(self):
        server_main.config["remote_only"] = False
        server_main.config["remote_webrender_url"] = "https://fallback.example/"
        server_main.webrender.remote_only = False
        server_main.webrender.remote_webrender_url = "https://fallback.example/"

        with (
            patch.object(server_main.webrender, "browser_init", AsyncMock(return_value=False)) as browser_init,
            patch.object(server_main.webrender, "browser_close", AsyncMock()) as browser_close,
            patch.object(server_main.webrender.browser, "check_status", AsyncMock(return_value=False)),
            patch.object(
                server_main.webrender, "_request_remote", AsyncMock(return_value=["remote-image"])
            ) as request_remote,
            TestClient(server_main.app) as client,
        ):
            response = client.post("/page/", json={"content": "fallback test"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["remote-image"])
        browser_init.assert_awaited_once()
        browser_close.assert_awaited_once()
        request_remote.assert_awaited_once()
        self.assertEqual(request_remote.await_args.args[0], "page")

    def test_remote_only_skips_local_browser_initialization(self):
        server_main.config["remote_only"] = True
        server_main.config["remote_webrender_url"] = "https://fallback.example/"
        server_main.webrender.remote_only = True
        server_main.webrender.remote_webrender_url = "https://fallback.example/"

        with (
            patch.object(server_main.webrender, "browser_init", AsyncMock()) as browser_init,
            patch.object(server_main.webrender, "browser_close", AsyncMock()),
            patch.object(
                server_main.webrender,
                "_request_remote",
                AsyncMock(return_value={"browser_initialized": True}),
            ),
            TestClient(server_main.app) as client,
        ):
            response = client.get("/status/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"browser_initialized": True})
        browser_init.assert_not_awaited()

    def test_incoming_fallback_request_is_not_forwarded_again(self):
        server_main.config["remote_only"] = False
        server_main.config["remote_webrender_url"] = "https://fallback.example/"
        server_main.webrender.remote_only = False
        server_main.webrender.remote_webrender_url = "https://fallback.example/"

        with (
            patch.object(server_main.webrender, "browser_init", AsyncMock(return_value=False)),
            patch.object(server_main.webrender, "browser_close", AsyncMock()),
            patch.object(server_main.webrender.browser, "check_status", AsyncMock(return_value=False)),
            patch("akari_bot_webrender.functions.main.httpx.AsyncClient") as client_class,
            TestClient(server_main.app) as client,
        ):
            response = client.post(
                "/page/",
                json={"content": "fallback loop test"},
                headers={"X-WebRender-Fallback-Hop": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json())
        client_class.assert_not_called()


if __name__ == "__main__":
    unittest.main()
