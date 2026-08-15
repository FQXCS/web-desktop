"""UI 层：创建 pywebview 窗口（基于系统 Edge/WebView2 内核），并向页面暴露 Python 接口。"""

import ctypes
import logging

import webview

# Windows 剪贴板格式常量：Unicode 文本（CF_UNICODETEXT）
CF_UNICODETEXT = 13


class BridgeApi:
    """暴露给页面 JavaScript 调用的接口（配置页与错误页按钮）。"""

    def __init__(self, controller):
        """
        初始化接口。

        Args:
            controller: 应用控制器实例。
        """
        self._controller = controller

    def retry(self) -> None:
        """页面「重试」按钮回调：重新执行服务启动流程。"""
        self._controller.retry()

    def exit_app(self) -> None:
        """页面「退出」按钮回调：关闭窗口。"""
        self._controller.exit_app()

    def save_config(self, data: dict) -> dict:
        """
        配置页「保存」按钮回调：校验并保存配置。

        Args:
            data: 页面提交的表单数据。

        Returns:
            {"ok": bool, "message": str} 结果字典。
        """
        return self._controller.save_config(data)

    def restart_app(self) -> None:
        """配置页保存成功后延时调用：重启应用。"""
        self._controller.restart_app()

    def open_config_page(self, source: str = "web") -> None:
        """
        打开配置页面（遮罩式，右上角带关闭按钮）。

        Args:
            source: 打开来源。"web" 表示从目标网页右键菜单进入（保持服务运行，
                关闭配置页后返回目标网页）；"error" 表示从错误页进入
                （先停止残留服务，关闭配置页后返回错误页）。
        """
        self._controller.open_config_page(source)

    def exit_config_page(self) -> None:
        """配置页右上角「✕」按钮回调：关闭配置页并返回来源页面。"""
        self._controller.exit_config_page()

    def get_clipboard_text(self):
        """
        读取 Windows 剪贴板中的 Unicode 文本（供目标网页右键菜单「粘贴」使用）。

        Returns:
            剪贴板文本；剪贴板为空、被其他进程占用或非 Windows 平台时返回 None。
        """
        # 非 Windows 平台（如 Linux/macOS）无 windll，直接视为不可用
        if not hasattr(ctypes, "windll"):
            return None
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # 声明参数与返回值类型，避免 64 位下句柄被截断
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_int
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        user32.GetClipboardData.restype = ctypes.c_void_p
        user32.CloseClipboard.restype = ctypes.c_int
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_int
        try:
            if not user32.OpenClipboard(None):
                # 剪贴板被其他进程占用等：视为读取失败
                return None
            try:
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return None
                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    return None
                try:
                    # 以 UTF-16 读取至终止符，返回 Python 字符串
                    return ctypes.wstring_at(pointer)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        except Exception:
            # 任何异常均退化为「不可用」，不让 js 桥调用链路报错
            logging.exception("读取剪贴板文本失败")
            return None


def create_main_window(controller, config: dict, html: str):
    """
    创建主窗口：初始页面由调用方指定（等待页或配置页）。

    Args:
        controller: 应用控制器实例（绑定窗口与关闭事件）。
        config: 应用配置字典。
        html: 初始页面 HTML。

    Returns:
        pywebview 窗口对象。
    """
    size = config.get("window_size", [1200, 800])
    window = webview.create_window(
        title=config.get("window_title", "Web 桌面启动器"),
        html=html,
        js_api=BridgeApi(controller),
        width=int(size[0]),
        height=int(size[1]),
        min_size=(800, 600),
        background_color="#0f172a",
    )
    controller.set_window(window)
    logging.info("主窗口已创建：%s（%sx%s）", window.title, size[0], size[1])
    return window
