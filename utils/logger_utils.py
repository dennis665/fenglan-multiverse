import logging

#! 初始化基本的 logging 配置 (如果其他地方沒設定的話)
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
)

class Colors:
    HEADER = "\033[95m"  #! 淡紫色
    OKBLUE = "\033[94m"  #! 藍色
    OKCYAN = "\033[96m"  #! 青色
    PROCESSING = "\033[92m"  #! 綠色
    WARNING = "\033[93m"  #! 黃色
    FAIL = "\033[91m"  #! 紅色
    ENDC = "\033[0m"  #! 重置顏色和樣式
    BOLD = "\033[1m"  #! 粗體
    UNDERLINE = "\033[4m"  #! 下劃線

    @staticmethod
    def _parse_error(error: Exception):
        """內部工具：解析 Exception 的詳細資訊"""
        tb = error.__traceback__
        filename = "未知"
        lineno = "未知"
        if tb:
            #! 取得最後一筆追蹤紀錄 (實際報錯的位置)
            while tb.tb_next:
                tb = tb.tb_next
            filename = tb.tb_frame.f_code.co_filename
            lineno = tb.tb_lineno
        return str(error), filename, lineno

    @classmethod
    def error_print(cls, error: Exception | str = "", message: str = ""):
        if isinstance(error, Exception):
            err_msg, filename, lineno = cls._parse_error(error)
            print(f"{cls.FAIL}{message}\n錯誤訊息：{err_msg}\n檔名：{filename}\n行數：{lineno}{cls.ENDC}")
        elif message:
            print(f"{cls.FAIL}{message}{cls.ENDC}")
        elif isinstance(error, str):
            print(f"{cls.FAIL}{error}{cls.ENDC}")

    @classmethod
    def highlight_print(cls, message: str = ""):
        print(f"{cls.OKCYAN}{message}{cls.ENDC}")

    @classmethod
    def warning_print(cls, message: str = ""):
        print(f"{cls.WARNING}{message}{cls.ENDC}")

    @classmethod
    def processing_print(cls, message: str = ""):
        print(f"{cls.PROCESSING}{message}{cls.ENDC}")

    @classmethod
    def paragraph_print(cls, message: str = ""):
        print(f"{cls.HEADER}{message}{cls.ENDC}")


def jinfo(message: str = ""):
    """一般資訊紀錄 (藍色)"""
    logging.info(f"{Colors.OKBLUE}{message}{Colors.ENDC}", stacklevel=2)


def jdebug(message: str = ""):
    """除錯資訊紀錄 (青色)"""
    logging.debug(f"{Colors.OKCYAN}[DEBUG] {message}{Colors.ENDC}", stacklevel=2)


def jinfo_error(error: Exception | str = "", message: str = ""):
    """錯誤紀錄 (紅色)"""
    if isinstance(error, Exception):
        err_msg, filename, lineno = Colors._parse_error(error)
        output = f"{Colors.FAIL}\n{message}\n錯誤訊息：{err_msg}\n檔名：{filename}\n行數：{lineno}\n{Colors.ENDC}"
        logging.error(output, stacklevel=2)
    else:
        msg_content = message or error
        logging.error(f"{Colors.FAIL}\n{msg_content}\n{Colors.ENDC}", stacklevel=2)
