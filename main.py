"""WebDesktop 桌面启动器：启动后台 web 服务，就绪后跳转到配置的服务地址。"""

import logging
import os
import sys

# 开发模式：优先从工作区 .site 目录加载第三方依赖（沙箱环境下系统 site-packages 不可写）
_SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".site")
if os.path.isdir(_SITE_DIR) and _SITE_DIR not in sys.path:
    sys.path.insert(0, _SITE_DIR)

import webview  # noqa: E402

from app.config import get_config_dir, get_config_issues, load_config  # noqa: E402
from app.controller import AppController  # noqa: E402
from app.pages import build_config_page, build_wait_page  # noqa: E402
from app.ui import create_main_window  # noqa: E402

LOG_FILE_NAME = "app.log"


def show_fatal_error(message: str) -> None:
    """
    在 GUI 环境下弹出系统错误对话框（未预期的致命错误）。

    Args:
        message: 展示给用户的错误信息。
    """
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "启动失败", 0x10)  # 0x10 = MB_ICONERROR
    except Exception:
        # 弹窗失败时退化为日志输出
        logging.critical(message)


def setup_logging(config: dict) -> None:
    """初始化日志：输出到配置项 log_dir 指定的目录（默认 ~/.WebDesktop/log）。"""
    log_dir = config.get("log_dir") or os.path.join(get_config_dir(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, LOG_FILE_NAME)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
        # force=True：清掉此前挂载的 root handler（如 Python 3.13 日志模块在无 handler 时
        # 隐式 basicConfig 的控制台 handler），确保日志确实写入 app.log
        force=True,
    )


def main() -> int:
    """
    程序入口：加载配置 → 配置缺失或参数为空时进入配置页面，否则启动服务等待流程 → 窗口关闭后清理。

    Returns:
        进程退出码，0 表示正常退出。
    """
    try:
        # 加载配置：自动确保 ~/.WebDesktop 目录与配置文件存在（不存在则创建）
        config = load_config()
        setup_logging(config)
        logging.info("程序启动，配置目录：%s", get_config_dir())

        issues = get_config_issues(config)
        controller = AppController(config, config_mode=bool(issues))
        if issues:
            # 配置缺失或存在空参数（如首次运行）：首页进入配置页面
            logging.warning("配置不完整，进入配置页面：%s", "；".join(issues))
            create_main_window(controller, config, build_config_page(config))
        else:
            create_main_window(controller, config, build_wait_page(config["web_url"]))

        # webview.start 会阻塞直到所有窗口关闭；controller.start 在其子线程中执行
        webview.start(controller.start, debug=False)
        # 窗口已关闭：停止后台服务进程
        controller.stop()
        logging.info("程序退出")
        return 0
    except Exception as exc:  # 兜底捕获未预期异常
        logging.exception("程序运行发生未预期异常")
        show_fatal_error(f"程序启动失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
