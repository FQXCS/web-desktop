"""配置模块：管理 ~/.WebDesktop/config.json 的创建、加载、校验与保存。"""

import copy
import json
import logging
import os

from app.paths import expand_home_path, get_home_dir

# 配置目录名：位于用户家目录下（Windows 上即 C:\Users\<用户名>\.WebDesktop）
CONFIG_DIR_NAME = ".WebDesktop"
CONFIG_FILE_NAME = "config.json"

# 默认配置：除 web_command / web_url 外所有参数均有默认值；
# web_command 与 web_url 为必填项但无默认值，留空时程序进入配置页面引导用户填写
DEFAULT_CONFIG = {
    # 服务启动命令：完整命令行字符串，含空格的路径请用双引号包裹（必填，无默认值）
    "web_command": "",
    # 服务地址：服务就绪后跳转的地址（必填，无默认值）
    "web_url": "",
    # 服务工作目录：默认 ~/.WebDesktop/working
    "working_dir": "~/.WebDesktop/working",
    # 等待服务就绪的超时秒数
    "startup_timeout": 60,
    # 健康检查轮询间隔（秒）
    "check_interval": 0.5,
    # 单次健康检查超时（秒）
    "check_timeout": 2,
    # 窗口标题
    "window_title": "Web 桌面启动器",
    # 窗口尺寸 [宽, 高]
    "window_size": [1200, 800],
    # 是否显示服务控制台窗口（调试用）
    "show_console": False,
    # 关闭窗口时是否终止服务进程
    "kill_on_exit": True,
    # 日志目录：默认 ~/.WebDesktop/log
    "log_dir": "~/.WebDesktop/log",
}

# 配置项的中文名称（校验提示信息用）
_CONFIG_LABELS = {
    "web_command": "服务启动命令",
    "web_url": "服务地址",
    "working_dir": "工作目录",
    "log_dir": "日志目录",
    "window_title": "窗口标题",
}


def get_config_dir() -> str:
    """
    获取配置目录（~/.WebDesktop）的绝对路径（~ 为用户家目录，从环境变量获取）。

    Returns:
        配置目录绝对路径。
    """
    return os.path.join(get_home_dir(), CONFIG_DIR_NAME)


def get_config_path() -> str:
    """
    获取配置文件（~/.WebDesktop/config.json）的绝对路径。

    Returns:
        配置文件绝对路径。
    """
    return os.path.join(get_config_dir(), CONFIG_FILE_NAME)


def ensure_config_file() -> str:
    """
    确保配置目录与配置文件存在：目录不存在时创建目录，配置文件不存在时用默认配置创建。

    Returns:
        配置文件绝对路径。
    """
    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    path = get_config_path()
    if not os.path.exists(path):
        write_config(copy.deepcopy(DEFAULT_CONFIG))
        logging.info("配置文件不存在，已使用默认配置创建：%s", path)
    return path


def load_config() -> dict:
    """
    加载配置：确保配置文件存在，与默认配置合并并规范化路径。

    Returns:
        合并后的完整配置字典（不保证合法，完整性由 get_config_issues 检查）。
    """
    path = ensure_config_file()
    config = copy.deepcopy(DEFAULT_CONFIG)
    user_config = _read_config(path)
    if user_config is not None:
        _merge(config, user_config)
    else:
        logging.warning("配置文件读取失败，将使用默认配置：%s", path)
    _normalize_paths(config)
    return config


def get_config_issues(config: dict) -> list:
    """
    检查配置完整性：任一参数为空或取值不合法都会记录问题。

    Args:
        config: 合并后的配置字典。

    Returns:
        问题描述列表；空列表表示配置可用。
    """
    issues = []

    command = config.get("web_command")
    if not isinstance(command, str) or not command.strip():
        issues.append(f"{_CONFIG_LABELS['web_command']}（web_command）不能为空")

    url = config.get("web_url")
    if not isinstance(url, str) or not url.strip():
        issues.append(f"{_CONFIG_LABELS['web_url']}（web_url）不能为空")
    elif not url.startswith(("http://", "https://")):
        issues.append(f"{_CONFIG_LABELS['web_url']}（web_url）必须以 http:// 或 https:// 开头")

    for key in ("working_dir", "log_dir"):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{_CONFIG_LABELS[key]}（{key}）不能为空")

    for key in ("startup_timeout", "check_interval", "check_timeout"):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            issues.append(f"{key} 必须是大于 0 的数字")

    title = config.get("window_title")
    if not isinstance(title, str) or not title.strip():
        issues.append(f"{_CONFIG_LABELS['window_title']}（window_title）不能为空")

    size = config.get("window_size")
    valid_size = (
        isinstance(size, list)
        and len(size) == 2
        and all(
            not isinstance(item, bool) and isinstance(item, (int, float)) and item > 0
            for item in size
        )
    )
    if not valid_size:
        issues.append("window_size（窗口尺寸）必须是 [宽, 高] 两个正数")

    for key in ("show_console", "kill_on_exit"):
        if not isinstance(config.get(key), bool):
            issues.append(f"{key} 必须是布尔值（true/false）")

    return issues


