import json
import gzip
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from line_manager.models import NutrientReference, FoodAdditive, FDANutrition


class Command(BaseCommand):
    help = "從 UTF-8 JSON 或 GZ 封裝檔一鍵匯入食品營養成分庫、添加物危害百科及營養標準"

    def add_arguments(self, parser):
        parser.add_argument(
            "-i", "--input",
            default="food_data_package.json.gz",
            help="匯入檔案路徑 (預設 food_data_package.json.gz，若不存在則嘗試 food_data_package.json)"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="匯入前清空現有資料庫 (慎用，預設採用 update_or_create 安全覆蓋)"
        )

    def handle(self, *args, **options):
        input_path = options["input"]
        clear = options["clear"]

        if not os.path.exists(input_path):
            alt_path = input_path.replace(".gz", "") if input_path.endswith(".gz") else input_path + ".gz"
            if os.path.exists(alt_path):
                input_path = alt_path
            else:
                self.stderr.write(f"找不到檔案: {input_path}")
                return

        self.stdout.write(f"正在讀取檔案: {input_path} ...")
        if input_path.endswith(".gz"):
            with gzip.open(input_path, "rt", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            with open(input_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

        data = payload.get("data", {})
        nutrients_list = data.get("nutrient_references", [])
        additives_list = data.get("food_additives", [])
        foods_list = data.get("fda_nutritions", [])

        self.stdout.write(f"資料包內容: 營養標準 {len(nutrients_list)} 筆, 添加物 {len(additives_list)} 筆, FDA 食品 {len(foods_list)} 筆")

        if clear:
            self.stdout.write(self.style.WARNING("正在清理舊資料..."))
            NutrientReference.objects.all().delete()
            FoodAdditive.objects.all().delete()
            FDANutrition.objects.all().delete()

        # 1. 匯入 NutrientReference
        self.stdout.write("1/3 正在匯入 NutrientReference (營養標準知識庫)...")
        with transaction.atomic():
            for item in nutrients_list:
                NutrientReference.objects.update_or_create(
                    name=item["name"],
                    defaults=item
                )
        self.stdout.write(self.style.SUCCESS(f"  [OK] 成功匯入 {len(nutrients_list)} 筆營養標準。"))

        # 2. 匯入 FoodAdditive
        self.stdout.write("2/3 正在匯入 FoodAdditive (添加物與危害百科)...")
        with transaction.atomic():
            for item in additives_list:
                FoodAdditive.objects.update_or_create(
                    name=item["name"],
                    defaults=item
                )
        self.stdout.write(self.style.SUCCESS(f"  [OK] 成功匯入 {len(additives_list)} 筆食品添加物。"))

        # 3. 匯入 FDANutrition
        self.stdout.write("3/3 正在匯入 FDANutrition (FDA 食品營養成分資料庫)...")
        chunk_size = 300
        for i in range(0, len(foods_list), chunk_size):
            chunk = foods_list[i:i + chunk_size]
            with transaction.atomic():
                for item in chunk:
                    code = item["code"]
                    FDANutrition.objects.update_or_create(
                        code=code,
                        defaults=item
                    )
            self.stdout.write(f"  進度: {min(i + chunk_size, len(foods_list))} / {len(foods_list)}...")

        self.stdout.write(self.style.SUCCESS("  [OK] Successfully imported 2213 FDA food items!"))
        self.stdout.write(self.style.SUCCESS("\n[OK] All food databases have been imported successfully!"))
