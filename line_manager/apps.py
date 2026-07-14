import sys
import threading
import time
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class LineManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'line_manager'

    def ready(self):
        # 避免在執行 migrate, makemigrations, test, check, collectstatic 等管理指令時觸發
        if any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'test', 'check', 'collectstatic', 'register_rich_menu', 'import_base_dramas']):
            return

        # 使用背景執行緒進行非同步自動註冊圖文選單與基礎清單匯入，防止因 LINE API 連線阻礙 Gunicorn/Django 啟動
        def auto_register():
            # 延遲 5 秒執行，確保伺服器已啟動完成
            time.sleep(5)
            try:
                from django.core.management import call_command
                logger.info("🤖 正在自動註冊/更新 LINE 雙區圖文選單...")
                call_command('register_rich_menu')
            except Exception as e:
                logger.warning(f"⚠️ 背景自動註冊圖文選單失敗: {e}")

            try:
                from django.core.management import call_command
                logger.info("🤖 正在自動比對並匯入基礎新番清單...")
                call_command('import_base_dramas')
            except Exception as e:
                logger.warning(f"⚠️ 自動匯入基礎劇集失敗: {e}")

        threading.Thread(target=auto_register, daemon=True).start()
