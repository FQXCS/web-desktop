"""应用控制器：编排「启动服务 → 等待就绪 → 跳转页面 / 错误提示」的完整流程。"""

import logging
import os
import subprocess
import sys
import threading
import time

from app.config import build_config_from_form, get_config_path, load_config, write_config
from app.context_menu import CONTEXT_MENU_SCRIPT
from app.pages import (
    CLOSE_OVERLAY_SCRIPT,
    build_config_overlay_script,
    build_config_page,
    build_error_page,
    build_wait_page,
)
from app.service import WebServiceError, WebServiceManager


class AppController:
    """应用主控制器，管理服务生命周期、配置保存与窗口页面切换。"""

    def __init__(self, config: dict, config_mode: bool = False):
        """
        初始化控制器。

        Args:
            config: 应用配置字典。
            config_mode: 配置模式（配置缺失或存在空参数时为 True），此模式下不启动服务。
        """
        self._config = config
        self._config_mode = config_mode
        self._window = None
        self._service = None
        self._lock = threading.Lock()
        # 窗口关闭时置位，用于通知等待循环及时退出
        self.stop_event = threading.Event()
        # 是否已跳转到目标网页（仅在目标网页注入自定义右键菜单）
        self._target_loaded = False
        # 配置页来源：None（首次启动）/ "web"（右键菜单）/ "error"（错误页）
        self._config_page_source = None
        # 最近一次错误页 HTML 缓存（配置页关闭时返回错误页用）
        self._last_error_html = None

    def set_window(self, window) -> None:
        """
        绑定 GUI 窗口（由 UI 层创建后注入）。

        Args:
            window: pywebview 窗口对象。
        """
        self._window = window
        # 窗口关闭 → 置位停止事件，等待循环随即退出
        window.events.closed += self.stop_event.set
        # 每次导航完成（含刷新、返回目标网页）→ 尝试注入右键菜单
        window.events.loaded += self._on_page_loaded

    def start(self) -> None:
        """启动流程（首次启动与错误页「重试」共用）；配置模式下不启动服务。"""
        if self._window is None or self.stop_event.is_set() or self._config_mode:
            return
        # 先停止可能残留的旧服务进程，避免重复启动
        self._stop_current_service()

        try:
            service = WebServiceManager(self._config)
            service.start()
        except WebServiceError as exc:
            self._show_error("服务启动失败", str(exc))
            return
        except Exception as exc:  # 兜底捕获未知异常
            logging.exception("启动服务时发生未知异常")
            self._show_error("服务启动失败", f"发生未知异常：{exc}")
            return

        with self._lock:
            self._service = service
        # 切换回等待页，并启动后台就绪检查线程
        self._target_loaded = False
        self._window.load_html(build_wait_page(self._config["web_url"]))
        threading.Thread(target=self._wait_loop, args=(service,), daemon=True).start()

    def retry(self) -> None:
        """错误页「重试」按钮回调（由页面 JS 经 js_api 调用）。"""
        logging.info("用户点击重试，重新启动服务")
        self.start()

    def exit_app(self) -> None:
        """错误页 / 配置页「退出」按钮回调（由页面 JS 经 js_api 调用）。"""
        logging.info("用户点击退出，关闭窗口")
        self._window.destroy()

    def save_config(self, data: dict) -> dict:
        """
        配置页「保存」按钮回调：校验并写入配置文件，返回结果供前端展示。

        Args:
            data: 页面提交的表单数据。

        Returns:
            {"ok": bool, "message": str} 结构的结果字典。
        """
        config, error = build_config_from_form(data)
        if error:
            logging.warning("配置保存被拒绝：%s", error)
            return {"ok": False, "message": error}
        write_config(config)
        self._config = config
        logging.info("配置已保存到：%s", get_config_path())
        return {"ok": True, "message": "配置已保存，程序即将自动重启"}

    def restart_app(self) -> None:
        """配置保存成功后重启应用：拉起新进程后关闭当前窗口（配置页 JS 延时调用）。"""
        if getattr(sys, "frozen", False):
            # PyInstaller 打包：sys.executable 即 exe 路径
            command = [sys.executable] + sys.argv[1:]
        else:
            # 源码运行：用解释器重新执行入口脚本
            command = [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]
        try:
            # CREATE_NEW_PROCESS_GROUP：新进程独立于当前进程组，不受本进程退出影响
            subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            logging.info("已拉起新进程：%s", " ".join(command))
        except Exception:
            # 拉起新进程失败时配置已保存，记录日志并继续关闭窗口（用户可手动重启）
            logging.exception("拉起新进程失败")
        self._window.destroy()

    def open_config_page(self, source: str = "web") -> None:
        """
        打开配置页面。

        Args:
            source: 打开来源。"error" 表示从错误页进入（先停止残留服务，
                关闭配置页后返回错误页）；"web" 表示从目标网页右键菜单进入，
                以全屏遮罩覆盖在目标网页上（不导航、不刷新，服务保持运行）。
        """
        logging.info("用户打开配置页面（来源：%s）", source)
        if source == "error":
            # 错误页进入：清理可能残留的服务进程（与历史行为一致），整页切换到配置页
            self._stop_current_service()
            self._config_page_source = source
            self._target_loaded = False
            self._config = load_config()
            self._window.load_html(build_config_page(self._config, show_close=True))
            return
        # 目标网页进入：注入遮罩 iframe，目标网页状态完整保留
        self._config_page_source = source
        self._config = load_config()
        overlay_html = build_config_page(self._config, show_close=True)
        try:
            self._window.evaluate_js(build_config_overlay_script(overlay_html))
        except Exception:
            # 注入失败时退化为整页打开配置页
            logging.exception("注入配置页遮罩失败，改为整页打开")
            self._target_loaded = False
            self._window.load_html(overlay_html)

    def exit_config_page(self) -> None:
        """配置页右上角「✕」按钮回调：关闭配置页，按来源返回对应页面。"""
        source = self._config_page_source
        logging.info("用户关闭配置页，返回来源：%s", source)
        self._config_page_source = None
        if source == "web":
            # 移除遮罩即可，目标网页原样保留（不导航、不刷新，右键菜单仍然有效）
            try:
                self._window.evaluate_js(CLOSE_OVERLAY_SCRIPT)
            except Exception:
                logging.exception("移除配置页遮罩失败")
        else:
            # 返回错误页（缓存快照）；无缓存时防御性回到等待页
            self._target_loaded = False
            if self._last_error_html:
                self._window.load_html(self._last_error_html)
            else:
                self._window.load_html(build_wait_page(self._config["web_url"]))

    def stop(self) -> None:
        """清理资源：停止后台服务（窗口关闭后由入口调用）。"""
        self._stop_current_service()

    def _wait_loop(self, service: WebServiceManager) -> None:
        """
        后台就绪检查循环：轮询服务健康状态，就绪后跳转目标地址；
        进程退出或超时则展示错误页；窗口关闭时立即退出。

        Args:
            service: 本次启动的服务管理器实例。
        """
        timeout = self._config.get("startup_timeout", 60)
        interval = self._config.get("check_interval", 0.5)
        deadline = time.monotonic() + timeout

        while not self.stop_event.is_set():
            if not service.is_running():
                # 服务进程已退出，展示退出码与日志
                self._show_error(
                    "服务已停止",
                    f"服务进程已退出（退出码：{service.exit_code()}），请检查服务日志。",
                )
                return
            if service.is_ready():
                logging.info("服务已就绪，跳转到 %s", self._config["web_url"])
                # 跳转目标网页：loaded 事件触发时注入自定义右键菜单
                self._target_loaded = True
                self._window.load_url(self._config["web_url"])
                return
            if time.monotonic() >= deadline:
                self._show_error(
                    "服务启动超时",
                    f"等待 {timeout} 秒后服务仍未就绪。\n"
                    "请检查 web_command 是否正确、web_url 是否与服务的实际端口一致。",
                )
                return
            time.sleep(interval)

    def _show_error(self, title: str, message: str) -> None:
        """
        展示错误页，并附带服务日志末尾内容便于排查。

        Args:
            title: 错误标题。
            message: 错误说明。
        """
        log_tail = self._service.read_log_tail() if self._service else ""
        error_html = build_error_page(title, message, log_tail)
        # 缓存错误页快照：配置页「✕」关闭时返回错误页
        self._last_error_html = error_html
        self._target_loaded = False
        self._window.load_html(error_html)

    def _on_page_loaded(self) -> None:
        """页面加载完成回调：已跳转到目标网页时注入自定义右键菜单脚本。"""
        if not self._target_loaded or self._window is None:
            return
        try:
            # 脚本自带幂等标记，重复注入（如整页刷新后）安全
            self._window.evaluate_js(CONTEXT_MENU_SCRIPT)
            logging.info("已向目标网页注入自定义右键菜单")
        except Exception:
            # 注入失败不影响主流程，仅记录日志
            logging.exception("注入自定义右键菜单失败")

    def _stop_current_service(self) -> None:
        """停止当前持有的服务管理器（幂等，可重复调用）。"""
        with self._lock:
            service = self._service
            self._service = None
        if service is not None:
            service.stop()
