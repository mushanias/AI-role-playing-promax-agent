"""项目根异常：所有自定义异常的祖先"""


class BaseAppException(Exception):
    """项目所有自定义异常的基类
    统一带 message 属性，方便日志记录和给用户提示
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)