"""日志配置模块：配置全局日志，终端 + 文件双输出"""
import os
import logging


def setup_logging() -> None:
    """配置全局日志
    - 终端：INFO 及以上，简洁格式
    - 文件：DEBUG 及以上，详细格式（含时间戳）
    - 日志文件位置：logs/app.log
    """
    # 确保日志目录存在
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 日志格式
    # 终端格式：简洁，只显示级别和消息
    console_format = "%(levelname)s: %(message)s"
    # 文件格式：详细，含时间、模块名、行号
    file_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    # 终端 handler：输出到控制台，级别 INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(console_format))

    # 文件 handler：输出到文件，级别 DEBUG
    file_handler = logging.FileHandler(
        os.path.join(log_dir, "app.log"),
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(file_format))

    # 配置 root logger（所有模块的日志都经过它）
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 总开关：全记
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)