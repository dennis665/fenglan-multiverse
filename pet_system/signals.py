from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils.timezone import now

from .models import DailyLoginLog


@receiver(user_logged_in)
def record_daily_login(sender, request, user, **kwargs):
    # 取得當地當前日期
    today = now().date()
    # 建立今日的登入紀錄，防刷
    DailyLoginLog.objects.get_or_create(user=user, login_date=today)
