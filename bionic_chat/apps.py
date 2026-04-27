from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BionicChatConfig(AppConfig):
    name = "bionic_chat"
    verbose_name = _("仿生人對話系統")  # * 設定後台顯示的繁體中文名稱
