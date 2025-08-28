import os

elements_to_disable = [".notifications-placeholder",
                       ".top-ads-container",
                       ".fandom-sticky-header",
                       "div#WikiaBar",
                       "aside.page__right-rail",
                       ".n-modal-container",
                       "div#moe-float-toc-container",
                       "div#moe-draw-float-button",
                       "div#moe-global-header",
                       ".mys-wrapper",
                       "div#moe-open-in-app",
                       "div#age-gate",
                       ".va-variant-prompt",
                       ".va-variant-prompt-mobile",
                       ".mw-cookiewarning-container",
                       "div#summerNotificationOverlay"
                       ]


templates_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../templates"))

base_user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"

base_width = 720
base_height = 1280

max_screenshot_height = 8192
