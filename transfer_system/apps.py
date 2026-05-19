from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TransferSystemConfig(AppConfig):
    """應用程式設定檔"""

    name = "transfer_system"
    verbose_name = _("物品轉移系統")
