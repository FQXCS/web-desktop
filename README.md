# WebDesktop 桌面启动器

一个 Windows 桌面 GUI 程序：点击桌面图标启动后打开窗口，在后台执行 web 服务的启动命令；
服务启动期间窗口显示「正在启动服务」等待动画，服务就绪后自动跳转到配置的地址
（如 `http://127.0.0.1:3080`）。浏览器内核使用系统自带 **Edge（WebView2）**。

## 功能特性

- 后台启动任意 web 服务命令（可配置），无需命令行窗口
- 等待期间展示加载动画与计时，就绪后自动跳转目标地址
- 配置文件保存在 `~/.WebDesktop/config.json`，首次运行时自动创建
- 首次运行（或启动时发现任意参数为空）首页进入图形化配置页面：全部参数必填，
  除 `web_command` / `web_url` 外的高级设置默认折叠，保存后自动重启
- 启动失败 / 进程退出 / 超时均展示错误页，附服务日志尾部，支持「重试」「打开配置」
- 跳转到目标网页后，右键弹出内置自定义菜单（白底黑字：刷新页面 / 复制 / 粘贴 /
  打开配置页），替换页面自身右键菜单，并强制启用文本选择便于复制
- 从右键菜单进入的配置页以全屏遮罩覆盖在目标网页上：不刷新页面、服务保持运行，
  右上角「✕」（或 Esc）关闭后目标网页原样保留；错误页进入的配置页同样带「✕」，
  关闭后返回错误页；首次启动的配置页无此按钮
- 应用启动后常驻系统托盘（右下角）：左键单击托盘图标打开主窗口；右键菜单可
  「打开主窗口」或「退出程序」
- 关闭窗口行为可在配置页设置：「最小化到系统托盘」（窗口隐藏、程序与服务继续
  后台运行，从托盘恢复或退出）或「退出程序」（关闭窗口即结束进程）
- 退出程序时自动清理服务进程树（可配置，最小化到托盘期间服务保持运行）
- 单文件 exe 分发，双击即用

## 目录结构

```
web-desktop/
├── main.py                # 程序入口
├── app/
│   ├── config.py          # 配置管理（~/.WebDesktop 下配置文件的创建/加载/校验/保存）
│   ├── controller.py      # 应用控制器（服务编排、页面切换、配置保存与重启）
│   ├── service.py         # web 服务子进程管理（启动/健康检查/日志/清理）
│   ├── pages.py           # 内置等待页、错误页与配置页 HTML
│   ├── tray.py            # 系统托盘（纯 Win32 API 实现：托盘图标与右键菜单）
│   ├── ui.py              # pywebview 窗口与 js 接口
│   └── paths.py           # 路径工具（兼容打包运行）
├── build.ps1              # 打包脚本（PyInstaller）
├── create_shortcut.ps1    # 桌面快捷方式脚本
└── requirements.txt       # Python 依赖
```

配置文件不随项目分发，首次运行时自动在用户家目录创建：
`~/.WebDesktop/config.json`（Windows 上即 `C:\Users\<用户名>\.WebDesktop\config.json`）。

其中 `~` 表示用户家目录，**从环境变量解析**：Windows 读取 `USERPROFILE`
（缺失时用 `HOMEDRIVE` + `HOMEPATH` 拼接），Linux/macOS 读取 `HOME`。

## 配置文件说明（~/.WebDesktop/config.json）

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `web_command` | 服务启动命令（完整命令行字符串，含空格的路径用双引号包裹） | 无默认值，必填 |
| `web_url` | 服务就绪后跳转的地址（也是健康检查地址） | 无默认值，必填 |
| `working_dir` | 服务进程工作目录 | `~/.WebDesktop/working` |
| `log_dir` | 日志目录（服务日志与程序日志） | `~/.WebDesktop/log` |
| `startup_timeout` | 等待服务就绪的超时秒数 | `60` |
| `check_interval` | 健康检查轮询间隔（秒） | `0.5` |
| `check_timeout` | 单次健康检查超时（秒） | `2` |
| `window_title` | 窗口标题 | `Web 桌面启动器` |
| `window_size` | 窗口尺寸 `[宽, 高]` | `[1200, 800]` |
| `show_console` | 是否显示服务控制台窗口（调试用） | `false` |
| `kill_on_exit` | 退出程序时是否终止服务进程 | `true` |
| `close_action` | 关闭窗口动作：`minimize_to_tray` 最小化到系统托盘 / `exit` 退出程序 | `minimize_to_tray` |

配置页面说明：

- 首次运行（配置文件不存在）或启动时发现任意参数为空，首页即进入配置页面
- `web_command` 与 `web_url` 直接展示；其余参数为高级设置，默认折叠
- 全部参数均为必填项；除 `web_command` / `web_url` 外均有默认值
- 点击「保存」校验通过后自动重启应用并进入正常启动流程
- 服务启动失败时可在错误页点击「打开配置」修改配置
- 从目标网页右键菜单进入的配置页是覆盖在网页上的遮罩（不刷新页面，服务保持运行），
  错误页进入的配置页为整页切换；两者均显示右上角「✕」按钮，点击关闭并返回来源
  页面；首次运行进入的配置页不显示该按钮

示例：启动 Node 服务并跳转 3080 端口：

```json
{
  "web_command": "node server.js",
  "web_url": "http://127.0.0.1:3080",
  "working_dir": "D:\\my-web-service"
}
```

> 提示：`web_command` 按 Windows 命令行规则解析，可执行文件路径含空格时请用
> 双引号包裹，例如 `"\"D:\\Program Files\\nodejs\\node.exe\" server.js"`。

## 运行方式（源码）

```powershell
pip install -r requirements.txt
python main.py
```

## 打包为 exe

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1   # 创建桌面快捷方式
```

打包产物：`dist\WebDesktop.exe`。配置文件无需随包分发，首次运行时自动创建。

应用图标使用项目根目录的 `app.ico`：打包时嵌入 exe（文件图标、桌面快捷方式图标），
运行时窗口标题栏与任务栏图标同样来源于它；替换图标只需替换 `app.ico` 后重新打包。

## 常见问题

- **WebView2 运行时缺失**：Windows 11 已内置；Windows 10 需安装
  [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。
- **服务启动失败**：错误页会展示服务日志末尾 30 行，可点击「打开配置」修改
  `web_command` 等参数，也可临时将 `show_console` 改为 `true` 观察服务真实输出。
- **一直等待不跳转**：确认 `web_url` 与服务的实际监听端口一致；健康检查以 HTTP
  响应为准，若服务不是 HTTP 协议请调整检查方式。
- **日志位置**：默认在 `~/.WebDesktop/log\` 目录下：`app.log`（程序日志）、
  `web_service.log`（服务日志），可通过 `log_dir` 修改。
- **如何恢复默认配置**：退出程序后删除 `~/.WebDesktop/config.json`，
  下次启动会自动重建并进入配置页面。

## DeepSeek Harness 鲸鱼娘图标

- https://github.com/fornarwhal/deepseek-whale-girl-icon
