import re
import time
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from bs4 import BeautifulSoup
from line_manager.models import GNNNews

PLATFORM_MAP = {
    "platform-pc": "PC",
    "platform-tv": "TV掌機",
    "platform-mobile": "手機",
    "platform-acg": "動漫畫",
    "platform-arcade": "大型機台",
    "platform-web": "網頁",
    "platform-esport": "電競",
    "platform-event": "活動展覽",
    "platform-tech": "科技硬體",
    "platform-party": "綜合",
    "cross": "跨平台",
}


def fetch_url_with_retry(url, headers, max_retries=3, backoff=3.0, timeout=12):
    """
    安全發送 HTTP 請求：具備指數退避與防 429 Too Many Requests 重試機制
    """
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_sec = backoff * attempt
                print(f"  ⚠️ [429 頻率限制] 觸發巴哈姆特防爬保護，暫停 {wait_sec:.1f} 秒後自動重試 (第 {attempt}/{max_retries} 次)...")
                time.sleep(wait_sec)
                continue
            elif e.code in (500, 502, 503, 504):
                time.sleep(1.5)
                continue
            else:
                print(f"  ❌ 請求失敗 HTTP {e.code}: {url}")
                raise
        except Exception as e:
            if attempt == max_retries:
                print(f"  ❌ 連線錯誤: {e} ({url})")
                raise
            time.sleep(1.0)
    return None


