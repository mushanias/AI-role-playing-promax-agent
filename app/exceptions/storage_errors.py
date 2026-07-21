"""储存相关异常"""

from app.exceptions.base import BaseAppException


class StorageException(BaseAppException):
    """储存相关错误的基类"""


class StorageCorruptionError(StorageException):
    """储存文件损坏（JSON 解析失败）"""


class StorageIOError(StorageException):
    """储存文件读写失败（权限、磁盘满等）"""


class StorageNotFoundError(StorageException):
    """请求读取的储存对象不存在"""


class StorageConflictError(StorageException):
    """创建储存对象时发生身份冲突"""
