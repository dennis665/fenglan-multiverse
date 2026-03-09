from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NoticesConfig(AppConfig):
    name = 'notices'
    verbose_name = _("系統公告")
