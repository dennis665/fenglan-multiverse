import logging
import time
from contextlib import contextmanager

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
        """內部工具：解析 Exception，過濾掉套件庫路徑，找出專案內的報錯位置"""
        tb = error.__traceback__
        filename = "未知"
        lineno = "未知"

        if tb:
            #! 我們要從頂層往底層找，保留最後一個「非套件」的位置
            curr_tb = tb
            while curr_tb:
                f_code = curr_tb.tb_frame.f_code
                f_name = f_code.co_filename

                #! 判斷邏輯：如果檔名不包含 Python 套件常見的路徑關鍵字
                #! 這裡過濾掉 .venv, site-packages, Lib 等
                if "site-packages" not in f_name and "lib" not in f_name and "<frozen" not in f_name:
                    filename = f_name
                    lineno = curr_tb.tb_lineno
                    #! 我們不 break，因為我們想找的是「你自己程式碼中，最接近報錯點」的那一行
                    #! 如果你想要「最外層的 try-except」那一行，就在這裡加 break

                curr_tb = curr_tb.tb_next

            #! 如果遍歷完都沒找到（代表真的是系統級錯誤），才抓最底層的
            if filename == "未知":
                while tb.tb_next:
                    tb = tb.tb_next
                filename = tb.tb_frame.f_code.co_filename
                lineno = tb.tb_lineno

        return str(error), filename, lineno

    @classmethod
    def _safe_print(cls, text: str):
        try:
            print(text)
        except UnicodeEncodeError:
            import sys
            encoding = sys.stdout.encoding or 'ascii'
            try:
                # 使用 terminal 的編碼進行編碼，不支援的字元（如 emoji）會被替換為問號，解碼後安全印出，避免崩潰
                safe_text = text.encode(encoding, errors='replace').decode(encoding)
                print(safe_text)
            except Exception:
                pass

    @classmethod
    def error_print(cls, error: Exception | str = "", message: str = ""):
        if isinstance(error, Exception):
            err_msg, filename, lineno = cls._parse_error(error)
            cls._safe_print(f"{cls.FAIL}{message}\n錯誤訊息：{err_msg}\n檔名：{filename}\n行數：{lineno}{cls.ENDC}")
        elif message:
            cls._safe_print(f"{cls.FAIL}{message}{cls.ENDC}")
        elif isinstance(error, str):
            cls._safe_print(f"{cls.FAIL}{error}{cls.ENDC}")

    @classmethod
    def highlight_print(cls, message: str = ""):
        cls._safe_print(f"{cls.OKCYAN}{message}{cls.ENDC}")

    @classmethod
    def warning_print(cls, message: str = ""):
        cls._safe_print(f"{cls.WARNING}{message}{cls.ENDC}")

    @classmethod
    def processing_print(cls, message: str = ""):
        cls._safe_print(f"{cls.PROCESSING}{message}{cls.ENDC}")

    @classmethod
    def paragraph_print(cls, message: str = ""):
        cls._safe_print(f"{cls.HEADER}{message}{cls.ENDC}")


def jinfo(message: str = ""):
    """一般資訊紀錄 (藍色)"""
    logging.info(f"{Colors.OKBLUE}{message}{Colors.ENDC}")


def jdebug(message: str = ""):
    """除錯資訊紀錄 (青色)"""
    logging.debug(f"{Colors.OKCYAN}[DEBUG] {message}{Colors.ENDC}")


def jinfo_error(error: Exception | str = "", message: str = ""):
    """錯誤紀錄 (紅色)"""
    if isinstance(error, Exception):
        err_msg, filename, lineno = Colors._parse_error(error)
        output = f"{Colors.FAIL}\n{message}\n錯誤訊息：{err_msg}\n檔名：{filename}\n行數：{lineno}\n{Colors.ENDC}"
        logging.error(output)
    else:
        msg_content = message or error
        logging.error(f"{Colors.FAIL}\n{msg_content}\n{Colors.ENDC}")


@contextmanager
#! 定義一個計時器，用於測量區塊程式碼的執行時間
def time_tracker(name):
    start = time.time()
    yield
    #! 在 Console 快速辨識耗時大戶
    Colors.paragraph_print(f"🕒 [{name}] 載入耗時：{time.time() - start:.1f} 秒")
