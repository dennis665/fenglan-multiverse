import re
import urllib.request
from datetime import datetime, date
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


def crawl_gnn_articles(target_date_str=None, crawl_all=False, limit=None):
    """
    爬取 GNN 新聞核心函式
    :param target_date_str: 指定日期字串 'YYYY-MM-DD' (預設為今天)
    :param crawl_all: 若為 True 則爬取首頁所有新聞 (不限當天)
    :param limit: 最多爬取筆數
    :return: dict(created=..., updated=..., total=...)
    """
    if not target_date_str:
        today = timezone.localdate()
        target_date_str = today.strftime("%Y-%m-%d")
    else:
        today = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8"
    }

    url = "https://gnn.gamer.com.tw/"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")
    boxes = soup.find_all("div", class_="GN-lbox2B")

    created_count = 0
    updated_count = 0
    skipped_count = 0
    scanned_count = 0

    for b in boxes:
        if limit and scanned_count >= limit:
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
            d_req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(d_req, timeout=8) as d_resp:
                d_soup = BeautifulSoup(d_resp.read().decode("utf-8", errors="ignore"), "html.parser")
                
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

        # 若非全量爬取且不是目標日期
        if not crawl_all:
            if article_date < today:
                # 列表通常按時間由新到舊排序，若已小於目標日期則可終止
                break
            elif article_date > today:
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
        "target_date": target_date_str,
    }


class Command(BaseCommand):
    help = "爬取巴哈姆特 GNN 新聞資訊 (支援爬取當天、指定日期或全量首頁)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="爬取 GNN 首頁目前所有報導 (約 90 筆)"
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="指定爬取日期 YYYY-MM-DD (預設為今天)"
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="限制最多爬取筆數"
        )

    def handle(self, *args, **options):
        crawl_all = options.get("all", False)
        target_date = options.get("date")
        limit = options.get("limit")

        self.stdout.write("==================================================")
        if crawl_all:
            self.stdout.write("[START] Crawling ALL news from GNN homepage...")
        else:
            d_str = target_date or timezone.localdate().strftime("%Y-%m-%d")
            self.stdout.write(f"[START] Crawling GNN news for date: {d_str}...")
        self.stdout.write("==================================================")

        res = crawl_gnn_articles(target_date_str=target_date, crawl_all=crawl_all, limit=limit)

        self.stdout.write("\n==================================================")
        self.stdout.write("[DONE] GNN News Crawl finished!")
        self.stdout.write(f"  * Scanned & Saved: {res['scanned']} articles")
        self.stdout.write(f"  * Newly Created:   {res['created']} articles")
        self.stdout.write(f"  * Updated Existing: {res['updated']} articles")
        self.stdout.write(f"  * Target Date:     {res['target_date']}")
        self.stdout.write(f"  * Total in DB:     {GNNNews.objects.count()} articles")
        self.stdout.write("==================================================")
