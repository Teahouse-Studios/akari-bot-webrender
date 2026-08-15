# AkariBot WebRender

此为[小可](https://github.com/Teahouse-Studios/akari-bot)的 WebRender 模块，主要用于渲染网页内容及浏览器代理请求等。

此模块已预置在小可的项目中，若你需要使用 WebRender 有关的内容，请在项目的 `config/webrender.toml` 处将 `enable_web_render` 设置为 `true`，然后使用 `playwright install --with-deps chromium` （或 `firefox`）安装浏览器及相关依赖即可（或是在配置中手动指定 `browser_executable_path` 路径以手动选择本地的浏览器）。

为了最大程度的网页兼容性，本项目仅支持 Chromium 内核和 Firefox 浏览器。

若你需要使用其进行二次开发，请使用你的包管理器安装 `akari-bot-webrender` 包，然后在你的代码中导入 `akari_bot_webrender` 模块。

或是作为远端部署的 WebRender 服务使用。你可以通过本项目根目录的 `run_server.py` 来启动一个 Web 服务器，在其它项目引入 `akari_bot_webrender` 后，配置 `remote_webrender_url` 指向该服务器地址即可。

若指定了 `remote_webrender_url`，则模块将在本地渲染失败时自动使用远程的 WebRender 服务进行渲染（或是配置 `remote_only` 项以强制指定使用远端渲染）。

## 独立部署的远端回退

通过 `run_server.py` 或 Docker 独立部署时，也可以在 `config.json` 的 `server` 中配置远端 WebRender：

```json
{
  "server": {
    "remote_webrender_url": "https://fallback.example.com/webrender/",
    "remote_only": false,
    "remote_timeout": 30
  }
}
```

- `remote_webrender_url`：远端 WebRender API 的 HTTP(S) 根地址，可以包含反向代理路径；末尾的 `/` 可省略，不应包含查询参数或 URL fragment。
- `remote_only`：为 `false` 时优先使用本地浏览器，本地浏览器未启动、处理抛出异常或没有返回结果时请求远端；为 `true` 时跳过本地浏览器初始化并将所有操作交给远端。
- `remote_timeout`：每次远端请求的超时时间，单位为秒，必须大于 `0`。

Docker 和其他容器化部署可以使用环境变量覆盖配置：

```bash
docker run --rm \
  -e WEBRENDER_REMOTE_URL=https://fallback.example.com/webrender/ \
  -e WEBRENDER_REMOTE_ONLY=false \
  -e WEBRENDER_REMOTE_TIMEOUT=30 \
  -p 127.0.0.1:15551:15551 \
  akari-bot-webrender:latest
```

`remote_only=true` 时必须同时提供远端 URL。服务会为回退请求添加单跳标记，远端实例仍会先尝试自己的本地浏览器，但不会在失败后继续转发，从而避免自指或 A→B→A 配置形成递归请求。建议仍将回退关系配置为单向，并确保远端目标具备可用的本地渲染能力。远端地址属于受信任的服务端配置；跨公网使用时建议通过 HTTPS、鉴权反向代理或私有网络连接。

## Docker 有头模式

项目的 Dockerfile 提供三种构建 target：

| Target | 建议镜像 tag | 用途 |
| --- | --- | --- |
| `headless`（也是默认 target） | `latest` 或版本号 | 无头模式，用于常规部署 |
| `headed` | `headed` 或 `<version>-headed` | 在虚拟 X Server 中运行有头 Chromium，不提供完整桌面 |
| `desktop` | `desktop` 或 `<version>-desktop` | 有头 Chromium + 完整 XFCE + noVNC，用于需要完整桌面会话的网站兼容、观察和人工调试 |

为减小镜像体积，`headless` 只包含 Chromium Headless Shell，`headed` 和 `desktop` 只包含完整 Chromium。不要通过 `WEBRENDER_HEADLESS` 把已构建镜像切换成另一种模式；需要哪种浏览器形态就使用对应 target。字体覆盖在三种镜像中均完整保留。

Target 是 Dockerfile 中的构建阶段，tag 是构建后的镜像名称，两者不会自动绑定。例如：

```bash
docker build --target headed -t akari-bot-webrender:headed .
docker build --target desktop -t akari-bot-webrender:desktop .
```

### Docker Compose 示例

仓库根目录的 `docker-compose.yml` 使用 profiles 提供三种运行模式，每次按需启动其中一种：

```bash
# API: http://127.0.0.1:15551
docker compose --profile headless up --build -d

# API: http://127.0.0.1:15552
docker compose --profile headed up --build -d

# API: http://127.0.0.1:15553
docker compose --profile desktop up --build -d
```

desktop 默认不启用 noVNC。需要通过浏览器访问桌面时，先在项目根目录创建 `.env`：

```dotenv
ENABLE_NOVNC=1
NOVNC_PASSWORD=replace-with-a-strong-password
```

然后启动 desktop profile，并访问 `http://127.0.0.1:6080/vnc.html`。停止对应 profile：

```bash
docker compose --profile desktop down
```

Compose 示例也支持独立部署的远端回退参数，可在 `.env` 中设置：

```dotenv
WEBRENDER_REMOTE_URL=https://fallback.example.com/webrender/
WEBRENDER_REMOTE_ONLY=false
WEBRENDER_REMOTE_TIMEOUT=30
```

可以通过 `WEBRENDER_HEADLESS_PORT`、`WEBRENDER_HEADED_PORT`、`WEBRENDER_DESKTOP_PORT` 和 `NOVNC_PORT` 修改宿主机端口。所有示例端口默认仅绑定到 `127.0.0.1`。

### 有头截图服务

`headed` 镜像对外提供 WebRender API，默认端口为 `15551`。Chromium 的桌面窗口仅存在于容器内的虚拟显示器中。

```bash
docker run --rm \
  --shm-size=1g \
  -e WEBRENDER_HOST=0.0.0.0 \
  -p 127.0.0.1:15551:15551 \
  akari-bot-webrender:headed
```

健康检查和一次本地 HTML 截图请求：

```bash
curl --fail http://127.0.0.1:15551/status/
curl --fail \
  -H 'Content-Type: application/json' \
  -d '{"content":"<!doctype html><h1>WebRender headed</h1>","output_type":"png"}' \
  http://127.0.0.1:15551/page/
```

`/page/` 和其他截图接口的返回值仍是 **base64 字符串数组**；长页面可能会按最大截图高度分成多张。有头模式只改变浏览器的运行方式，`page.screenshot()` 获取的仍是网页内容，不包含浏览器标题栏、窗口边框或桌面。需要整个桌面画面时，应另外使用 X11 屏幕采集工具。

对于 Turnstile、延迟 iframe 或其他动态页面，可以关闭 stealth 并显式设置页面加载策略：

```bash
curl --fail \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/","stealth":false,"wait_until":"load","wait_after_load":5000,"output_type":"png"}' \
  http://127.0.0.1:15551/page/
```

`stealth=false` 时 WebRender 不再覆盖 Chromium 的 User-Agent，由浏览器使用与自身版本匹配的原生 UA 和 Client Hints。`wait_until` 支持 `commit`、`domcontentloaded`、`load` 和 `networkidle`，为兼容现有调用默认仍使用 `networkidle`；`wait_after_load` 是页面达到该状态后的额外等待时间，单位为毫秒，范围为 `0`–`60000`，默认值为 `0`。截图阶段不会再中止页面的后续网络请求，因此异步脚本、XHR、iframe 和字体仍可继续加载。

### 完整桌面与 noVNC

`desktop` target 启动完整 XFCE 会话，而不是仅启动一个轻量窗口管理器，适合用于规避部分依赖正常桌面会话、DBus、窗口管理器等环境的网站兼容问题。网页仍可能通过浏览器指纹、WebGL、语言、时区等信号识别自动化环境，因此完整桌面不是通用的反检测保证。

该 target 支持在 `6080` 端口提供 noVNC 页面。为避免意外暴露桌面，noVNC 默认关闭；启用时必须同时提供密码。下面的示例用只读挂载的密码文件，避免把密码直接写入命令行参数：

```bash
printf '%s' 'replace-with-a-strong-password' > /tmp/webrender-novnc-password
chmod 600 /tmp/webrender-novnc-password

docker run --rm \
  --shm-size=1g \
  -e WEBRENDER_HOST=0.0.0.0 \
  -e ENABLE_NOVNC=1 \
  -e NOVNC_LISTEN=0.0.0.0 \
  -e NOVNC_PASSWORD_FILE=/run/secrets/novnc-password \
  -v /tmp/webrender-novnc-password:/run/secrets/novnc-password:ro \
  -p 127.0.0.1:15551:15551 \
  -p 127.0.0.1:6080:6080 \
  akari-bot-webrender:desktop
```

在本机访问 `http://127.0.0.1:6080/vnc.html` 即可观察桌面。也可以用 `NOVNC_PASSWORD` 环境变量传入密码，但密码文件更适合长期部署。noVNC/VNC 可以读取并控制浏览器会话，不应将 `6080` 或底层 VNC 端口直接暴露到公网。远程使用时应通过带 HTTPS 和身份认证的反向代理、VPN 或 SSH 隧道访问，并限制可访问的网络范围。
