import io
import json
import re
import ssl
import urllib.request
import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction
from line_manager.models import FDANutrition


class Command(BaseCommand):
    help = "從衛生福利部 FDA 台灣食品營養成分資料庫爬取與更新 2500+ 食品成分"

    def handle(self, *args, **options):
        self.stdout.write("開始從衛生福利部 FDA 下載食品營養成分資料庫 Excel...")

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # 優先從主頁動態尋找最新 Excel 下載檔案 ID
        main_url = "https://consumer.fda.gov.tw/Food/TFND.aspx?nodeID=178"
        file_url = None

        try:
            req = urllib.request.Request(main_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

                # 尋找包含 EXCEL 的試算表檔案連結
                matches = re.findall(r'href=["\']([^"\']*GetFile\.ashx[^"\']+)["\']', html)
                for m in matches:
                    m_clean = m.replace("&amp;", "&")
                    if "EXCEL" in m_clean or "excel" in m_clean or "4862259227103213368" in m_clean:
                        if not m_clean.startswith("http"):
                            if m_clean.startswith("//"):
                                file_url = "https:" + m_clean
                            elif m_clean.startswith("/"):
                                file_url = "https://consumer.fda.gov.tw" + m_clean
                            else:
                                file_url = "https://consumer.fda.gov.tw/" + m_clean
                        else:
                            file_url = m_clean
                        break
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"動態解析主頁失敗: {e}，將使用預設檔案庫 URL"))

        if not file_url:
            file_url = "https://consumer.fda.gov.tw/uc/GetFile.ashx?type=ServerFile&id=4862259227103213368"

        self.stdout.write(f"正在下載檔案: {file_url}")

        req_file = urllib.request.Request(file_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req_file, context=ctx, timeout=60) as resp:
            excel_bytes = resp.read()

        self.stdout.write(f"Excel 下載完成 (共 {len(excel_bytes)} 位元組)，開始解析試算表...")

        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
        sheet = wb.active

        headers = [str(cell.value).strip() if cell.value is not None else "" for cell in sheet[2]]
        
        # 尋找關鍵欄位 Index
        def find_idx(keywords):
            for idx, h in enumerate(headers):
                for kw in keywords:
                    if kw in h:
                        return idx
            return -1

        code_idx = find_idx(["整合編號", "編號"])
        cat_idx = find_idx(["分類"])
        name_idx = find_idx(["樣品名稱", "名稱"])
        common_idx = find_idx(["俗名"])
        cal_idx = find_idx(["熱量(kcal)", "熱量"])
        protein_idx = find_idx(["粗蛋白(g)", "蛋白質(g)"])
        fat_idx = find_idx(["粗脂肪(g)", "脂肪(g)"])
        carbs_idx = find_idx(["總碳水化合物(g)", "碳水化合物(g)"])
        fiber_idx = find_idx(["膳食纖維(g)"])
        sodium_idx = find_idx(["鈉(mg)"])
        sugar_idx = find_idx(["糖(g)", "總糖(g)"])

        created_count = 0
        updated_count = 0

        def parse_float(val):
            if val is None:
                return 0.0
            try:
                return float(val)
            except Exception:
                return 0.0

        records = []
        for row_idx in range(3, sheet.max_row + 1):
            row_vals = [cell.value for cell in sheet[row_idx]]
            if not row_vals or not any(row_vals):
                continue

            code = str(row_vals[code_idx]).strip() if code_idx != -1 and row_vals[code_idx] else f"FOOD_{row_idx}"
            category = str(row_vals[cat_idx]).strip() if cat_idx != -1 and row_vals[cat_idx] else "未分類"
            name = str(row_vals[name_idx]).strip() if name_idx != -1 and row_vals[name_idx] else "未命名食物"
            common_name = str(row_vals[common_idx]).strip() if common_idx != -1 and row_vals[common_idx] else ""

            # 建立全欄位 JSON 字典
            raw_details = {}
            for h_idx, h_name in enumerate(headers):
                if h_name and h_idx < len(row_vals):
                    v = row_vals[h_idx]
                    raw_details[h_name] = v if v is not None else ""

            obj, created = FDANutrition.objects.update_or_create(
                code=code,
                defaults={
                    "category": category,
                    "name": name,
                    "common_name": common_name,
                    "calories": parse_float(row_vals[cal_idx]) if cal_idx != -1 else 0.0,
                    "protein": parse_float(row_vals[protein_idx]) if protein_idx != -1 else 0.0,
                    "fat": parse_float(row_vals[fat_idx]) if fat_idx != -1 else 0.0,
                    "carbs": parse_float(row_vals[carbs_idx]) if carbs_idx != -1 else 0.0,
                    "fiber": parse_float(row_vals[fiber_idx]) if fiber_idx != -1 else 0.0,
                    "sodium": parse_float(row_vals[sodium_idx]) if sodium_idx != -1 else 0.0,
                    "sugar": parse_float(row_vals[sugar_idx]) if sugar_idx != -1 else 0.0,
                    "raw_details": json.dumps(raw_details, ensure_ascii=False),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"成功完成衛福部 FDA 食品營養庫更新！新增 {created_count} 筆，更新 {updated_count} 筆，共 {created_count + updated_count} 筆資料。"
        ))
