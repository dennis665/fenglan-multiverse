from django.apps import AppConfig


class LineManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'line_manager'

    def ready(self):
        # 啟動時不再自動註冊/更新 LINE 圖文選單
        # 如需註冊或更新圖文選單，請手動執行: python manage.py register_rich_menu
        pass
