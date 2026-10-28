import urllib.request
import urllib.parse
import ssl
import re
import time
import http.cookiejar
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bilinovel.com"
FALLBACK_BASE_URL = "https://tw.linovelib.com"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.bilinovel.com/",
    "Accept-Language": "zh-TW,zh-CN,zh;q=0.9,en;q=0.8",
}


def _create_ssl_context():
    ctx = ssl._create_unverified_context()
    return ctx


def _build_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=_create_ssl_context())
    )
    opener.addheaders = list(DEFAULT_HEADERS.items())
    return opener, cj


try:
    import zhconv
except ImportError:
    zhconv = None

_cached_opener = None
_cached_cookie_jar = None
_last_handshake_time = 0


def _get_authenticated_search_opener(force_refresh=False):
    """獲取具備搜尋防護交握之 Opener，快取基礎 JS/CSS Cookie"""
    global _cached_opener, _cached_cookie_jar, _last_handshake_time
    now = time.time()
    if not force_refresh and _cached_opener is not None and (now - _last_handshake_time) < 1800:
        return _cached_opener

    opener, cj = _build_opener()
    try:
        # Step 1: js guard
        r1 = opener.open(f"{BASE_URL}/search.html?search_guard=js", timeout=8)
        body1 = r1.read().decode("utf-8", errors="ignore")
        m = re.search(r"jieqiSearchJs=([^;\'\"]+)", body1)
        if m:
            val = m.group(1)
            cj.set_cookie(http.cookiejar.Cookie(
                version=0, name="jieqiSearchJs", value=val, port=None, port_specified=False,
                domain=".bilinovel.com", domain_specified=True, domain_initial_dot=True,
                path="/", path_specified=True, secure=True, expires=None, discard=True,
                comment=None, comment_url=None, rest={"HttpOnly": None}, rfc2109=False
            ))

        # Step 2: css guard
        try:
            opener.open(f"{BASE_URL}/search.html?search_guard=css", timeout=6)
        except Exception:
            pass

        _cached_opener = opener
        _cached_cookie_jar = cj
        _last_handshake_time = now
        return opener
    except Exception as e:
        logger.warning(f"[LINOVEL_CRAWLER] Handshake warning: {e}")
        return opener


def _redeem_search_ticket(opener):
    """每次搜尋前獲取單次有效的 redeem ticket"""
    try:
        ts = int(time.time() * 1000)
        opener.open(f"{BASE_URL}/search.html?search_guard=redeem&r={ts}", timeout=6)
    except Exception as e:
        logger.warning(f"[LINOVEL_CRAWLER] Redeem ticket warning: {e}")


