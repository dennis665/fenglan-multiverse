import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore

logger = logging.getLogger(__name__)


def update_prices_job():
    print("⏳ [排程任務] 開始執行每日收盤後股價更新...")
    try:
        call_command("update_prices")  # * 呼叫你的爬蟲指令
        print("✅ [排程任務] 每日股價更新完成！")
    except Exception as e:
        print(f"❌ [排程任務] 執行失敗: {e}")


# def test_job():
#     print("🤖 測試排程執行中... 滴答！(每 5 秒觸發)")


class Command(BaseCommand):
    help = "啟動背景排程器，每天定時更新股價"

    def handle(self, *args, **options):
        #! 初始化排程器，並綁定 Django 的時區
        scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        try:
            #! 設定排程時間：每天 (週一到週五) 的下午 14:30 執行
            scheduler.add_job(
                update_prices_job,  # * 直接呼叫外面的函式
                trigger=CronTrigger(day_of_week="mon-fri", hour=14, minute=30),
                id="daily_stock_update",
                max_instances=1,
                replace_existing=True,
            )

            self.stdout.write(self.style.SUCCESS("啟動成功！排程器正在背景監聽中..."))
            self.stdout.write(self.style.SUCCESS("⏰ 已設定為：每週一至週五 14:30 自動更新股價。"))
            self.stdout.write(self.style.WARNING("按 Ctrl+C 可以安全關閉此排程器。"))

            #! 測試用
            # scheduler.add_job(
            #     test_job,
            #     trigger=IntervalTrigger(seconds=5),  # * 改用 IntervalTrigger
            #     id="test_5_seconds_job",  # * 給它一個測試用的 ID
            #     max_instances=1,
            #     replace_existing=True,
            # )

            #! 開始阻擋並持續運行
            scheduler.start()

            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("🛑 收到關閉訊號，排程器已停止。"))
            scheduler.shutdown()
