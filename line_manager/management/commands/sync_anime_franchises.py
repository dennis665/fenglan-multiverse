import collections
import os
import re
from django.core.management.base import BaseCommand
from line_manager.models import AnimeFranchise, Drama


class Command(BaseCommand):
    help = "把全量動漫資料自動與 AnimeFranchise 資料庫關聯表進行對應同步 (寫入 DB 供 Admin 後台設定)"

    def clean_franchise_title(self, title):
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
        title_upper = title.upper()
        if "魔法科高中" in title:
            return "魔法科高中的劣等生"
        if "魔法紀錄" in title or "魔法少女小圓" in title:
            return "魔法少女小圓 系列"
        if "魔法騎士" in title:
            return "魔法騎士雷阿斯"
        if "CENCOROLL" in title_upper:
            return "CENCOROLL"
        if "CHAOS;CHILD" in title_upper or "CHAOS;HEAD" in title_upper or "CHAOS CHILD" in title_upper:
            return "CHAOS;CHILD 混沌之子"
        if "CLEVATESS" in title_upper:
            return "Clevatess"
        if "BANG DREAM" in title_upper:
            return "BanG Dream！"
        if "LOVE LIVE" in title_upper or "LOVELIVE" in title_upper:
            return "Love Live! 系列"
        if "IDOLM@STER" in title_upper or "偶像大師" in title:
            return "THE IDOLM@STER 偶像大師 系列"
        if "光之美少女" in title or "PRETTY CURE" in title_upper or "PRECURE" in title_upper:
            return "光之美少女 系列"
        if "卡片戰鬥" in title or "VANGUARD" in title_upper:
            return "卡片戰鬥!! 先導者"
        if "閃電十一人" in title or "INAZUMA ELEVEN" in title_upper:
            return "閃電十一人"
        if "數碼寶貝" in title or "DIGIMON" in title_upper:
            return "數碼寶貝 系列"
        if "寶可夢" in title or "POKÉMON" in title_upper or "POKEMON" in title_upper or "神奇寶貝" in title:
            return "寶可夢 Pokémon"
        if "遊戲王" in title or "YU-GI-OH" in title_upper:
            return "遊戲王 系列"
        if "約會大作戰" in title or "DATE A LIVE" in title_upper:
            return "約會大作戰 DATE A LIVE"
        if "戰姬絕唱" in title or "SYMPHOGEAR" in title_upper:
            return "戰姬絕唱 SYMPHOGEAR"
        if "CODE GEASS" in title_upper or "反叛的魯路修" in title:
            return "Code Geass 反叛的魯路修"
        if "請問您今天要來點兔子嗎" in title:
            return "請問您今天要來點兔子嗎？"
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
            r"\s*第[0-90-9一二三四五六七八九十]+\s*[季期篇章].*",
            r"\s*Season\s*[0-9]+.*",
            r"\s*S[0-9]+.*",
            r"\s*[0-9]+(?:st|nd|rd|th)\s*Season.*",
            r"\s*Part\s*[0-9]+.*",
            r"\s*The\s*Final\s*Season.*",
            r"\s*Final\s*SEASON.*",
            r"\s*【?總集篇】?.*",
            r"\s*特别總集篇.*",
            r"\s*特別篇.*",
            r"\s*OVA.*",
            r"\s*OAD.*",
            r"\s*劇場版.*",
            r"\s*電影版.*",
            r"\s*第二章.*",
            r"\s*第三章.*",
            r"\s*第一章.*",
            r"\s*\(\s*\d{4}\s*\).*",
            r"\s+II.*",
            r"\s+III.*",
            r"\s+IV.*",
            r"\s+2nd.*",
            r"\s+3rd.*",
            r"\s+2\s*$",
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

    def classify_media_type(self, title, category):
        title_upper = title.upper()
        if "總集篇" in title or "總集" in title or "RECAP" in title_upper:
            return "RECAP"
        elif (
            "劇場版" in title
            or "電影" in title
            or "MOVIE" in title_upper
            or "劇場版" in category
            or "電影" in category
        ):
            return "MOVIE"
        elif (
            "OVA" in title_upper
            or "OAD" in title_upper
            or "特別篇" in title
            or "SPECIAL" in title_upper
            or "SP" in title_upper
        ):
            return "OVA"
        else:
            return "TV"

    def is_valid_prefix(self, cname):
        clean_c = re.sub(r"^\W+|\W+$", "", cname)
        if not clean_c:
            return False
        STOP_PREFIXES = {
            "RE", "NO", "GO", "SO", "MY", "IN", "ON", "TO", "DO", "HI", "HE",
            "ME", "WE", "BE", "THE", "NEW", "ONE", "ALL", "TOP"
        }
        if re.match(r"^[a-zA-Z0-9\s]+$", clean_c):
            if len(clean_c) < 3 or clean_c.upper() in STOP_PREFIXES:
                return False
        else:
            cjk_chars = re.findall(r"[\u4e00-\u9fff]", clean_c)
            if len(cjk_chars) < 2:
                return False
        return True

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[SYNC] 開始對資料庫全量劇集進行實體化關聯寫入 (雙階段極致歸類)..."))
        all_dramas = list(Drama.objects.all())

        # 第一階段：單項基礎清洗
        initial_map = collections.defaultdict(list)
        for d in all_dramas:
            fname = self.clean_franchise_title(d.title)
            mtype = self.classify_media_type(d.title, d.category)
            initial_map[fname].append((d, mtype))

        # 第二階段：字首前綴比對合併 (自動歸類至最簡短的作品名稱)
        sorted_names = sorted(initial_map.keys(), key=lambda n: len(n))
        delimiters = (
            " ", "：", ":", "-", "—", "–", "～", "~", "！", "!", "／", "/",
            "《", "〈", "【", "[", "『", "「"
        )

        final_target_map = {}
        canonical_names = []

        for name in sorted_names:
            matched_target = None
            for cname in canonical_names:
                if not self.is_valid_prefix(cname):
                    continue
                if name == cname:
                    matched_target = cname
                    break
                if name.startswith(cname):
                    rem = name[len(cname):]
                    if rem.startswith(delimiters) or not rem[0].isalnum():
                        matched_target = cname
                        break
            if matched_target:
                final_target_map[name] = matched_target
            else:
                final_target_map[name] = name
                canonical_names.append(name)

        # 第三階段：寫入資料庫與 Drama 實體關聯
        franchise_cache = {}
        created_franchises_count = 0
        updated_dramas_count = 0

        for orig_fname, d_list in initial_map.items():
            target_fname = final_target_map[orig_fname]

            if target_fname not in franchise_cache:
                af, created = AnimeFranchise.objects.get_or_create(name=target_fname)
                if created:
                    created_franchises_count += 1
                franchise_cache[target_fname] = af
            else:
                af = franchise_cache[target_fname]

            for d, m_type in d_list:
                if d.image_url and not af.cover_image_url:
                    af.cover_image_url = d.image_url
                    af.save()

                if d.franchise != af or d.media_type != m_type:
                    d.franchise = af
                    d.media_type = m_type
                    d.save()
                    updated_dramas_count += 1

        # 第四階段：清理空的舊系列
        from line_manager.admin import cleanup_empty_franchises
        cleaned_empty_count = cleanup_empty_franchises()

        self.stdout.write(
            self.style.SUCCESS(
                f"[SUCCESS] 全量歸類與同步完成！\n"
                f" - 當前總動漫系列數: {AnimeFranchise.objects.count()} 個 (新建立 {created_franchises_count} 個)\n"
                f" - 關聯更新劇集: {updated_dramas_count} 部\n"
                f" - 清理空系列: {cleaned_empty_count} 個"
            )
        )
