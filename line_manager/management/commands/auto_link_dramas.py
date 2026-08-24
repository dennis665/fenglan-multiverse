import json
import os
import re
from django.core.management.base import BaseCommand
from line_manager.models import Drama


class Command(BaseCommand):
    help = "自動分析資料庫內所有動畫作品，關聯同一作品的第幾季、OVA、劇場版、總集篇"

    def clean_franchise_title(self, title):
        """提取動畫主系列名稱 (Core Franchise Name)"""
        if not title:
            return ""
        t = str(title).strip()

        # 1. 移除前導 '#' / '＃' 與開頭連線/空格符號
        t = re.sub(r"^[#＃\s]+", "", t).strip()

        # 2. 移除前綴：劇場版、電影版、動畫電影、OVA、OAD、特別篇、SP、【新番】、[新番]
        t = re.sub(
            r"^(劇場版|電影版|動畫電影|OVA|OAD|特別篇|SP|【新番】|\[新番\]|\s)+",
            "",
            t,
            flags=re.IGNORECASE,
        ).strip()

        # 3. 特殊熱門/知名 IP 保護對應
        if "Infinite Dendrogram" in title or "無盡連鎖" in title:
            return "Infinite Dendrogram -無盡連鎖-"
        if "尋找殭屍中" in title:
            return "尋找殭屍中"
        if "從零開始的異世界生活" in title:
            return "Re:從零開始的異世界生活"
        if "間諜家家酒" in title or "SPY×FAMILY" in title:
            return "SPY×FAMILY 間諜家家酒"
        if "名偵探柯南" in title:
            return "名偵探柯南"
        if "鬼滅之刃" in title:
            return "鬼滅之刃"
        if "進擊的巨人" in title:
            return "進擊的巨人"
        if "刀劍神域" in title:
            return "刀劍神域"
        if "無職轉生" in title:
            return "無職轉生 ～到了異世界就拿出真本事～"
        if "轉生成史萊姆" in title or "關於我轉生變成史萊姆這檔事" in title:
            return "關於我轉生變成史萊姆這檔事"
        if "五等分的新娘" in title:
            return "五等分的新娘"
        if "咒術迴戰" in title:
            return "咒術迴戰"
        if "鏈鋸人" in title:
            return "鏈鋸人"
        if "排球少年" in title:
            return "排球少年"
        if "我的英雄學院" in title:
            return "我的英雄學院"
        if "文豪Stray Dogs" in title or "文豪野犬" in title:
            return "文豪Stray Dogs"
        if "魔法禁書目錄" in title:
            return "魔法禁書目錄"
        if "科學超電磁砲" in title:
            return "科學超電磁砲"
        if "Overlord" in title or "不死者之王" in title:
            return "Overlord 不死者之王"
        if "賽馬娘" in title:
            return "賽馬娘 Pretty Derby"
        if "孤獨搖滾" in title:
            return "BOCCHI THE ROCK! 孤獨搖滾!"
        if "死神" in title or "BLEACH" in title:
            return "BLEACH 死神"
        if "Fate/" in title or "Fate／" in title:
            return "Fate 系列"
        if "蠟筆小新" in title:
            return "蠟筆小新"
        if "哆啦A夢" in title:
            return "哆啦A夢"
        if "海賊王" in title or "航海王" in title or "ONE PIECE" in title:
            return "航海王 ONE PIECE"
        if "火影忍者" in title or "BORUTO" in title:
            return "火影忍者 / BORUTO"
        if "龍珠" in title or "七龍珠" in title or "Dragon Ball" in title:
            return "七龍珠 Dragon Ball"
        if "機動戰士高達" in title or "機動戰士鋼彈" in title or "鋼彈" in title:
            return "機動戰士鋼彈 系列"
        if "銀魂" in title:
            return "銀魂"

        # 4. 移除季數、期數與章節尾綴
        patterns = [
            r"\s*第[0-90-9一二三四五六七八九十]+\s*[季期].*",
            r"\s*Season\s*[0-9]+.*",
            r"\s*S[0-9]+.*",
            r"\s*[0-9]+(?:st|nd|rd|th)\s*Season.*",
            r"\s*Part\s*[0-9]+.*",
            r"\s*The\s*Final\s*Season.*",
            r"\s*【?總集篇】?.*",
            r"\s*特别總集篇.*",
            r"\s*特別篇.*",
            r"\s*OVA.*",
            r"\s*OAD.*",
            r"\s*劇場版.*",
            r"\s*電影版.*",
        ]
        for pat in patterns:
            t = re.sub(pat, "", t, flags=re.IGNORECASE).strip()

        # 5. 清理包覆在最外層的書名號 〈〉 《》 
        if (t.startswith("〈") and "〉" in t) or (t.startswith("《") and "》" in t):
            t = re.sub(r"^[〈《]|[\s:：\-—–]*[〉》].*", "", t).strip()

        # 6. 分隔符號分割（注意：對冒號與連字號做切分，不對空格作切分，避免英文書名被斷開）
        split_match = re.split(r"[:：\-—–]+", t)
        if len(split_match) > 1 and len(split_match[0].strip()) >= 2:
            t = split_match[0].strip()

        # 7. 移除首尾殘留符號
        t = re.sub(r"^[#＃\s〈《『「【\[]+|[#＃\s〉》』」】\]]+$", "", t).strip()

        return t if t else title.strip()
        if "轉生成史萊姆" in title or "關於我轉生變成史萊姆這檔事" in title:
            return "關於我轉生變成史萊姆這檔事"
        if "五等分的新娘" in title:
            return "五等分的新娘"
        if "咒術迴戰" in title:
            return "咒術迴戰"
        if "鏈鋸人" in title:
            return "鏈鋸人"
        if "排球少年" in title:
            return "排球少年"
        if "我的英雄學院" in title:
            return "我的英雄學院"
        if "文豪Stray Dogs" in title or "文豪野犬" in title:
            return "文豪Stray Dogs"
        if "魔法禁書目錄" in title:
            return "魔法禁書目錄"
        if "科學超電磁砲" in title:
            return "科學超電磁砲"
        if "Overlord" in title or "不死者之王" in title:
            return "Overlord 不死者之王"
        if "賽馬娘" in title:
            return "賽馬娘 Pretty Derby"
        if "孤獨搖滾" in title:
            return "BOCCHI THE ROCK! 孤獨搖滾!"
        if "死神" in title or "BLEACH" in title:
            return "BLEACH 死神"
        if "Fate/" in title or "Fate／" in title:
            return "Fate 系列"
        if "蠟筆小新" in title:
            return "蠟筆小新"
        if "哆啦A夢" in title:
            return "哆啦A夢"
        if "海賊王" in title or "航海王" in title or "ONE PIECE" in title:
            return "航海王 ONE PIECE"
        if "火影忍者" in title or "BORUTO" in title:
            return "火影忍者 / BORUTO"
        if "龍珠" in title or "七龍珠" in title or "Dragon Ball" in title:
            return "七龍珠 Dragon Ball"
        if "機動戰士高達" in title or "機動戰士鋼彈" in title or "鋼彈" in title:
            return "機動戰士鋼彈 系列"
        if "銀魂" in title:
            return "銀魂"

        # 若非上述大作品，切割副標題
        split_match = re.split(r"[\s:：\-—–]+", t)
        if len(split_match) > 1 and len(split_match[0]) >= 2:
            return split_match[0].strip()

        return t if t else title.strip()

    def classify_media_type(self, title, category):
        """精準判定媒體類型：TV正篇、劇場版/電影、OVA/特別篇、總集篇"""
        title_upper = title.upper()

        if "總集篇" in title or "總集" in title or "RECAP" in title_upper:
            return "RECAP", "🎞️ 總集篇"
        elif (
            "劇場版" in title
            or "電影" in title
            or "MOVIE" in title_upper
            or "劇場版" in category
            or "電影" in category
        ):
            return "MOVIE", "🎬 劇場版 / 電影"
        elif (
            "OVA" in title_upper
            or "OAD" in title_upper
            or "特別篇" in title
            or "SPECIAL" in title_upper
            or "SP" in title_upper
        ):
            return "OVA", "📼 OVA / 特別篇"
        else:
            return "TV", "📺 季番 / 正篇"

    def extract_season_number(self, title):
        """提取季數 (Season Number)"""
        m = re.search(r"第\s*([0-9一二三四五六七八九十]+)\s*[季期]", title)
        if m:
            num_map = {
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "五": 5,
                "六": 6,
                "七": 7,
                "八": 8,
                "九": 9,
                "十": 10,
            }
            val = m.group(1)
            if val in num_map:
                return num_map[val]
            try:
                return int(val)
            except ValueError:
                pass

        m2 = re.search(r"Season\s*([0-9]+)", title, re.IGNORECASE)
        if m2:
            return int(m2.group(1))

        m3 = re.search(r"S([0-9]+)", title, re.IGNORECASE)
        if m3:
            return int(m3.group(1))

        return 1

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[START] 開始對資料庫中的所有動漫劇集進行關聯與整合分析..."))
        all_dramas = list(Drama.objects.all())

        franchise_groups = {}

        for d in all_dramas:
            franchise = self.clean_franchise_title(d.title)
            m_type_code, m_type_label = self.classify_media_type(d.title, d.category)
            season_num = self.extract_season_number(d.title)

            item_info = {
                "id": d.id,
                "title": d.title,
                "category": d.category,
                "total_seasons": d.total_seasons,
                "total_episodes": d.total_episodes,
                "media_type_code": m_type_code,
                "media_type_label": m_type_label,
                "season_num": season_num,
                "created_at": d.created_at.strftime("%Y-%m-%d") if d.created_at else "",
            }

            if franchise not in franchise_groups:
                franchise_groups[franchise] = {
                    "franchise_name": franchise,
                    "total_items": 0,
                    "items": [],
                    "tv_seasons": [],
                    "movies": [],
                    "ovas": [],
                    "recaps": [],
                }

            franchise_groups[franchise]["items"].append(item_info)
            franchise_groups[franchise]["total_items"] += 1

            if m_type_code == "TV":
                franchise_groups[franchise]["tv_seasons"].append(item_info)
            elif m_type_code == "MOVIE":
                franchise_groups[franchise]["movies"].append(item_info)
            elif m_type_code == "OVA":
                franchise_groups[franchise]["ovas"].append(item_info)
            elif m_type_code == "RECAP":
                franchise_groups[franchise]["recaps"].append(item_info)

        multi_item_franchises = {
            k: v for k, v in franchise_groups.items() if len(v["items"]) > 1
        }

        self.stdout.write(self.style.SUCCESS("\n[REPORT] 資料庫動漫作品關聯統計報告："))
        self.stdout.write(f"----------------------------------------")
        self.stdout.write(f"資料庫動漫總筆數: {len(all_dramas)} 筆")
        self.stdout.write(f"獨立作品/系列總數: {len(franchise_groups)} 個")
        self.stdout.write(
            f"包含跨季/劇場版/OVA/總集篇之關聯系列數: {len(multi_item_franchises)} 個"
        )
        self.stdout.write(f"----------------------------------------\n")

        # 匯出結果 JSON 檔
        output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "anime_franchise_relations.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(franchise_groups, f, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"[SUCCESS] 動漫關聯資料已成功生成並導出至:\n   {output_path}")
        )
