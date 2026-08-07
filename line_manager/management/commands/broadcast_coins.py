# -*- coding: utf-8 -*-
import json
import uuid
import urllib.parse
from django.core.management.base import BaseCommand
from django.conf import settings
from line_manager.models import LineProfile
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    FlexMessage,
    FlexContainer,
)

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
        gift_id = f"gift_{uuid.uuid4().hex[:8]}"

        self.stdout.write(self.style.SUCCESS(f"[START] Beginning Flex Box Push for {coins} coins..."))

        configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
        # 過濾有效的 line_user_id (LINE 用戶 ID 通常為 'U' 開頭的 33 字元字串)
        profiles = LineProfile.objects.filter(line_user_id__startswith='U')
        if not profiles.exists():
            self.stdout.write(self.style.WARNING("[WARN] No valid LINE profiles found."))
            return

        success_count = 0
        fail_count = 0

        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)

            for prof in profiles:
                if prof.line_user_id and len(prof.line_user_id) >= 30:
                    encoded_msg = urllib.parse.quote(str(msg_text))
                    liff_claim_url = f"https://liff.line.me/{settings.LINE_LIFF_ID}?page=pet&claim_coins={coins}&gift_id={gift_id}&gift_msg={encoded_msg}"

                    flex_contents = {
                        "type": "bubble",
                        "size": "mega",
                        "header": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "🎁 禮物獎勵領取通知",
                                    "weight": "bold",
                                    "size": "sm",
                                    "color": "#ffffff"
                                }
                            ],
                            "backgroundColor": "#ff9a9e",
                            "paddingAll": "15px"
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": title_text,
                                    "weight": "bold",
                                    "size": "lg",
                                    "color": "#111111",
                                    "wrap": True
                                },
                                {
                                    "type": "text",
                                    "text": msg_text,
                                    "size": "sm",
                                    "color": "#555555",
                                    "wrap": True,
                                    "margin": "md"
                                },
                                {
                                    "type": "box",
                                    "layout": "baseline",
                                    "contents": [
                                        {
                                            "type": "text",
                                            "text": "獎勵金額：",
                                            "size": "xs",
                                            "color": "#888888"
                                        },
                                        {
                                            "type": "text",
                                            "text": f"+{coins} 金幣",
                                            "weight": "bold",
                                            "size": "md",
                                            "color": "#e67e22"
                                        }
                                    ],
                                    "margin": "lg"
                                }
                            ],
                            "paddingAll": "20px"
                        },
                        "footer": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri",
                                        "label": f"🎁 點擊領取 {coins} 金幣",
                                        "uri": liff_claim_url
                                    },
                                    "style": "primary",
                                    "color": "#ff9a9e",
                                    "height": "sm"
                                }
                            ],
                            "paddingAll": "15px"
                        }
                    }

                    try:
                        api_instance.push_message(
                            PushMessageRequest(
                                to=prof.line_user_id,
                                messages=[
                                    FlexMessage(
                                        alt_text=f"🎁【領取通知】{title_text} (+{coins}金幣)",
                                        contents=FlexContainer.from_dict(flex_contents)
                                    )
                                ]
                            )
                        )
                        success_count += 1
                        self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Pushed Flex Box to {prof.line_display_name} (+{coins} coins)"))
                    except Exception as push_err:
                        fail_count += 1
                        self.stdout.write(self.style.WARNING(f"[FAIL] Push error for {prof.line_display_name}: {push_err}"))

        self.stdout.write(self.style.SUCCESS(f"\n[DONE] Flex Box broadcast completed! Success: {success_count}, Failed: {fail_count}."))
