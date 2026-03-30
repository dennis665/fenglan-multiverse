from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SurvivorConfig(AppConfig):
    name = "games"
    verbose_name = _("遊戲中心")