def build_config_from_form(data: dict):
    """
    将配置页面提交的表单数据转换为配置字典，并做完整性校验（全部参数必填）。

    Args:
        data: 页面提交的原始数据（字符串与布尔值混合）。

    Returns:
        (config, error) 元组：校验失败时 config 为空字典、error 为错误描述；
        校验通过时 error 为空字符串。
    """
    if not isinstance(data, dict):
        return {}, "提交的数据格式不正确"

    config = {}

    # 必填字符串字段：去除首尾空白后不能为空
    command = _text(data, "web_command")
    if not command:
        return {}, f"{_CONFIG_LABELS['web_command']}（web_command）不能为空"
    config["web_command"] = command

    url = _text(data, "web_url")
    if not url:
        return {}, f"{_CONFIG_LABELS['web_url']}（web_url）不能为空"
    if not url.startswith(("http://", "https://")):
        return {}, f"{_CONFIG_LABELS['web_url']}（web_url）必须以 http:// 或 https:// 开头"
    config["web_url"] = url

    # 目录字段：必填，写入前展开 ~ 并转为绝对路径
    for key in ("working_dir", "log_dir"):
        value = _text(data, key)
        if not value:
            return {}, f"{_CONFIG_LABELS[key]}（{key}）不能为空"
        config[key] = _expand_path(value)

    # 数字字段：必填且大于 0
    for key in ("startup_timeout", "check_interval", "check_timeout"):
        number = _parse_positive_number(data.get(key))
        if number is None:
            return {}, f"{key} 必须是大于 0 的数字"
        config[key] = number

    title = _text(data, "window_title")
    if not title:
        return {}, f"{_CONFIG_LABELS['window_title']}（window_title）不能为空"
    config["window_title"] = title

    # 窗口尺寸：必填且宽高均为正数（转为整数保存）
    size = data.get("window_size")
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        return {}, "window_size（窗口尺寸）必须是 [宽, 高] 两个正数"
    width = _parse_positive_number(size[0])
    height = _parse_positive_number(size[1])
    if width is None or height is None or int(width) <= 0 or int(height) <= 0:
        return {}, "window_size（窗口尺寸）必须是 [宽, 高] 两个正数"
    config["window_size"] = [int(width), int(height)]

    # 布尔字段：接受布尔值与 "true"/"false" 字符串
    for key in ("show_console", "kill_on_exit"):
        boolean = _parse_bool(data.get(key))
        if boolean is None:
            return {}, f"{key} 必须是布尔值（true/false）"
        config[key] = boolean

    return config, ""


def write_config(config: dict) -> None:
    """
    将配置写入 ~/.WebDesktop/config.json（先写临时文件再替换，避免写入中断导致文件损坏）。

    Args:
        config: 待写入的配置字典。
    """
    config_dir = get_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    path = get_config_path()
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)
    logging.info("配置已写入：%s", path)


def _read_config(path: str):
    """
    读取指定路径的 JSON 配置文件。

    Args:
        path: 配置文件路径。

    Returns:
        解析出的字典；文件不存在或解析失败时返回 None。
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("配置文件根节点必须是 JSON 对象")
        return data
    except FileNotFoundError:
        logging.info("配置文件不存在：%s", path)
        return None
    except (OSError, ValueError) as exc:
        logging.error("读取配置文件失败：%s，原因：%s", path, exc)
        return None


def _merge(config: dict, user_config: dict) -> None:
    """将用户配置合并进默认配置：缺失字段保留默认值，字符串字段做类型兜底。"""
    for key in DEFAULT_CONFIG:
        if key in user_config and user_config[key] is not None:
            config[key] = user_config[key]
    # 字符串字段类型异常时置空，交由完整性检查提示用户
    for key in ("web_command", "web_url", "working_dir", "window_title", "log_dir"):
        if not isinstance(config[key], str):
            config[key] = ""


def _normalize_paths(config: dict) -> None:
    """规范化目录字段：展开 ~ 并转为绝对路径（相对路径以配置目录为基准）。"""
    base = get_config_dir()
    for key in ("working_dir", "log_dir"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            config[key] = _expand_path(value, base)


def _expand_path(value: str, base: str = "") -> str:
    """展开 ~（家目录从环境变量获取）并将相对路径转换为绝对路径。base 为空时以配置目录为基准。"""
    expanded = expand_home_path(value.strip())
    if not os.path.isabs(expanded):
        expanded = os.path.join(base or get_config_dir(), expanded)
    return os.path.abspath(expanded)


def _text(data: dict, key: str) -> str:
    """读取表单字符串字段并去除首尾空白。"""
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


def _parse_positive_number(value):
    """解析大于 0 的数字，解析失败返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if number > 0 else None


def _parse_bool(value):
    """解析布尔值（接受布尔与 "true"/"false" 字符串），解析失败返回 None。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return None
