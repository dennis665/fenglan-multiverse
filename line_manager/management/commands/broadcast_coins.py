# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from line_manager.models import LineProfile
from line_manager.views import broadcast_coins_to_all_users

class Command(BaseCommand):
    help = '推播 Flex Box 禮物卡至所有加 LINE Bot 的使用者，點擊進入 LIFF 領取指定金額金幣'

    def add_arguments(self, parser):
        parser.add_argument('--coins', type=int, default=800, help='要發放給每位使用者的金幣數量 (預設: 800)')
        parser.add_argument('--message', type=str, default='🎉 感謝大家支持！休閒小站新增小八貓發放金幣800，請點擊領取！', help='推播通知訊息內容')
        parser.add_argument('--title', type=str, default='🎉 感謝大家支持！', help='Flex Box 大標題')

    def handle(self, *args, **options):
        coins = options['coins']
        msg_text = options['message']
        title_text = options['title']

        self.stdout.write(self.style.SUCCESS(f"[START] Beginning Flex Box Push for {coins} coins..."))

        # 過濾有效的 line_user_id (LINE 用戶 ID 通常為 'U' 開頭的 33 字元字串)
        if not LineProfile.objects.filter(line_user_id__startswith='U').exists():
            self.stdout.write(self.style.WARNING("[WARN] No valid LINE profiles found."))
            return

        #! 與 LINE「發放金幣」指令共用同一份禮物卡與 multicast 發送邏輯 (每 500 人一次 API 呼叫)
        success_count, fail_count = broadcast_coins_to_all_users(coins, msg_text, title_text)

        self.stdout.write(self.style.SUCCESS(f"\n[DONE] Flex Box broadcast completed! Success: {success_count}, Failed: {fail_count}."))
