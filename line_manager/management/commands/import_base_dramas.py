import os
import csv
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from line_manager.models import Drama, LineProfile

class Command(BaseCommand):
    help = "讀取 base_dramas.csv 並將不存在的基礎劇集匯入資料庫"

    def handle(self, *args, **options):
        csv_path = os.path.join(settings.BASE_DIR, "line_manager", "resources", "base_dramas.csv")
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.WARNING(f"⚠️ 找不到基礎劇集 CSV 檔: {csv_path}"))
            return

        self.stdout.write(self.style.WARNING("正在讀取基礎劇集清單並比對資料庫..."))

        # 取得或建立系統匯入者帳戶
        importer_user, _ = User.objects.get_or_create(username="system_importer")
        LineProfile.objects.get_or_create(
            user=importer_user,
            defaults={
                "line_user_id": "U_system_importer_dummy",
                "line_display_name": "新番匯入小助手"
            }
        )

        # 由於 title 為 EncryptedCharField，無法在資料庫層面直接過濾比對，故加載至記憶體中比對
        existing_titles = {d.title for d in Drama.objects.all()}
        
        created_count = 0
        total_rows = 0

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("title", "").strip()
                if not title:
                    continue

                total_rows += 1
                if title in existing_titles:
                    continue

                category = row.get("category", "其他").strip()
                try:
                    total_seasons = int(row.get("total_seasons", 1))
                except ValueError:
                    total_seasons = 1
                try:
                    total_episodes = int(row.get("total_episodes", 0))
                except ValueError:
                    total_episodes = 0
                info_links = row.get("info_links", "[]").strip()

                # 建立新劇集
                Drama.objects.create(
                    title=title,
                    category=category,
                    total_seasons=total_seasons,
                    total_episodes=total_episodes,
                    info_links=info_links,
                    creator=importer_user
                )
                existing_titles.add(title)
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"📊 基礎劇集比對完成！CSV 總筆數: {total_rows} | 新建立: {created_count} 筆。"))
