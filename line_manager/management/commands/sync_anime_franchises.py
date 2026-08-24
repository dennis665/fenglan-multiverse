import os
import re
from django.core.management.base import BaseCommand
from line_manager.models import AnimeFranchise, Drama


class Command(BaseCommand):
    help = "把全量動漫資料自動與 AnimeFranchise 資料庫關聯表進行對應同步 (寫入 DB 供 Admin 後台設定)"

    def clean_franchise_title(self, title):
        if not title:
            return ""
        t = title.strip()
        t = re.sub(
            r"^(劇場版|電影版|動畫電影|OVA|OAD|特別篇|SP|【新番】|\[新番\]|\s)+",
            "",
            t,
            flags=re.IGNORECASE,
        ).strip()

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

        split_match = re.split(r"[\s:：\-—–]+", t)
        if len(split_match) > 1 and len(split_match[0]) >= 2:
            return split_match[0].strip()

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

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[SYNC] 開始對資料庫全量劇集進行實體化關聯寫入..."))
        all_dramas = list(Drama.objects.all())

        franchise_cache = {}
        created_franchises_count = 0
        updated_dramas_count = 0

        for d in all_dramas:
            f_name = self.clean_franchise_title(d.title)
            m_type = self.classify_media_type(d.title, d.category)

            if f_name not in franchise_cache:
                af, created = AnimeFranchise.objects.get_or_create(name=f_name)
                if created:
                    created_franchises_count += 1
                franchise_cache[f_name] = af
            else:
                af = franchise_cache[f_name]

            # 檢查並關聯 cover_image_url
            if d.image_url and not af.cover_image_url:
                af.cover_image_url = d.image_url
                af.save()

            if d.franchise != af or d.media_type != m_type:
                d.franchise = af
                d.media_type = m_type
                d.save()
                updated_dramas_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"[SUCCESS] 同步完成！\n"
                f" - 新增/對應動漫系列: {AnimeFranchise.objects.count()} 個 (新建立 {created_franchises_count} 個)\n"
                f" - 關聯更新劇集: {updated_dramas_count} 部"
            )
        )
