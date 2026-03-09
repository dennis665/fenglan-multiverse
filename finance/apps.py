from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FinanceConfig(AppConfig):
    name = 'finance'
    verbose_name = _("財務與商城")
