# -*- coding: utf-8 -*-
import csv
import json
import os
import re
import subprocess
import time
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from line_manager.models import Drama, LineProfile, DramaRecommendation

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

headers_curl = [
    "curl.exe", "-s",
    "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "-H", "Accept-Language: zh-TW,zh;q=0.9,en-US;q=0.8"
]

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


def run_daily_drama_update():
    """ 每日 16:00 執行：抓取最新 TV 季番與動畫電影，更新 resources CSV 與 DB """
    print("\n==================================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [Daily Scheduler] Updating TV (2026/07+) and Movie (2026+)...")
    print("==================================================")

    res_dir = os.path.join(settings.BASE_DIR, "line_manager", "resources")
    test_dir = os.path.join(settings.BASE_DIR, "test")
    os.makedirs(res_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)

    res_tv_csv = os.path.join(res_dir, "tv_dramas.csv")
    res_movie_csv = os.path.join(res_dir, "movie_dramas.csv")
    test_tv_csv = os.path.join(test_dir, "tv_dramas.csv")
    test_movie_csv = os.path.join(test_dir, "movie_dramas.csv")

    fieldnames = ['title', 'category', 'total_seasons', 'total_episodes', 'info_links', 'image_url']

    # ----------------------------------------------------
    # Part 1. 抓取 TV 季番 (動畫化決定 + 2026年7月(含)之後)
    # ----------------------------------------------------
    print("\n[TV] [1/2] 正在抓取 TV 動畫 (動畫化決定 & 2026年7月(含)之後)...")
    tv_seasons = [f"{y}{m:02d}" for y in range(2026, 2029) for m in [1, 4, 7, 10] if not (y == 2026 and m < 7)]
    
    aid_image_cache = {}

    def get_anime_images(aid):
        if aid in aid_image_cache:
            return aid_image_cache[aid]
        if not aid or not str(aid).isdigit():
            return ""
        url = f"https://youranimes.tw/animes/{aid}"
        cmd = headers_curl + [url]
        try:
            raw_html = subprocess.check_output(cmd, timeout=10).decode('utf-8', errors='ignore')
        except Exception:
            raw_html = ""
        if not raw_html:
            aid_image_cache[aid] = ""
            return ""

        pattern = re.compile(rf'https://d28s5ztqvkii64\.cloudfront\.net/images/anime/{aid}/([^"\'\s\\<>]+)')
        matches = pattern.findall(raw_html)
        
        bases = []
        base_best_file = {}
        for m in matches:
            base = re.sub(r'(_2x|_thumbnail)?\.(webp|jpg|png|jpeg)', '', m)
            if not base:
                continue
            if base not in bases:
                bases.append(base)
                
            if base not in base_best_file:
                base_best_file[base] = m
            else:
                cur = base_best_file[base]
                if "_2x.webp" in m:
                    base_best_file[base] = m
                elif ".webp" in m and "_thumbnail" not in m and "_2x" not in cur:
                    base_best_file[base] = m

        res_urls = []
        for b in bases:
            f_name = base_best_file[b]
            if "_thumbnail" in f_name:
                f_name = f_name.replace("_thumbnail", "")
            res_urls.append(f"https://d28s5ztqvkii64.cloudfront.net/images/anime/{aid}/{f_name}")
            
        result_str = "\n".join(res_urls)
        aid_image_cache[aid] = result_str
        return result_str

    def crawl_tv_page(url, tag_label):
        animes = []
        try:
            raw_html = subprocess.check_output(headers_curl + [url], timeout=15).decode('utf-8', errors='ignore')
            if raw_html and len(raw_html) > 50000:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw_html, 'html.parser')
                anchors = soup.find_all('a', href=re.compile(r'/animes/\d+'))
                seen_local = set()
                for a in anchors:
                    aid_m = re.search(r'/animes/(\d+)', a.get('href', ''))
                    if not aid_m: continue
                    aid = aid_m.group(1)
                    if aid in seen_local: continue
                    
                    img = a.find('img')
                    title = img.get('alt') or img.get('title') or '' if img else a.get_text(strip=True)
                    title = re.sub(r'^\d+\s*', '', title).strip()
                    clean_t = normalize_title(title)
                    if clean_t and len(clean_t) > 1 and "排行榜" not in clean_t:
                        seen_local.add(aid)
                        img_url = get_anime_images(aid)
                        animes.append({
                            'id': aid,
                            'title': clean_t,
                            'category': tag_label,
                            'url': f"https://youranimes.tw/animes/{aid}",
                            'image_url': img_url
                        })
        except Exception as e:
            print(f"Fetch error for {url}: {e}")
        return animes

    # (1) 動畫化決定
    print("  -> 抓取 [動畫化決定] (bangumi/unknown)...")
    unknown_tv = crawl_tv_page("https://youranimes.tw/bangumi/unknown", "動畫化決定")
    for item in unknown_tv:
        clean_t = item['title']
        mk = get_match_key(clean_t)
        if mk not in tv_seen_keys:
            tv_seen_keys.add(mk)
            link_entry = [{"title": "YourAnimes 連結", "url": item['url']}]
            tv_rows.append({
                'title': clean_t, 'category': "動畫化決定",
                'total_seasons': '1', 'total_episodes': '0',
                'info_links': json.dumps(link_entry, ensure_ascii=False),
                'image_url': item.get('image_url', '')
            })

    # (2) 2026年7月(含)之後所有季度
    for scode in tv_seasons:
        y = scode[:4]
        m = int(scode[4:])
        tag_label = f"{y}年{m}月新番"
        url = f"https://youranimes.tw/bangumi/{scode}"
        print(f"  -> 抓取季番 [{tag_label}] ({url})...")
        items = crawl_tv_page(url, tag_label)
        for item in items:
            clean_t = item['title']
            mk = get_match_key(clean_t)
            if mk not in tv_seen_keys:
                tv_seen_keys.add(mk)
                link_entry = [{"title": "YourAnimes 連結", "url": item['url']}]
                tv_rows.append({
                    'title': clean_t, 'category': tag_label,
                    'total_seasons': '1', 'total_episodes': '0',
                    'info_links': json.dumps(link_entry, ensure_ascii=False),
                    'image_url': item.get('image_url', '')
                })
        time.sleep(0.02)

    # 寫入 line_manager/resources/tv_dramas.csv
    with open(res_tv_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in tv_rows:
            writer.writerow(r)
    print(f"[SUCCESS] 完成 TV 季番更新：{len(tv_rows)} 筆已儲存至 {res_tv_csv}")

    # ----------------------------------------------------
    # Part 2. 抓取 動畫電影 (日本動畫電影製作決定 + 2026年(含)之後)
    # ----------------------------------------------------
    print("\n[MOVIE] [2/2] 正在抓取 動畫電影 (日本動畫電影製作決定 & 2026年(含)之後)...")
    movie_years = [str(y) for y in range(2026, 2029)]
    movie_rows = []
    movie_seen_keys = set()

    def crawl_movie_edition(year, ed_type):
        tag_label = "日本動畫電影製作決定" if year == 'unknown' else f"{year}年{'日' if ed_type=='jp' else '台'}版動畫電影"
        url = f"https://youranimes.tw/anime-movie-premiered/{year}/{ed_type}"
        return crawl_tv_page(url, tag_label)

    # (1) 日本動畫電影製作決定
    print("  -> 抓取 [日本動畫電影製作決定] (unknown/jp)...")
    unknown_movies = crawl_movie_edition('unknown', 'jp')
    for item in unknown_movies:
        clean_t = item['title']
        mk = get_match_key(clean_t) + "_日本動畫電影製作決定"
        if mk not in movie_seen_keys:
            movie_seen_keys.add(mk)
            link_entry = [{"title": "YourAnimes 連結", "url": item['url']}]
            movie_rows.append({
                'title': clean_t, 'category': "日本動畫電影製作決定",
                'total_seasons': '1', 'total_episodes': '1',
                'info_links': json.dumps(link_entry, ensure_ascii=False),
                'image_url': item.get('image_url', '')
            })

    # (2) 2026年(含)之後日版與台版電影
    for myear in movie_years:
        for ed in ['jp', 'tw']:
            tag_label = f"{myear}年{'日' if ed=='jp' else '台'}版動畫電影"
            url = f"https://youranimes.tw/anime-movie-premiered/{myear}/{ed}"
            print(f"  -> 抓取電影 [{tag_label}]...")
            items = crawl_tv_page(url, tag_label)
            for item in items:
                clean_t = item['title']
                mk = get_match_key(clean_t) + "_" + tag_label
                if mk not in movie_seen_keys:
                    movie_seen_keys.add(mk)
                    link_entry = [{"title": "YourAnimes 連結", "url": item['url']}]
                    movie_rows.append({
                        'title': clean_t, 'category': tag_label,
                        'total_seasons': '1', 'total_episodes': '1',
                        'info_links': json.dumps(link_entry, ensure_ascii=False),
                        'image_url': item.get('image_url', '')
                    })
            time.sleep(0.02)

    # 寫入 line_manager/resources/movie_dramas.csv
    with open(res_movie_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in movie_rows:
            writer.writerow(r)
    print(f"[SUCCESS] 完成動畫電影更新：{len(movie_rows)} 筆已儲存至 {res_movie_csv}")

    # ----------------------------------------------------
    # Part 3. 資料庫 DB 同步 (Pure Diff Sync)
    # ----------------------------------------------------
    print("\n[SYNC] 正在執行 DB 資料庫同步與清單整合...")
    csv_map = {}

    def merge_csv_file(filepath):
        if not os.path.exists(filepath): return
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                t = normalize_title(r.get('title', ''))
                cat = r.get('category', '').strip()
                if not t: continue
                mk = get_match_key(t)
                key = (mk, cat)
                csv_map[key] = {
                    'title': t,
                    'category': cat,
                    'total_seasons': r.get('total_seasons', 1),
                    'total_episodes': r.get('total_episodes', 0),
                    'info_links': r.get('info_links', '[]'),
                    'image_url': r.get('image_url', '')
                }

    # 合併 resources 與 test CSV
    merge_csv_file(test_tv_csv)
    merge_csv_file(test_movie_csv)
    merge_csv_file(res_tv_csv)
    merge_csv_file(res_movie_csv)

    print(f"  -> 合併後不重複劇集總計: {len(csv_map)} 筆")

    # 取得或建立系統匯入者帳戶
    system_user, _ = User.objects.get_or_create(username="system_importer")
    LineProfile.objects.get_or_create(
        user=system_user,
        defaults={"line_user_id": "U_system_importer_dummy", "line_display_name": "系統管理員"}
    )

    db_dramas = list(Drama.objects.all())
    deleted_count = 0
    retained_count = 0
    db_existing_keys = set()

    for d in db_dramas:
        mk = get_match_key(d.title)
        key = (mk, d.category)
        if key in csv_map:
            db_existing_keys.add(key)
            retained_count += 1
            row = csv_map[key]
            if row.get('image_url') and d.image_url != row['image_url']:
                d.image_url = row['image_url']
                d.save()
        else:
            for progress in list(d.progresses.all()):
                progress.delete()
            DramaRecommendation.objects.filter(drama=d).delete()
            d.delete()
            deleted_count += 1

    created_count = 0
    for key, row in csv_map.items():
        if key not in db_existing_keys:
            Drama.objects.create(
                creator=system_user,
                title=row['title'],
                category=row['category'],
                total_seasons=int(row['total_seasons']) if str(row['total_seasons']).isdigit() else 1,
                total_episodes=int(row['total_episodes']) if str(row['total_episodes']).isdigit() else 0,
                info_links=row['info_links'],
                image_url=row.get('image_url', '')
            )
            created_count += 1

    final_db_count = Drama.objects.count()
    print(f"[SYNC SUCCESS] DB 自動同步完畢！保留: {retained_count} | 移除: {deleted_count} | 新增: {created_count} | 最終 DB 筆數: {final_db_count}")
    print(f"==================================================\n")


class Command(BaseCommand):
    help = "每日下午 4:00 (16:00) 自動啟動 TV 季番與動畫電影爬取更新排程"

    def add_arguments(self, parser):
        parser.add_argument('--now', action='store_true', help='立即觸發一次更新任務')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 正在啟動 CSI Server 自動排程服務 (start_scheduler)..."))
        
        if options['now']:
            self.stdout.write(self.style.WARNING("⚡ 偵測到 --now 旗標，立即執行一次劇集與電影更新任務..."))
            run_daily_drama_update()

        scheduler = BlockingScheduler(timezone="Asia/Taipei")

        # 每日 16:00 執行更新任務
        scheduler.add_job(
            run_daily_drama_update,
            trigger=CronTrigger(hour=16, minute=0),
            id="daily_drama_update_job",
            replace_existing=True
        )

        self.stdout.write(self.style.SUCCESS("✅ 排程服務已就緒！每日 16:00 (下午4點) 將自動更新 resources/*.csv 與 DB 資料庫。"))
        self.stdout.write(self.style.NOTICE("按 Ctrl+C 可停止排程服務。"))

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write(self.style.WARNING("🛑 排程服務已停止。"))