def search_novels(keyword: str):
    """
    搜尋輕小說。
    支援繁體、簡體中文自動互轉搜尋，或直接輸入小說 ID / 網址。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    # 1. 如果輸入為純數字或小說網址，直接檢索該作品
    id_match = re.search(r'(?:/novel/)?(\d+)(?:\.html|/catalog)?', keyword)
    if id_match and (keyword.isdigit() or "/novel/" in keyword):
        novel_id = id_match.group(1)
        details = fetch_novel_details(novel_id)
        if details:
            return [{
                "novel_id": details["novel_id"],
                "title": details["title"],
                "author": details.get("author", ""),
                "cover_url": details.get("cover_url", ""),
                "description": details.get("description", ""),
                "category": details.get("category", ""),
                "status": details.get("status", ""),
                "source_url": details.get("source_url", f"{BASE_URL}/novel/{novel_id}.html"),
                "total_chapters": sum(len(v.get("chapters", [])) for v in details.get("volumes", [])),
            }]
        return []

    # 2. 建立繁簡候選搜尋字詞清單 (如: "無職轉生" -> 自動包含 "无职转生")
    candidates = [keyword]
    try:
        simp = zhconv.convert(keyword, "zh-cn")
        if simp != keyword and simp not in candidates:
            candidates.append(simp)
        trad = zhconv.convert(keyword, "zh-tw")
        if trad != keyword and trad not in candidates:
            candidates.append(trad)
    except Exception:
        pass

    opener = _get_authenticated_search_opener()

    for attempt in range(2):
        for search_term in candidates:
            try:
                # 每次搜尋必須先取得單次有效 redeem ticket
                _redeem_search_ticket(opener)

                encoded_kw = urllib.parse.quote(search_term)
                search_url = f"{BASE_URL}/search.html?searchkey={encoded_kw}"
                resp = opener.open(search_url, timeout=10)
                html = resp.read().decode("utf-8", errors="ignore")

                # 若遇到 guard 跳轉，強制刷新基礎 handshake
                if "search_guard=js" in html or len(html) < 200:
                    opener = _get_authenticated_search_opener(force_refresh=True)
                    continue

                soup = BeautifulSoup(html, "html.parser")
                results = []

                # 正確擷取小說卡片元素：a.book-layout 或 li.book-li
                cards = soup.find_all("a", class_="book-layout")
                if not cards:
                    cards = soup.find_all("li", class_="book-li") or soup.find_all("div", class_="book-cell")

                for card in cards:
                    if card.name == "a":
                        a_link = card
                    else:
                        a_link = card.find_parent("a", class_="book-layout") or card.find("a", href=re.compile(r"/novel/\d+"))

                    if not a_link:
                        continue

                    href = a_link.get("href", "")
                    id_m = re.search(r"/novel/(\d+)", href)
                    if not id_m:
                        continue
                    novel_id = id_m.group(1)

                    # 標題
                    title_el = a_link.find(["h4", "h3", "div"], class_=re.compile(r"title|book-title|book-name")) or a_link.find("h4")
                    raw_title = title_el.get_text(strip=True) if title_el else a_link.get("title", "")

                    # 封面
                    img_el = a_link.find("img")
                    cover_url = ""
                    if img_el:
                        cover_url = img_el.get("data-src") or img_el.get("src") or ""
                        if cover_url.startswith("//"):
                            cover_url = "https:" + cover_url
                        elif cover_url.startswith("/"):
                            cover_url = BASE_URL + cover_url

                    # 作者
                    author = ""
                    author_el = a_link.find(class_=re.compile(r"author|book-author"))
                    if author_el:
                        author = author_el.get_text(strip=True)

                    # 簡介
                    intro_el = a_link.find("p", class_=re.compile(r"intro|desc|book-desc|book-intro"))
                    description = intro_el.get_text(strip=True) if intro_el else ""

                    # 類別/狀態
                    category = ""
                    status = ""
                    tag_els = a_link.find_all(["em", "span", "div"], class_=re.compile(r"tag|status|badge"))
                    for t in tag_els:
                        t_text = t.get_text(strip=True)
                        if any(kw in t_text for kw in ["連載", "完結", "连载", "完结"]):
                            status = t_text
                        elif not category and t_text:
                            category = t_text

                    # 繁體化轉換展示
                    try:
                        title = zhconv.convert(raw_title, "zh-tw")
                        author = zhconv.convert(author, "zh-tw")
                        description = zhconv.convert(description, "zh-tw")
                        category = zhconv.convert(category, "zh-tw")
                        status = zhconv.convert(status, "zh-tw")
                    except Exception:
                        title = raw_title

                    if not any(r["novel_id"] == novel_id for r in results):
                        results.append({
                            "novel_id": novel_id,
                            "title": title,
                            "author": author,
                            "cover_url": cover_url,
                            "description": description,
                            "category": category,
                            "status": status,
                            "source_url": f"{FALLBACK_BASE_URL}/novel/{novel_id}.html",
                        })

                if results:
                    return results

            except Exception as e:
                logger.warning(f"[LINOVEL_CRAWLER] Search query '{search_term}' error: {e}")

        # 若第一次迴圈未搜到任何結果，強制重整 handshake 重試
        opener = _get_authenticated_search_opener(force_refresh=True)

    return []



def fetch_novel_details(novel_id: str):
    """
    獲取小說完整詳情與目錄章節結構。
    """
    novel_id = str(novel_id).strip()
    catalog_url = f"{BASE_URL}/novel/{novel_id}/catalog"
    info_url = f"{BASE_URL}/novel/{novel_id}.html"

    opener, _ = _build_opener()

    try:
        # 1. 抓取目錄頁
        req = urllib.request.Request(catalog_url)
        resp = opener.open(req, timeout=12)
        html = resp.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        # 抓取小說基本資訊
        title = ""
        title_el = soup.find(["h1", "h2", "h3"], class_=re.compile(r"title|book-title|catalog-title"))
        if title_el:
            title = title_el.get_text(strip=True)

        author = ""
        author_el = soup.find(class_=re.compile(r"author"))
        if author_el:
            author = author_el.get_text(strip=True)

        cover_url = ""
        cover_el = soup.find("img", class_=re.compile(r"cover|book-cover"))
        if cover_el:
            cover_url = cover_el.get("data-src") or cover_el.get("src") or ""
            if cover_url.startswith("//"):
                cover_url = "https:" + cover_url
            elif cover_url.startswith("/"):
                cover_url = BASE_URL + cover_url

        # 若目錄頁資訊不足，再抓取 info_url
        description = ""
        category = ""
        status = ""
        if not title or not cover_url:
            try:
                info_req = urllib.request.Request(info_url)
                info_resp = opener.open(info_req, timeout=10)
                info_html = info_resp.read().decode("utf-8", errors="ignore")
                info_soup = BeautifulSoup(info_html, "html.parser")
                if not title:
                    t = info_soup.find(["h1", "h2"], class_=re.compile(r"book-title|title"))
                    if t:
                        title = t.get_text(strip=True)
                if not author:
                    a = info_soup.find(class_=re.compile(r"author"))
                    if a:
                        author = a.get_text(strip=True)
                if not cover_url:
                    c = info_soup.find("img", class_=re.compile(r"cover|book-cover"))
                    if c:
                        cover_url = c.get("data-src") or c.get("src") or ""
                desc_el = info_soup.find(class_=re.compile(r"intro|description|book-intro"))
                if desc_el:
                    description = desc_el.get_text(strip=True)
                cat_el = info_soup.find(class_=re.compile(r"category|tag"))
                if cat_el:
                    category = cat_el.get_text(strip=True)
            except Exception as e:
                logger.warning(f"[LINOVEL_CRAWLER] Could not fetch extra info for novel {novel_id}: {e}")

        # 2. 解析分卷與目錄章節
        volumes = []
        vol_blocks = soup.find_all("div", class_="catalog-volume")
        order_counter = 1

        if vol_blocks:
            for vol_el in vol_blocks:
                vol_title_el = vol_el.find(["h3", "h4", "div", "dt"], class_=re.compile(r"volume|title")) or vol_el.find(["h3", "h4"])
                vol_title = vol_title_el.get_text(strip=True) if vol_title_el else f"分卷 {len(volumes) + 1}"

                chapters = []
                for li in vol_el.find_all("li"):
                    a = li.find("a")
                    if not a:
                        continue
                    ch_href = a.get("href", "")
                    ch_id_m = re.search(r"/novel/\d+/(\d+)\.html", ch_href)
                    if not ch_id_m:
                        continue
                    ch_id = ch_id_m.group(1)
                    ch_title = a.get_text(strip=True)

                    chapters.append({
                        "chapter_id": ch_id,
                        "title": ch_title,
                        "order": order_counter,
                        "url": f"{BASE_URL}{ch_href}" if ch_href.startswith("/") else ch_href,
                    })
                    order_counter += 1

                if chapters:
                    volumes.append({
                        "volume_title": vol_title,
                        "chapters": chapters,
                    })
        else:
            # 備用：若無 catalog-volume 結構，抓取所有符合 /novel/{novel_id}/(\d+).html 的連結
            flat_chapters = []
            for a in soup.find_all("a", href=re.compile(rf"/novel/{novel_id}/(\d+)\.html")):
                ch_href = a.get("href", "")
                ch_id_m = re.search(r"/novel/\d+/(\d+)\.html", ch_href)
                if ch_id_m:
                    ch_id = ch_id_m.group(1)
                    ch_title = a.get_text(strip=True)
                    if not any(c["chapter_id"] == ch_id for c in flat_chapters):
                        flat_chapters.append({
                            "chapter_id": ch_id,
                            "title": ch_title,
                            "order": order_counter,
                            "url": f"{BASE_URL}{ch_href}" if ch_href.startswith("/") else ch_href,
                        })
                        order_counter += 1
            if flat_chapters:
                volumes.append({
                    "volume_title": "章節目錄",
                    "chapters": flat_chapters,
                })

        return {
            "novel_id": novel_id,
            "title": title or f"輕小說 #{novel_id}",
            "author": author,
            "cover_url": cover_url,
            "description": description,
            "category": category,
            "status": status,
            "source_url": f"{FALLBACK_BASE_URL}/novel/{novel_id}.html",
            "volumes": volumes,
        }

    except Exception as e:
        logger.error(f"[LINOVEL_CRAWLER] Fetch novel {novel_id} details error: {e}", exc_info=True)
        return None


def _clean_chapter_text(text: str) -> str:
    """清理章節段落中的站方防盜、偽裝報錯或水印提示，並轉換為繁體中文"""
    if not text:
        return ""
    patterns = [
        r"[\(（]\s*內容?加[載载]失[敗败]！?[請请][刷重][新載载]或更[換换][瀏浏]覽器\s*[\)）]",
        r"【[手機机]版頁面由於[相容兼容]性問題暫不支持[電腦电脑]端閱讀.*?】",
        r"【[手機机]版頁面由于[相容兼容]性问题暂不支持[電腦电脑]端阅读.*?】",
        r"[\(（]\s*[繼續继][下一页頁].*?[\)）]",
        r"[\(（]\s*本章未完.*?[\)）]",
        r"最新最全的.*?[輕轻]小說.*",
        r"https?://(?:www\.)?(?:bilinovel|linovelib)\.com[^\s]*",
        r"(?:bilinovel|linovelib)\.com",
    ]
    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    if cleaned:
        try:
            cleaned = zhconv.convert(cleaned, "zh-tw")
        except Exception:
            pass
    return cleaned


def _is_truncated_content(elements) -> bool:
    """檢查內容是否含有站方防盜截斷、假報錯或嚴重腰斬特徵"""
    if not elements:
        return True
    
    text_elements = [e["content"] for e in elements if isinstance(e, dict) and e.get("type") == "text"]
    if not text_elements:
        return True

    # 檢查是否含有防盜或偽裝報錯水印
    watermark_keywords = [
        "加載失敗", "加载失败", "更換瀏覽器", "更换浏览器",
        "相容性問題", "兼容性问题", "暫不支持電腦端", "暂不支持电脑端",
        "請使用手機閱讀", "请使用手机阅读"
    ]
    for t in text_elements:
        if any(w in t for w in watermark_keywords):
            return True

    # 若文字段落數偏少（少於 35 段）且結尾以省略號、破折號或逗號異常中止
    if len(text_elements) < 35:
        last_t = text_elements[-1].strip()
        if last_t.endswith("……") or last_t.endswith("…") or last_t.endswith("——") or last_t.endswith("，") or "肉體" in last_t or "肉体" in last_t:
            return True

    return False


def _fetch_from_backup_mirror(novel_id: str, chapter_id: str, chapter_title: str = ""):
    """
    備用乾淨鏡像源抓取器。
    當主站遭遇伺服器端故意腰斬（如無職轉生第15卷日記後篇等）或頻繁請求 429 阻擋時，
    從備用乾淨鏡像提取完整無缺正文。
    """
    novel_id = str(novel_id).strip()
    chapter_id = str(chapter_id).strip()
    ctx = _create_ssl_context()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "http://www.bibixiaoshuo.com/",
    }

    # 針對《無職轉生》(2013) 的精準映射與通用回退
    if novel_id == "2013":
        candidate_urls = []
        if chapter_id.isdigit():
            cid_int = int(chapter_id)
            # 第 15 卷偏移映射：72236 -> 1064, 72237 -> 1065, ...
            if 72236 <= cid_int <= 72260:
                bibi_cid = cid_int - 71172
                candidate_urls.append(f"http://www.bibixiaoshuo.com/wuzhizhuansheng/{bibi_cid}.html")

        # 遍歷抓取備用鏡像
        for cur_url in candidate_urls:
            try:
                req = urllib.request.Request(cur_url, headers=headers)
                resp = urllib.request.urlopen(req, context=ctx, timeout=8)
                html = resp.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                nr1 = soup.find("div", id="nr1") or soup.find("div", class_="content")
                if nr1:
                    raw_text = nr1.get_text(separator="\n")
                    paras = [p.strip() for p in raw_text.splitlines() if p.strip()]
                    if len(paras) >= 15:
                        backup_elements = []
                        for p in paras:
                            # 清理水印並繁體化
                            cleaned = _clean_chapter_text(p)
                            if cleaned:
                                backup_elements.append({"type": "text", "content": cleaned})
                        if len(backup_elements) >= 15:
                            return backup_elements
            except Exception as e:
                logger.warning(f"[LINOVEL_CRAWLER] Backup mirror fetch error for {cur_url}: {e}")
                continue

    return []


def fetch_chapter_content(novel_id: str, chapter_id: str):
    """
    抓取章節內文與插圖。
    支援自動拼接多頁子章節（例如 73621.html, 73621_2.html）。
    自動清理防盜防爬水印及偽裝報錯，並具備智慧腰斬檢測與備用鏡像無損補全機制。
    """
    novel_id = str(novel_id).strip()
    chapter_id = str(chapter_id).strip()

    opener, _ = _build_opener()

    # 優先嘗試繁體站 tw.linovelib.com，若失敗則 fallback 到 bilinovel 與 linovelib
    candidate_domains = [
        FALLBACK_BASE_URL,      # https://tw.linovelib.com
        BASE_URL,               # https://www.bilinovel.com
        "https://www.linovelib.com",
    ]

    best_result = None

    for domain in candidate_domains:
        current_page_url = f"{domain}/novel/{novel_id}/{chapter_id}.html"
        all_elements = []  # [{"type": "text"|"image", "content": ...}]
        visited_urls = set()
        chapter_title = ""
        next_chapter_id = None
        prev_chapter_id = None
        has_images = False
        page_num = 1
        max_pages = 20  # 防止死循環

        try:
            while current_page_url and page_num <= max_pages:
                if current_page_url in visited_urls:
                    break
                visited_urls.add(current_page_url)

                req = urllib.request.Request(current_page_url)
                resp = opener.open(req, timeout=12)
                html = resp.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")

                # 第一頁時抓取章節標題
                if page_num == 1:
                    title_el = soup.find("h1", id="atitle") or soup.find(["h1", "h2"], class_=re.compile(r"title|chapter-title"))
                    if title_el:
                        raw_ch_title = title_el.get_text(strip=True)
                        try:
                            chapter_title = zhconv.convert(raw_ch_title, "zh-tw")
                        except Exception:
                            chapter_title = raw_ch_title

                # 解析 ReadParams 取得上一章/下一頁/下一章
                read_params_raw = re.search(r"var\s+ReadParams\s*=\s*\{([^}]+)\}", html)
                url_next = None
                url_previous = None
                if read_params_raw:
                    params_str = read_params_raw.group(1)
                    m_next = re.search(r"url_next\s*:\s*[\'\"]([^\'\"]+)[\'\"]", params_str)
                    m_prev = re.search(r"url_previous\s*:\s*[\'\"]([^\'\"]+)[\'\"]", params_str)
                    if m_next:
                        url_next = m_next.group(1)
                    if m_prev:
                        url_previous = m_prev.group(1)

                # 記錄上一章 (僅在第一頁記錄)
                if page_num == 1 and url_previous:
                    prev_m = re.search(r"/novel/\d+/(\d+)(?:_\d+)?\.html", url_previous)
                    if prev_m:
                        prev_chapter_id = prev_m.group(1)

                # 解析 acontent 內容
                content_div = soup.find("div", id="acontent")
                if content_div:
                    # 先清除 script, style, center (水印公告常放於 center), ins 等垃圾元素
                    for unwanted in content_div.find_all(["script", "style", "center", "ins"]):
                        unwanted.decompose()
                    for cgo in content_div.find_all("div", class_="cgo"):
                        cgo.decompose()

                    # 遍歷段落和圖片
                    for child in content_div.children:
                        if not getattr(child, "name", None):
                            continue

                        # 檢查圖片
                        imgs = child.find_all("img") if child.name != "img" else [child]
                        if imgs:
                            for img in imgs:
                                img_src = img.get("data-src") or img.get("src") or ""
                                if "loading" in img_src or not img_src:
                                    continue
                                if img_src.startswith("//"):
                                    img_src = "https:" + img_src
                                elif img_src.startswith("/"):
                                    img_src = domain + img_src

                                all_elements.append({
                                    "type": "image",
                                    "content": img_src,
                                    "original_url": img_src,
                                })
                                has_images = True
                            continue

                        # 段落文字
                        raw_text = child.get_text()
                        cleaned_text = _clean_chapter_text(raw_text)
                        if cleaned_text:
                            all_elements.append({
                                "type": "text",
                                "content": cleaned_text,
                            })

                # 判斷是否有下一分頁（同章節子頁）
                if url_next:
                    subpage_pattern = rf"/novel/{novel_id}/{chapter_id}_(\d+)\.html"
                    if re.search(subpage_pattern, url_next):
                        # 下一頁仍是當前章節的子分頁
                        current_page_url = f"{domain}{url_next}" if url_next.startswith("/") else url_next
                        page_num += 1
                        time.sleep(0.2)  # 溫和延遲，降低 429 機率
                        continue
                    else:
                        # 已經不是當前章節的子分頁，代表這是下一章
                        next_m = re.search(r"/novel/\d+/(\d+)(?:_\d+)?\.html", url_next)
                        if next_m:
                            next_chapter_id = next_m.group(1)
                        break
                else:
                    break

            # 智慧腰斬檢驗與無縫備用鏡像補全
            if _is_truncated_content(all_elements):
                logger.info(f"[LINOVEL_CRAWLER] Chapter {chapter_id} detected as truncated ({len(all_elements)} elements). Fetching backup mirror...")
                backup_text_elements = _fetch_from_backup_mirror(novel_id, chapter_id, chapter_title)
                if backup_text_elements and len(backup_text_elements) > len(all_elements):
                    # 保留主站的所有原版插圖
                    saved_images = [e for e in all_elements if e.get("type") == "image"]
                    all_elements = saved_images + backup_text_elements
                    if saved_images:
                        has_images = True
                    logger.info(f"[LINOVEL_CRAWLER] Chapter {chapter_id} seamlessly repaired with backup mirror! New count: {len(all_elements)}")

            # 評估當前 domain 抓取品質
            if all_elements and not _is_truncated_content(all_elements):
                result = {
                    "novel_id": novel_id,
                    "chapter_id": chapter_id,
                    "title": chapter_title or f"第 {chapter_id} 章",
                    "elements": all_elements,
                    "has_images": has_images,
                    "prev_chapter_id": prev_chapter_id,
                    "next_chapter_id": next_chapter_id,
                    "total_paragraphs": len(all_elements),
                }
                return result
            elif all_elements:
                result = {
                    "novel_id": novel_id,
                    "chapter_id": chapter_id,
                    "title": chapter_title or f"第 {chapter_id} 章",
                    "elements": all_elements,
                    "has_images": has_images,
                    "prev_chapter_id": prev_chapter_id,
                    "next_chapter_id": next_chapter_id,
                    "total_paragraphs": len(all_elements),
                }
                if best_result is None or len(all_elements) > len(best_result["elements"]):
                    best_result = result

        except Exception as e:
            logger.warning(f"[LINOVEL_CRAWLER] Domain {domain} failed for chapter {chapter_id}: {e}")
            continue

    # 若所有主站皆失敗或依然腰斬，啟動終極備用鏡像兜底
    if not best_result or _is_truncated_content(best_result.get("elements", [])):
        fallback_elements = _fetch_from_backup_mirror(novel_id, chapter_id, "")
        if fallback_elements:
            saved_images = [e for e in (best_result.get("elements", []) if best_result else []) if e.get("type") == "image"]
            merged = saved_images + fallback_elements
            return {
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "title": (best_result.get("title") if best_result else "") or f"第 {chapter_id} 章",
                "elements": merged,
                "has_images": bool(saved_images),
                "prev_chapter_id": best_result.get("prev_chapter_id") if best_result else None,
                "next_chapter_id": best_result.get("next_chapter_id") if best_result else None,
                "total_paragraphs": len(merged),
            }

    if best_result:
        return best_result

    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "title": f"第 {chapter_id} 章",
        "elements": [],
        "has_images": False,
        "prev_chapter_id": None,
        "next_chapter_id": None,
        "total_paragraphs": 0,
    }

