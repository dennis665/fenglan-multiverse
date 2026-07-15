import os

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "註冊並綁定 LINE 官方帳號的雙區圖文選單 (Rich Menu)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--image-path",
            type=str,
            required=False,
            help="Rich Menu 背景圖片的路徑 (預設為 static/images/rich_menu_bg.jpg)"
        )

    def handle(self, *args, **options):
        image_path = options.get("image_path")
        if not image_path:
            image_path = os.path.join(settings.BASE_DIR, "static", "images", "rich_menu_bg.jpg")

        if not os.path.exists(image_path):
            self.stdout.write(self.style.ERROR(f"❌ 圖片路徑不存在: {image_path}"))
            return

        self.stdout.write(self.style.WARNING("正在註冊 Rich Menu..."))



        # 1. 建立 Rich Menu JSON 定義
        # 左右對稱雙按鈕選單 (2500 x 843)
        liff_id = settings.LINE_LIFF_ID
        rich_menu_data = {
            "size": {
                "width": 2500,
                "height": 843
            },
            "selected": True,
            "name": "CSI Portal 雙區選單",
            "chatBarText": "選單功能",
            "areas": [
                {
                    "bounds": {
                        "x": 0,
                        "y": 0,
                        "width": 1250,
                        "height": 843
                    },
                    "action": {
                        "type": "uri",
                        "label": "出門行程",
                        "uri": f"https://liff.line.me/{liff_id}"
                    }
                },
                {
                    "bounds": {
                        "x": 1250,
                        "y": 0,
                        "width": 1250,
                        "height": 843
                    },
                    "action": {
                        "type": "uri",
                        "label": "追劇行程",
                        "uri": f"https://liff.line.me/{liff_id}?page=drama"
                    }
                }
            ]
        }

        # 取得目前已存在的 Rich Menu 列表進行比對
        try:
            list_url = "https://api.line.me/v2/bot/richmenu/list"
            list_headers = {
                "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}"
            }
            list_res = requests.get(list_url, headers=list_headers)
            if list_res.status_code == 200:
                existing_menus = list_res.json().get("richmenus", [])
                for menu in existing_menus:
                    if menu.get("name") == "CSI Portal 雙區選單":
                        existing_areas = menu.get("areas", [])

                        # 比對各按鈕區域的連結，完全一致就直接重用並設為預設
                        match = True
                        if len(existing_areas) != len(rich_menu_data["areas"]):
                            match = False
                        else:
                            for idx, area in enumerate(existing_areas):
                                if area.get("action", {}).get("uri") != rich_menu_data["areas"][idx]["action"]["uri"]:
                                    match = False
                                    break

                        if match:
                            self.stdout.write(self.style.SUCCESS(f"ℹ️ 已存在完全一致的選單 (ID: {menu['richMenuId']})，無需重複註冊。"))
                            # 確保它是預設選單
                            default_url = f"https://api.line.me/v2/bot/user/all/richmenu/{menu['richMenuId']}"
                            requests.post(default_url, headers=list_headers)
                            return
                        else:
                            # 結構有更新，刪除該舊選單
                            self.stdout.write(self.style.WARNING(f"🗑️ 檢測到選單結構有更新，正在刪除舊選單 (ID: {menu['richMenuId']})..."))
                            delete_url = f"https://api.line.me/v2/bot/richmenu/{menu['richMenuId']}"
                            requests.delete(delete_url, headers=list_headers)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️ 查詢選單列表發生錯誤: {e}"))

        try:
            # 建立 Rich Menu
            url = "https://api.line.me/v2/bot/richmenu"
            headers = {
                "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
            res = requests.post(url, json=rich_menu_data, headers=headers)
            if res.status_code != 200:
                self.stdout.write(self.style.ERROR(f"❌ LINE Rich Menu 建立失敗: {res.text}"))
                return

            rich_menu_id = res.json()["richMenuId"]
            self.stdout.write(self.style.SUCCESS(f"✅ Rich Menu 建立成功，ID: {rich_menu_id}"))

            # 2. 上傳背景圖片
            self.stdout.write(self.style.WARNING("正在上傳選單圖片..."))
            upload_url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"
            upload_headers = {
                "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
            }
            with open(image_path, "rb") as img_file:
                upload_res = requests.post(upload_url, data=img_file, headers=upload_headers)

            if upload_res.status_code != 200:
                self.stdout.write(self.style.ERROR(f"❌ 圖片上傳失敗: {upload_res.text}"))
                return

            self.stdout.write(self.style.SUCCESS("✅ 背景圖片上傳成功！"))

            # 3. 設為該帳號的預設 Rich Menu
            self.stdout.write(self.style.WARNING("正在套用預設選單..."))
            default_url = f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}"
            default_res = requests.post(default_url, headers={"Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}"})

            if default_res.status_code != 200:
                self.stdout.write(self.style.ERROR(f"❌ 設定預設選單失敗: {default_res.text}"))
                return

            self.stdout.write(self.style.SUCCESS("🎉 成功！雙區圖文選單已生效並套用為預設。"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 發生異常錯誤: {e}"))