def crawl_gnn_articles(target_date_str=None, crawl_all=False, limit=None, days=None, force_update=False):
    """
    爬取 GNN 新聞核心函式
    :param target_date_str: 指定單一日期字串 'YYYY-MM-DD'
    :param crawl_all: 若為 True 則全量爬取首頁 (約 90 筆)
    :param limit: 最多爬取筆數限制
    :param days: 爬取最近 X 天內的所有新聞 (如 days=3 抓近 3 天)
    :param force_update: 是否強制重新抓取已存在的新聞內頁 (預設為 False，自動避開重複資料以高速完成)
    :return: dict(scanned=..., created=..., updated=..., skipped=..., mode=...)
    """
    today = timezone.localdate()
    cutoff_date = None
    exact_date = None

    if days is not None and days > 0:
        cutoff_date = today - timedelta(days=days - 1)
        mode_desc = f"近 {days} 天新聞 ({cutoff_date} ~ {today})"
    elif target_date_str:
        exact_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        cutoff_date = exact_date
        mode_desc = f"指定日期 {target_date_str}"
    elif crawl_all:
        mode_desc = "首頁全量新聞"
    else:
        cutoff_date = today
        mode_desc = f"今日新聞 ({today})"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
        "Referer": "https://gnn.gamer.com.tw/",
    }

    created_count = 0
    updated_count = 0
    skipped_count = 0
    scanned_count = 0

    # 決定抓取列表之目標 URL
    # 巴哈姆特首頁包含近 5~6 天約 90 幾篇報導；若跨度超過 5 天則改查巴哈官方年月封存 (yy=YYYY&mm=MM)
    target_urls = []
    if days and days > 4:
        cur_y, cur_m = today.year, today.month
        end_y, end_m = cutoff_date.year, cutoff_date.month
        y, m = cur_y, cur_m
        while (y > end_y) or (y == end_y and m >= end_m):
            target_urls.append(f"https://gnn.gamer.com.tw/index.php?yy={y}&mm={m}")
            m -= 1
            if m < 1:
                m = 12
                y -= 1
    elif target_date_str:
        if exact_date.year == today.year and exact_date.month == today.month:
            target_urls.append("https://gnn.gamer.com.tw/")
        else:
            target_urls.append(f"https://gnn.gamer.com.tw/index.php?yy={exact_date.year}&mm={exact_date.month}")
    else:
        target_urls.append("https://gnn.gamer.com.tw/")

    stopped = False

    for url in target_urls:
        if stopped:
            break

        try:
            html = fetch_url_with_retry(url, headers=headers)
            if not html:
                continue
        except Exception as e:
            print(f"Error fetching GNN URL {url}: {e}")
            break

        soup = BeautifulSoup(html, "html.parser")
        boxes = soup.find_all("div", class_="GN-lbox2B")
        if not boxes:
            continue

        for b in boxes:
            if limit and scanned_count >= limit:
                stopped = True
                break

            h1 = b.find("h1", class_="GN-lbox2D")
            if not h1:
                continue

            a_link = h1.find("a")
            if not a_link:
                continue

            title = a_link.get_text(strip=True)
            href = a_link.get("href", "")
            m_sn = re.search(r"sn=(\d+)", href)
            if not m_sn:
                continue
            sn = m_sn.group(1)
            full_url = f"https://gnn.gamer.com.tw/detail.php?sn={sn}"

            # 避開重複資料機制 (若資料庫已有該 sn 且未強制更新，直接跳過內頁請求)
            existing_obj = GNNNews.objects.filter(sn=sn).first()
            if existing_obj and not force_update:
                article_date = existing_obj.crawl_date
                # 若已早於目標截止日，由於列表按時間降序排列，可提早終止
                if cutoff_date and not crawl_all:
                    if article_date < cutoff_date:
                        stopped = True
                        break
                    elif target_date_str and article_date != exact_date:
                        continue
                skipped_count += 1
                scanned_count += 1
                continue

            # 縮圖
            img = b.find("img")
            img_url = ""
            if img:
                srcset = img.get("srcset", "")
                if srcset:
                    m_img = re.findall(r"(https://[^\s,]+\.(?:jpg|png|jpeg|webp))", srcset, re.I)
                    img_url = m_img[-1] if m_img else ""
                if not img_url:
                    img_url = img.get("src", "")

            # 摘要
            desc_p = b.find("p", class_="GN-lbox2C")
            summary = ""
            if desc_p:
                summary = desc_p.get_text(strip=True)
                if summary.endswith("繼續閱讀"):
                    summary = summary[:-4].strip()

            # 分類標籤 (多項 Tag)
            tags = []
            plat_div = h1.find("div", class_=re.compile(r"platform-"))
            if plat_div:
                for c in plat_div.get("class", []):
                    if c in PLATFORM_MAP:
                        tags.append(PLATFORM_MAP[c])
                    elif c.startswith("platform-") and c != "platform-tag_list":
                        tags.append(c.replace("platform-", ""))

            m_bracket = re.match(r"^[【\[]([^】\]]+)[】\]]", title)
            if m_bracket:
                bracket_tag = m_bracket.group(1).strip()
                if bracket_tag and bracket_tag not in tags:
                    tags.append(bracket_tag)

            # 深入內頁獲取精準發布時間與內文 Hashtag
            published_at = None
            article_date = today

            try:
                # 請求內頁前進行微延遲 (0.35 秒)，體貼巴哈姆特伺服器並防範 429
                time.sleep(0.35)
                d_html = fetch_url_with_retry(full_url, headers=headers, max_retries=3, backoff=3.0, timeout=10)
                if d_html:
                    d_soup = BeautifulSoup(d_html, "html.parser")
                    
                    # 發布時間字串
                    date_s = d_soup.find(string=re.compile(r"202\d-\d{2}-\d{2}\s+\d{2}:\d{2}"))
                    if date_s:
                        m_time = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)", str(date_s))
                        if m_time:
                            d_part = m_time.group(1)
                            t_part = m_time.group(2)
                            if len(t_part.split(":")) == 2:
                                t_part += ":00"
                            dt_naive = datetime.strptime(f"{d_part} {t_part}", "%Y-%m-%d %H:%M:%S")
                            published_at = timezone.make_aware(dt_naive, timezone.get_current_timezone())
                            article_date = datetime.strptime(d_part, "%Y-%m-%d").date()

                    # 內文標籤 (Hashtag)
                    for ht_a in d_soup.find_all("a", href=re.compile(r"kw=.*o=tag")):
                        t_txt = ht_a.get_text(strip=True).lstrip("#")
                        if t_txt and t_txt not in tags:
                            tags.append(t_txt)
            except Exception:
                pass

            # 若非全量爬取且早於目標日期
            if not crawl_all and cutoff_date:
                if article_date < cutoff_date:
                    stopped = True
                    break
                elif target_date_str and article_date != exact_date:
                    continue

            scanned_count += 1

            obj, created = GNNNews.objects.update_or_create(
                sn=sn,
                defaults={
                    "title": title,
                    "link": full_url,
                    "tags": tags,
                    "thumbnail": img_url,
                    "summary": summary,
                    "published_at": published_at,
                    "crawl_date": article_date,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

    return {
        "scanned": scanned_count,
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "mode": mode_desc,
        "target_date": target_date_str or (str(cutoff_date) if cutoff_date else "ALL"),
    }


class Command(BaseCommand):
    help = "爬取巴哈姆特 GNN 新聞資訊 (支援爬取 X 天內、當天、指定日期或全量首頁)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="爬取最近 X 天內的所有新聞報導 (例如 --days 3 爬取近3天，自動避開重複)"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="爬取 GNN 首頁目前所有報導 (約 90 筆)"
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="指定爬取單一日期 YYYY-MM-DD"
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="限制最多爬取筆數"
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="強制重新爬取已存在之新聞內頁 (預設會避開重複以秒速完成)"
        )

    def handle(self, *args, **options):
        days = options.get("days")
        crawl_all = options.get("all", False)
        target_date = options.get("date")
        limit = options.get("limit")
        force_update = options.get("force_update", False)

        self.stdout.write("==================================================")
        if days:
            self.stdout.write(f"[START] 正在爬取最近 {days} 天內之 GNN 新聞報導 (避開重複)...")
        elif crawl_all:
            self.stdout.write("[START] 正在爬取 GNN 首頁目前所有新聞報導...")
        elif target_date:
            self.stdout.write(f"[START] 正在爬取 GNN 指定日期之新聞: {target_date}...")
        else:
            d_str = timezone.localdate().strftime("%Y-%m-%d")
            self.stdout.write(f"[START] 正在爬取 GNN 當天之新聞: {d_str}...")
        self.stdout.write("==================================================")

        res = crawl_gnn_articles(
            target_date_str=target_date,
            crawl_all=crawl_all,
            limit=limit,
            days=days,
            force_update=force_update
        )

        self.stdout.write("\n==================================================")
        self.stdout.write("[DONE] GNN 新聞爬蟲執行完畢！")
        self.stdout.write(f"  * 執行模式:       {res['mode']}")
        self.stdout.write(f"  * 掃描處理數:     {res['scanned']} 篇")
        self.stdout.write(f"  * 新增至資料庫:   {res['created']} 篇")
        self.stdout.write(f"  * 更新現有資料:   {res['updated']} 篇")
        self.stdout.write(f"  * 略過重複已存在: {res['skipped']} 篇 (避開重複)")
        self.stdout.write(f"  * 目前資料庫總數: {GNNNews.objects.count()} 篇")
        self.stdout.write("==================================================")

