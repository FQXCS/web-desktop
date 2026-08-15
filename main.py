"""WebDesktop 桌面启动器：启动后台 web 服务，就绪后跳转到配置的服务地址。"""

import logging
import os
import subprocess
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

# 环境变量标记：自动重启兜底只执行一次，防止解压目录持续异常时陷入重启循环
_RESTARTED_MARK = "WEBDESKTOP_AUTO_RESTARTED"


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


def try_auto_restart(exc: Exception) -> bool:
    """
    解压目录被意外破坏时的兜底：以干净环境自动重启一次，避免弹出「启动失败」。

    打包后的单文件程序依赖 PyInstaller 解压目录，极端情况下该目录中的文件
    可能被外部进程删除（典型报错：Cannot find win-arm64）。此时以剥离
    _PYI_* 环境变量的方式重启，新进程会独立解压，通常即可恢复。

    Args:
        exc: main 捕获到的未预期异常。

    Returns:
        已自动重启返回 True（调用方直接退出，不再弹错误框）。
    """
    if not getattr(sys, "frozen", False):
        # 源码模式无解压目录，无需兜底
        return False
    if not isinstance(exc, FileNotFoundError) or "Cannot find" not in str(exc):
        # 仅针对解压目录文件缺失类异常兜底，其余异常仍正常提示
        return False
    if os.environ.get(_RESTARTED_MARK):
        # 已自动重启过一次仍失败：不再循环，让错误正常弹出
        return False
    try:
        # 剥离 PyInstaller 父子进程共享解压目录的环境变量，确保独立解压
        env = {key: value for key, value in os.environ.items() if not key.startswith("_PYI_")}
        env[_RESTARTED_MARK] = "1"
        subprocess.Popen(
            [sys.executable] + sys.argv[1:],
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        logging.warning("解压目录异常（%s），已自动重启应用", exc)
        return True
    except Exception:
        # 自动重启失败：退化为弹窗提示
        logging.exception("自动重启失败")
        return False


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
        if try_auto_restart(exc):
            return 1
        show_fatal_error(f"程序启动失败：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
