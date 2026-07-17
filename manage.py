#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import re
import sys
import time
from datetime import datetime

#! 強制清除環境變數，讓 Python 回去抓預設路徑
if "TCL_LIBRARY" in os.environ:
    del os.environ["TCL_LIBRARY"]
if "TK_LIBRARY" in os.environ:
    del os.environ["TK_LIBRARY"]


#! 啟動訊息調整
class DjangoTranslator:
    def __init__(self, stream, start_time):
        self.stream = stream
        self.start_time = start_time
        self.has_printed_duration = False
        self.translations = {
            "Performing system checks...": "🔍 正在執行系統檢查...",
            "System check identified no issues (0 silenced).": "✅ 系統檢查完成，未發現任何問題。",
            "Django version": "📦 Django 版本",
            "using settings": "⚙️  使用設定檔",
            "Starting development server at": "🚀 開發伺服器已啟動，請訪問：",
            "Starting ASGI/Daphne version 4.2.1 development server at": "🚀 ASGI/Daphne 版本 4.2.1 開發伺服器啟動於：",
            "Quit the server with": "🛑 停止伺服器請按",
        }

    def write(self, data):
        #! 排除非必要的警告訊息
        if "WARNING: This is a development server" in data or "production setting" in data:
            return

        #! 轉換日期格式 (捕捉 Month DD, YYYY 並轉為 YYYY/MM/DD)
        #! 匹配範例: January 27, 2026
        date_pattern = r"^([A-Z][a-z]+) (\d{1,2}), (\d{4})"
        match = re.search(date_pattern, data)
        if match:
            month_str, day, year = match.groups()
            try:
                #! 將英文月份轉為數字格式
                dt = datetime.strptime(f"{month_str} {day} {year}", "%B %d %Y")
                new_date = dt.strftime("%Y/%m/%d")
                data = data.replace(f"{month_str} {day}, {year}", f"🕒 啟動時間：{new_date}")
            except ValueError:
                pass

        #! 進行中文翻譯替換
        translated_data = data
        for eng, chi in self.translations.items():
            if eng in translated_data:
                translated_data = translated_data.replace(eng, chi)

        #! 偵測到啟動成功訊息時，計算並補上耗時
        if (
            "Starting ASGI/Daphne version 4.2.1 development server at" in data
            and not self.has_printed_duration
        ):
            duration = time.time() - self.start_time
            translated_data = translated_data.rstrip() + f" (⚡ 總啟動耗時：{duration:.1f} 秒)\n"
            self.has_printed_duration = True

        try:
            self.stream.write(translated_data)
        except UnicodeEncodeError:
            encoding = getattr(self.stream, 'encoding', 'ascii') or 'ascii'
            try:
                safe_data = translated_data.encode(encoding, errors='replace').decode(encoding)
                self.stream.write(safe_data)
            except Exception:
                pass

    def flush(self):
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)


def main():
    """Run administrative tasks."""
    start_time = time.time()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    #! 在啟動 runserver 時掛載翻譯過濾器
    if "runserver" in sys.argv:
        sys.stdout = DjangoTranslator(sys.stdout, start_time)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
