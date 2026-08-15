"""页面模板模块：内置「等待服务启动」页与「启动失败/超时」错误页的 HTML。"""

import html
import json
from string import Template

from app.config import get_config_path

# 等待页：服务启动期间展示，带旋转动画与计时器
WAIT_PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>正在启动服务</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    user-select: none;
  }
  .card { text-align: center; max-width: 520px; padding: 0 24px; }
  .spinner {
    width: 56px; height: 56px; margin: 0 auto 28px;
    border: 5px solid rgba(148, 163, 184, 0.25);
    border-top-color: #38bdf8; border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .title { font-size: 20px; font-weight: 600; letter-spacing: 1px; }
  .sub { margin-top: 10px; font-size: 14px; color: #94a3b8; }
  .timer { margin-top: 8px; font-size: 13px; color: #64748b; font-variant-numeric: tabular-nums; }
  .url {
    margin-top: 22px; font-size: 13px; color: #38bdf8;
    word-break: break-all; font-family: Consolas, monospace;
  }
  .hint { margin-top: 30px; font-size: 12px; color: #475569; line-height: 1.8; }
</style>
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <div class="title">正在启动服务，请稍候…</div>
    <div class="sub">服务就绪后将自动打开页面</div>
    <div class="timer">已等待 <span id="sec">0</span> 秒</div>
    <div class="url">$TARGET_URL</div>
    <div class="hint">如果长时间无响应，请检查启动命令与服务地址配置<br>关闭窗口将自动停止后台服务</div>
  </div>
  <script>
    // 页面加载时刻作为计时起点
    var startAt = Date.now();
    setInterval(function () {
      var seconds = Math.floor((Date.now() - startAt) / 1000);
      document.getElementById('sec').textContent = seconds;
    }, 1000);
  </script>
</body>
</html>
""")

# 错误页：启动失败 / 服务退出 / 启动超时时展示，可重试或退出
ERROR_PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>$ERROR_TITLE</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card { width: 640px; max-width: 92vw; background: #1e293b; border-radius: 12px; padding: 36px 40px; }
  .icon {
    width: 52px; height: 52px; margin: 0 auto 20px;
    border-radius: 50%; background: rgba(248, 113, 113, 0.15);
    color: #f87171; font-size: 30px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
  }
  .title { text-align: center; font-size: 19px; font-weight: 600; }
  .message { margin-top: 14px; font-size: 14px; color: #94a3b8; line-height: 1.8; white-space: pre-wrap; }
  .log-box { display: $LOG_DISPLAY; margin-top: 18px; }
  .log-label { font-size: 12px; color: #64748b; margin-bottom: 8px; }
  .log-content {
    max-height: 220px; overflow: auto; padding: 12px 14px;
    background: #0f172a; border-radius: 8px;
    font-family: Consolas, monospace; font-size: 12px;
    color: #cbd5e1; line-height: 1.7; white-space: pre-wrap; word-break: break-all;
  }
  .actions { margin-top: 28px; display: flex; justify-content: center; gap: 14px; }
  .btn {
    min-width: 110px; padding: 10px 22px; border: none; border-radius: 8px;
    font-size: 14px; cursor: pointer; transition: opacity .15s;
  }
  .btn:hover { opacity: 0.85; }
  .btn-primary { background: #38bdf8; color: #0f172a; font-weight: 600; }
  .btn-ghost { background: transparent; color: #94a3b8; border: 1px solid #475569; }
</style>
</head>
<body>
  <div class="card">
    <div class="icon">!</div>
    <div class="title">$ERROR_TITLE</div>
    <div class="message">$ERROR_MESSAGE</div>
    <div class="log-box">
      <div class="log-label">服务日志（末尾 $LOG_LINES 行）：</div>
      <div class="log-content">$LOG_TAIL</div>
    </div>
    <div class="actions">
      <button class="btn btn-primary" onclick="pywebview.api.retry()">重 试</button>
      <button class="btn btn-ghost" onclick="pywebview.api.open_config_page('error')">打开配置</button>
      <button class="btn btn-ghost" onclick="pywebview.api.exit_app()">退 出</button>
    </div>
  </div>
</body>
</html>
""")

# 配置页：配置缺失或存在空参数时作为首页展示，可编辑全部配置项；高级设置默认折叠
CONFIG_PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>应用配置</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    background: #0f172a; color: #e2e8f0;
    min-height: 100vh; padding: 36px 20px 64px;
    display: flex; justify-content: center; align-items: flex-start;
  }
  .card { width: 760px; max-width: 100%; background: #1e293b; border-radius: 12px; padding: 34px 38px; position: relative; }
  .close-btn {
    position: absolute; top: 12px; right: 12px;
    width: 34px; height: 34px; border: none; border-radius: 8px;
    background: transparent; color: #94a3b8; font-size: 18px; line-height: 34px;
    text-align: center; cursor: pointer; transition: background .15s, color .15s;
  }
  .close-btn:hover { background: rgba(148, 163, 184, 0.15); color: #f87171; }
  .title { text-align: center; font-size: 20px; font-weight: 600; letter-spacing: 1px; }
  .sub { margin-top: 10px; text-align: center; font-size: 13px; color: #94a3b8; line-height: 1.9; }
  .sub .path { color: #38bdf8; font-family: Consolas, monospace; }
  .form { margin-top: 26px; }
  .field { margin-bottom: 18px; }
  .field > label { display: block; font-size: 13px; color: #cbd5e1; margin-bottom: 7px; }
  .req { color: #f87171; }
  input[type="text"], input[type="url"], input[type="number"] {
    width: 100%; padding: 10px 12px; font-size: 14px;
    background: #0f172a; color: #e2e8f0;
    border: 1px solid #475569; border-radius: 8px; outline: none;
  }
  input:focus { border-color: #38bdf8; }
  .help { margin-top: 6px; font-size: 12px; color: #64748b; line-height: 1.7; }
  details {
    margin-top: 8px; border: 1px solid #334155; border-radius: 10px;
    padding: 2px 18px 6px; background: #172033;
  }
  summary { cursor: pointer; padding: 13px 0; font-size: 14px; color: #38bdf8; user-select: none; }
  details[open] summary { border-bottom: 1px solid #334155; margin-bottom: 16px; }
  .row { display: flex; gap: 16px; }
  .row .field { flex: 1; }
  .check-field { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
  .check-field input { width: 16px; height: 16px; accent-color: #38bdf8; cursor: pointer; }
  .check-field label { margin: 0; font-size: 13px; color: #cbd5e1; cursor: pointer; }
  .actions { margin-top: 28px; display: flex; justify-content: center; gap: 14px; }
  .btn {
    min-width: 120px; padding: 10px 22px; border: none; border-radius: 8px;
    font-size: 14px; cursor: pointer; transition: opacity .15s;
  }
  .btn:hover { opacity: 0.85; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary { background: #38bdf8; color: #0f172a; font-weight: 600; }
  .btn-ghost { background: transparent; color: #94a3b8; border: 1px solid #475569; }
  #status { margin-top: 18px; text-align: center; font-size: 13px; min-height: 20px; line-height: 1.7; }
  #status.error { color: #f87171; }
  #status.success { color: #4ade80; }
</style>
</head>
<body>
  <div class="card">
    <button type="button" class="close-btn" style="display: $CLOSE_DISPLAY;" onclick="closeConfigOverlay()" title="关闭配置页" aria-label="关闭配置页">✕</button>
    <div class="title">应用配置</div>
    <div class="sub">
      请填写服务启动命令与服务地址（必填），其余参数为高级设置（已填入默认值）。<br>
      配置文件位置：<span class="path">$CONFIG_PATH</span>，点击保存后程序将自动重启。
    </div>
    <form id="config-form" class="form">
      <div class="field">
        <label for="web_command">服务启动命令（web_command）<span class="req">*</span></label>
        <input type="text" id="web_command" required placeholder="例如：python -m http.server 8080 --bind 127.0.0.1">
        <div class="help">完整命令行字符串；可执行文件路径含空格时请用双引号包裹。</div>
      </div>
      <div class="field">
        <label for="web_url">服务地址（web_url）<span class="req">*</span></label>
        <input type="url" id="web_url" required pattern="https?://.*" placeholder="例如：http://127.0.0.1:8080">
        <div class="help">服务就绪后跳转的地址，也是健康检查地址；必须以 http:// 或 https:// 开头。</div>
      </div>
      <details id="advanced">
        <summary>高级设置</summary>
        <div class="row">
          <div class="field">
            <label for="working_dir">工作目录（working_dir）<span class="req">*</span></label>
            <input type="text" id="working_dir" required>
            <div class="help">服务进程的工作目录，支持 ~ 表示用户主目录。</div>
          </div>
          <div class="field">
            <label for="log_dir">日志目录（log_dir）<span class="req">*</span></label>
            <input type="text" id="log_dir" required>
            <div class="help">服务日志与程序日志保存目录，支持 ~ 表示用户主目录。</div>
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label for="startup_timeout">启动超时秒数（startup_timeout）<span class="req">*</span></label>
            <input type="number" id="startup_timeout" required min="0.01" step="any">
          </div>
          <div class="field">
            <label for="check_interval">检查间隔秒数（check_interval）<span class="req">*</span></label>
            <input type="number" id="check_interval" required min="0.01" step="any">
          </div>
          <div class="field">
            <label for="check_timeout">检查超时秒数（check_timeout）<span class="req">*</span></label>
            <input type="number" id="check_timeout" required min="0.01" step="any">
          </div>
        </div>
        <div class="field">
          <label for="window_title">窗口标题（window_title）<span class="req">*</span></label>
          <input type="text" id="window_title" required>
        </div>
        <div class="row">
          <div class="field">
            <label for="window_width">窗口宽度（window_size[0]）<span class="req">*</span></label>
            <input type="number" id="window_width" required min="1" step="1">
          </div>
          <div class="field">
            <label for="window_height">窗口高度（window_size[1]）<span class="req">*</span></label>
            <input type="number" id="window_height" required min="1" step="1">
          </div>
        </div>
        <div class="check-field">
          <input type="checkbox" id="show_console">
          <label for="show_console">显示服务控制台窗口（show_console，调试用）</label>
        </div>
        <div class="check-field">
          <input type="checkbox" id="kill_on_exit">
          <label for="kill_on_exit">关闭窗口时终止服务进程（kill_on_exit）</label>
        </div>
      </details>
      <div class="actions">
        <button type="submit" class="btn btn-primary" id="btn-save">保 存</button>
        <button type="button" class="btn btn-ghost" id="btn-exit">退 出</button>
      </div>
      <div id="status"></div>
    </form>
  </div>
  <script>
    // 当前配置（由 Python 端注入，用于回填表单）
    var CONFIG = $CONFIG_JSON;

    // 桥接就绪等待超时毫秒数：超时后提示重启应用并恢复保存按钮
    var BRIDGE_READY_TIMEOUT_MS = 10000;
    // 桥接就绪轮询间隔毫秒数
    var BRIDGE_POLL_INTERVAL_MS = 200;

    // 动态解析当前可用的桥对象：pywebview 在页面加载完成（NavigationCompleted）
    // 之后才注入 window.pywebview 与 api，因此不能在脚本加载时缓存，必须按需解析。
    // 顶层加载（首次启动 / 错误页进入）时桥位于 window.pywebview；
    // 作为遮罩 iframe（srcdoc，同源）加载在目标网页上时，桥位于父窗口。
    function resolveBridgeApi() {
      var api = window.pywebview && window.pywebview.api;
      // api 对象已创建但函数尚未填充（空对象）时视为未就绪
      if (api && typeof api.save_config === 'function') { return api; }
      var parentWindow = window.parent;
      if (parentWindow && parentWindow !== window && parentWindow.pywebview) {
        var parentApi = parentWindow.pywebview.api;
        if (parentApi && typeof parentApi.save_config === 'function') { return parentApi; }
      }
      return null;
    }

    // 桥就绪后执行回调：pywebview 注入完成时会派发 pywebviewready 事件，
    // 但事件可能已错过（页面脚本运行时注入早已完成）或派发在父窗口，
    // 因此事件监听与轮询双保险；超时后提示重启应用。
    function whenBridgeReady(callback) {
      var startedAt = Date.now();
      var finished = false;

      function tryResolve() {
        if (finished) { return; }
        var api = resolveBridgeApi();
        if (api) {
          finished = true;
          callback(api);
          return;
        }
        if (Date.now() - startedAt >= BRIDGE_READY_TIMEOUT_MS) {
          finished = true;
          setStatus('页面桥接不可用，请重启应用', 'error');
          setSaveEnabled(true);
          return;
        }
        setTimeout(tryResolve, BRIDGE_POLL_INTERVAL_MS);
      }

      window.addEventListener('pywebviewready', tryResolve);
      // 遮罩 iframe 模式下事件在父窗口派发（srcdoc 与父页面同源，可直接订阅）
      if (window.parent && window.parent !== window) {
        window.parent.addEventListener('pywebviewready', tryResolve);
      }
      tryResolve();
    }

    function setValue(id, value) {
      document.getElementById(id).value = (value === undefined || value === null) ? '' : value;
    }
    function setStatus(text, kind) {
      var el = document.getElementById('status');
      el.textContent = text || '';
      el.className = kind || '';
    }
    function setSaveEnabled(enabled) {
      document.getElementById('btn-save').disabled = !enabled;
    }
    function closeConfigOverlay() {
      // 右上角「✕」：关闭遮罩并返回来源页面（顶层首次配置页不显示该按钮）
      var api = resolveBridgeApi();
      if (api) { api.exit_config_page(); }
    }

    // 遮罩模式（iframe 内）下支持 Esc 关闭配置页
    if (window.parent && window.parent !== window) {
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') { closeConfigOverlay(); }
      });
    }

    // 回填当前配置
    setValue('web_command', CONFIG.web_command);
    setValue('web_url', CONFIG.web_url);
    setValue('working_dir', CONFIG.working_dir);
    setValue('log_dir', CONFIG.log_dir);
    setValue('startup_timeout', CONFIG.startup_timeout);
    setValue('check_interval', CONFIG.check_interval);
    setValue('check_timeout', CONFIG.check_timeout);
    setValue('window_title', CONFIG.window_title);
    var size = (CONFIG.window_size && CONFIG.window_size.length === 2) ? CONFIG.window_size : [1200, 800];
    setValue('window_width', size[0]);
    setValue('window_height', size[1]);
    document.getElementById('show_console').checked = !!CONFIG.show_console;
    document.getElementById('kill_on_exit').checked = !!CONFIG.kill_on_exit;

    document.getElementById('config-form').addEventListener('submit', function (event) {
      event.preventDefault();
      // 高级设置折叠时若其中存在必填项未通过校验，先自动展开再提示
      var advanced = document.getElementById('advanced');
      var requiredInputs = advanced.querySelectorAll('input[required]');
      var hasInvalid = false;
      for (var i = 0; i < requiredInputs.length; i++) {
        if (!requiredInputs[i].checkValidity()) { hasInvalid = true; break; }
      }
      if (hasInvalid) { advanced.open = true; }
      if (!this.checkValidity()) { this.reportValidity(); return; }

      var payload = {
        web_command: document.getElementById('web_command').value,
        web_url: document.getElementById('web_url').value,
        working_dir: document.getElementById('working_dir').value,
        startup_timeout: document.getElementById('startup_timeout').value,
        check_interval: document.getElementById('check_interval').value,
        check_timeout: document.getElementById('check_timeout').value,
        window_title: document.getElementById('window_title').value,
        window_size: [
          document.getElementById('window_width').value,
          document.getElementById('window_height').value
        ],
        show_console: document.getElementById('show_console').checked,
        kill_on_exit: document.getElementById('kill_on_exit').checked,
        log_dir: document.getElementById('log_dir').value
      };

      setSaveEnabled(false);
      setStatus('正在保存…');
      // 桥接在页面加载完成后才注入：等待就绪后再提交保存
      whenBridgeReady(function (api) {
        api.save_config(payload).then(function (result) {
          if (result && result.ok) {
            setStatus(result.message || '保存成功，程序即将自动重启…', 'success');
            // 延时重启：给用户看到保存成功提示的时间
            setTimeout(function () { api.restart_app(); }, 800);
          } else {
            setStatus((result && result.message) || '保存失败，请检查填写内容', 'error');
            setSaveEnabled(true);
          }
        }).catch(function (error) {
          setStatus('保存失败：' + error, 'error');
          setSaveEnabled(true);
        });
      });
    });

    document.getElementById('btn-exit').addEventListener('click', function () {
      var api = resolveBridgeApi();
      if (api) { api.exit_app(); }
    });
  </script>
</body>
</html>
""")


def build_wait_page(target_url: str) -> str:
    """
    生成「等待服务启动」页面 HTML。

    Args:
        target_url: 目标服务地址，展示在页面上。

    Returns:
        完整 HTML 字符串。
    """
    return WAIT_PAGE_TEMPLATE.substitute(TARGET_URL=html.escape(target_url))


def build_error_page(title: str, message: str, log_tail: str = "", max_log_lines: int = 30) -> str:
    """
    生成错误提示页 HTML。

    Args:
        title: 错误标题（如「服务启动超时」）。
        message: 错误说明文字。
        log_tail: 服务日志末尾内容，为空时隐藏日志区域。
        max_log_lines: 日志最多展示行数（仅用于标签展示）。

    Returns:
        完整 HTML 字符串。
    """
    return ERROR_PAGE_TEMPLATE.substitute(
        ERROR_TITLE=html.escape(title),
        ERROR_MESSAGE=html.escape(message),
        LOG_DISPLAY="block" if log_tail else "none",
        LOG_LINES=max_log_lines,
        LOG_TAIL=html.escape(log_tail),
    )


def build_config_page(config: dict, config_path: str = "", show_close: bool = False) -> str:
    """
    生成配置页面 HTML：回填当前配置，全部字段必填，高级设置默认折叠。

    Args:
        config: 当前配置字典（用于回填表单）。
        config_path: 配置文件路径（展示用），为空时自动获取。
        show_close: 是否显示右上角关闭按钮（遮罩式进入时显示，点击返回来源页面）。

    Returns:
        完整 HTML 字符串。
    """
    # 将 < 转义为 \u003c，避免 JSON 内容破坏 <script> 标签
    config_json = json.dumps(config, ensure_ascii=False).replace("<", "\\u003c")
    return CONFIG_PAGE_TEMPLATE.substitute(
        CONFIG_JSON=config_json,
        CONFIG_PATH=html.escape(config_path or get_config_path()),
        CLOSE_DISPLAY="block" if show_close else "none",
    )


# 关闭遮罩脚本：移除配置页遮罩节点，目标网页原样保留（不导航、不刷新）
CLOSE_OVERLAY_SCRIPT = (
    "(function () {"
    "  var el = document.querySelector('[data-wbd-config-overlay]');"
    "  if (el) { el.remove(); }"
    "})();"
)


def build_config_overlay_script(html_content: str) -> str:
    """
    生成「配置页遮罩」注入脚本：在目标网页 DOM 上挂载全屏 iframe 遮罩，
    配置页经 iframe srcdoc 加载（与父页面同源，可经父窗口调用 js 桥）。
    遮罩打开 / 关闭均不导航，目标网页状态完整保留。

    Args:
        html_content: 配置页完整 HTML。

    Returns:
        可交由 window.evaluate_js 执行的注入脚本字符串。
    """
    # JSON 序列化后的字符串可作为合法 JS 字面量嵌入（引号、换行均已转义）
    payload = json.dumps(html_content, ensure_ascii=False)
    return (
        "(function () {"
        "  'use strict';"
        "  var existing = document.querySelector('[data-wbd-config-overlay]');"
        "  if (existing) { existing.remove(); }"
        "  var host = document.createElement('div');"
        "  host.setAttribute('data-wbd-config-overlay', '1');"
        "  var shadow = host.attachShadow({ mode: 'open' });"
        "  shadow.innerHTML = '<style>'"
        "    + ':host { all: initial; }'"
        "    + '.overlay { position: fixed; inset: 0; z-index: 2147483646; }'"
        "    + 'iframe { width: 100%; height: 100%; border: none; display: block; background: #0f172a; }'"
        "    + '</style>'"
        "    + '<div class=\"overlay\"><iframe title=\"应用配置\"></iframe></div>';"
        "  (document.body || document.documentElement).appendChild(host);"
        "  var frame = shadow.querySelector('iframe');"
        "  frame.srcdoc = " + payload + ";"
        "})();"
    )
