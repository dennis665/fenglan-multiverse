import csv
import os
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from line_manager.models import Drama, LineProfile, UserDramaProgress, DramaRecommendation


def normalize_title(title):
    if not title:
        return ""
    t = str(title).strip()
    t = t.replace("的主視覺圖", "").replace("《", "").replace("》", "").replace("『", "").replace("』", "").strip()
    t = re.sub(r'[~∼〜〰⁓]', '～', t)
    t = t.replace(':', '：')
    t = t.replace('!', '！').replace('?', '？')
    t = re.sub(r'[\s\u3000]+', ' ', t).strip()
    t = re.sub(r'：+', '：', t)
    t = re.sub(r'～+', '～', t)
    return t


def get_match_key(title):
    t = normalize_title(title).lower()
    return re.sub(r'[^\w\u4e00-\u9fff]', '', t)


class Command(BaseCommand):
    help = "讀取 test/tv_dramas.csv 與 test/movie_dramas.csv 兩份 CSV 並與 DB 進行純粹比對同步 (缺則補，多則刪)"

    def handle(self, *args, **options):
        tv_csv_path = os.path.join(settings.BASE_DIR, "test", "tv_dramas.csv")
        movie_csv_path = os.path.join(settings.BASE_DIR, "test", "movie_dramas.csv")

        csv_map = {}
        total_csv_rows = 0

        def load_csv(path, label):
            nonlocal total_csv_rows
            if not os.path.exists(path):
                self.stdout.write(self.style.WARNING(f"⚠️ 找不到 CSV 檔: {path}"))
                return
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for r in reader:
                    title = normalize_title(r.get('title', ''))
                    cat = r.get('category', '').strip()
                    if not title:
                        continue
                    mk = get_match_key(title)
                    key = (mk, cat)
                    if key not in csv_map:
                        csv_map[key] = {
                            'title': title,
                            'category': cat,
                            'total_seasons': r.get('total_seasons', 1),
                            'total_episodes': r.get('total_episodes', 0),
                            'info_links': r.get('info_links', '[]')
                        }
                        count += 1
                        total_csv_rows += 1
            self.stdout.write(self.style.SUCCESS(f"已讀取 {count} 筆來自 {label} ({path})"))

        load_csv(tv_csv_path, "TV 動畫季番 CSV")
        load_csv(movie_csv_path, "動畫電影 CSV")

        self.stdout.write(self.style.WARNING(f"兩份 CSV 總計不重複劇集筆數: {total_csv_rows}"))

        # 取得或建立系統匯入者帳戶
        system_user, _ = User.objects.get_or_create(username="system_importer")
        LineProfile.objects.get_or_create(
            user=system_user,
            defaults={"line_user_id": "U_system_importer_dummy", "line_display_name": "系統管理員"}
        )

        # 比對 DB
        db_dramas = list(Drama.objects.all())
        self.stdout.write(self.style.WARNING(f"目前資料庫 Drama 總筆數: {len(db_dramas)}"))

        deleted_count = 0
        retained_count = 0
        db_existing_keys = set()

        for d in db_dramas:
            mk = get_match_key(d.title)
            key = (mk, d.category)
            if key in csv_map:
                db_existing_keys.add(key)
                retained_count += 1
            else:
                # 不在 2 份 CSV 總合裡的 DB 紀錄 -> 移除
                for progress in list(d.progresses.all()):
                    progress.delete()
                DramaRecommendation.objects.filter(drama=d).delete()
                d.delete()
                deleted_count += 1

        self.stdout.write(self.style.SUCCESS(f"資料庫清理：保留 {retained_count} 筆符合項，移除 {deleted_count} 筆多餘項"))

        # 新增缺少的劇集
        created_count = 0
        for key, row in csv_map.items():
            if key not in db_existing_keys:
                Drama.objects.create(
                    creator=system_user,
                    title=row['title'],
                    category=row['category'],
                    total_seasons=int(row['total_seasons']) if str(row['total_seasons']).isdigit() else 1,
                    total_episodes=int(row['total_episodes']) if str(row['total_episodes']).isdigit() else 0,
                    info_links=row['info_links']
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"資料庫匯入：新增 {created_count} 筆缺失劇集"))

        final_db_count = Drama.objects.count()
        self.stdout.write(self.style.SUCCESS(f"[IMPORT SUCCESS] 同步完成！兩份 CSV 總筆數: {total_csv_rows} | 最終 DB 筆數: {final_db_count}"))
