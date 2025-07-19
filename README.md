# AkariBot WebRender

此为小可的 WebRender 模块，主要用于渲染网页内容及浏览器代理请求等。

此模块已预置在小可的项目中，若你需要使用 WebRender 有关的内容，请在项目的 `config/webrender.toml` 处将 `enable_web_render` 设置为 `true`，然后使用 `playwright install --with-deps chromium` （或 `firefox`）安装浏览器及相关依赖即可（或是在配置中手动指定 `browser_executable_path` 路径以手动选择本地的浏览器）。

为了最大程度的网页兼容性，本项目仅支持 Chromium 内核和 Firefox 浏览器。

若你需要使用其进行二次开发，请使用你的包管理器安装 `akari-bot-webrender` 包，然后在你的代码中导入 `akari_bot_webrender` 模块。

或是作为远端部署的 WebRender 服务使用。你可以通过本项目根目录的 `run_server.py` 来启动一个 Web 服务器，在其它项目引入 `akari_bot_webrender` 后，配置 `remote_webrender_url` 指向该服务器地址即可。

若指定了 `remote_webrender_url`，则模块将在本地渲染失败时自动使用远程的 WebRender 服务进行渲染（或是配置 `remote_only` 项以强制指定使用远端渲染）。