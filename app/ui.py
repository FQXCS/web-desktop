"""UI 层：创建 pywebview 窗口（基于系统 Edge/WebView2 内核），并向页面暴露 Python 接口。"""

import logging

import webview


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

    def open_config_page(self) -> None:
        """错误页「打开配置」按钮回调：进入配置页面。"""
        self._controller.open_config_page()


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
