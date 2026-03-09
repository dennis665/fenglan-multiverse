from django.apps import AppConfig


class InvestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest"  # * 確認這裡是你的 app 名稱

    def ready(self):
        #! 啟動時載入訊號 (這行非常重要！)
        import invest.signals  # noqa: F401
