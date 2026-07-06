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


def check_itinerary_reminders_job():
    try:
        from django.conf import settings
        from django.utils.timezone import now, localtime
        from linebot.v3.messaging import (
            ApiClient,
            Configuration,
            MessagingApi,
            PushMessageRequest,
            TextMessage,
        )

        from line_manager.models import Itinerary

        current_time = now()
        # 查詢未通知行程
        itineraries = Itinerary.objects.filter(is_notified=False)

        configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)

        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)

            for item in itineraries:
                from datetime import timedelta
                # 計算應該提醒的時間點
                reminder_time = item.date_time - timedelta(minutes=item.notify_minutes_before)

                # 判定是否達到通知時間（且行程開始時間未過去超過 15 分鐘，以防過期推播）
                if current_time >= reminder_time and current_time <= item.date_time + timedelta(minutes=15):
                    target_id = None
                    if item.group_id:
                        target_id = item.group_id
                    else:
                        try:
                            target_id = item.user.line_profile.line_user_id
                        except AttributeError:
                            print(f"⚠️ 行程 #{item.pk} 找不到綁定的 LINE 用戶，無法發送通知。")
                            continue

                    if not target_id:
                        continue

                    # 驗證是否為符合 LINE 格式的有效 ID（避免開發或測試環境中的 UUID 等模擬 ID 導致 LINE API 報錯）
                    import re
                    if not re.match(r"^[UCR][0-9a-fA-F]{32}$", target_id):
                        print(f"⚠️ 行程 #{item.pk} 的目標 ID [{target_id}] 格式不符合 LINE 規範，自動忽略並標記為已處理。")
                        item.is_notified = True
                        item.save()
                        continue

                    # 讀取解密資料
                    title_dec = item.title
                    location_dec = item.location
                    notes_dec = item.notes

                    # 取得發起人的 LINE 顯示名稱
                    try:
                        creator_name = item.user.line_profile.line_display_name or item.user.username
                    except AttributeError:
                        creator_name = item.user.username

                    msg_content = (
                        f"🔔 行程提醒\n"
                        f"================\n"
                        f"【{title_dec}】將於 {localtime(item.date_time).strftime('%Y-%m-%d %H:%M')} 開始！\n"
                        f"📍 地點：{location_dec}\n"
                        f"📝 備註：{notes_dec or '無'}"
                    )

                    if item.group_id:
                        msg_content += f"\n\n(由 {creator_name} 發起)"

                    try:
                        api_instance.push_message_with_http_info(
                            PushMessageRequest(
                                to=target_id, messages=[TextMessage(text=msg_content)]
                            )
                        )
                        # 標記為已通知
                        item.is_notified = True
                        item.save()

                        # 取得推播對象資訊 (如果有群組則嘗試抓取群組名稱)
                        target_info = f"個人 [{target_id}]"
                        if item.group_id:
                            try:
                                group_summary = api_instance.get_group_summary(item.group_id)
                                target_info = f"群組 [{group_summary.group_name}] ({item.group_id})"
                            except Exception:
                                target_info = f"群組 [{item.group_id}]"

                        push_time_str = localtime(now()).strftime("%Y-%m-%d %H:%M:%S")
                        print(f"✅ 已成功推播行程 #{item.pk} 通知至 {target_info} (時間: {push_time_str})")
                    except Exception as e:
                        print(f"❌ 推播行程 #{item.pk} 通知失敗: {e}")

    except Exception as e:
        print(f"❌ [排程任務] 執行行程提醒檢查時發生錯誤: {e}")


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

            #! 新增：行程提醒排程，每 1 分鐘檢查一次
            scheduler.add_job(
                check_itinerary_reminders_job,
                trigger=CronTrigger(minute="*"),
                id="itinerary_reminder_check",
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
