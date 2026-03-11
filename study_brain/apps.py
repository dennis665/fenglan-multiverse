from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StudyBrainConfig(AppConfig):
    """設定 AI 教材大腦 App"""

    name = "study_brain"
    verbose_name = _("AI 教材大腦")
