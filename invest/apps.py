from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InvestConfig(AppConfig):
    name = "invest"  # * 確認這裡是你的 app 名稱
    verbose_name = _("投資理財")

    def ready(self):
        #! 啟動時載入訊號 (這行非常重要！)
        import invest.signals  # noqa: F401
