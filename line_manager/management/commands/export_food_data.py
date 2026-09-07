import json
import gzip
import os
from django.core.management.base import BaseCommand
from line_manager.models import NutrientReference, FoodAdditive, FDANutrition


class Command(BaseCommand):
    help = "導出食品營養成分庫、添加物危害百科及營養參考標準為 UTF-8 JSON 或 GZ 封裝檔"

    def add_arguments(self, parser):
        parser.add_argument(
            "-o", "--output",
            default="food_data_package.json.gz",
            help="導出檔案路徑 (副檔名為 .gz 則自動壓縮，預設 food_data_package.json.gz)"
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        self.stdout.write(f"開始整理並導出食品資料庫...")

        # 1. NutrientReference
        nutrients = []
        for obj in NutrientReference.objects.all():
            nutrients.append({
                "name": obj.name,
                "unit": obj.unit,
                "category": obj.category,
                "daily_recommended": obj.daily_recommended,
                "daily_upper_limit": obj.daily_upper_limit,
                "benefits": obj.benefits,
                "concerns": obj.concerns,
                "excess_hazards": obj.excess_hazards,
                "deficiency_hazards": obj.deficiency_hazards,
            })

        # 2. FoodAdditive
        additives = []
        for obj in FoodAdditive.objects.all():
            additives.append({
                "name": obj.name,
                "e_number": obj.e_number,
                "category": obj.category,
                "purpose": obj.purpose,
                "common_foods": obj.common_foods,
                "health_hazards": obj.health_hazards,
                "safe_advice": obj.safe_advice,
            })

        # 3. FDANutrition
        foods = []
        for obj in FDANutrition.objects.all():
            foods.append({
                "code": obj.code,
                "category": obj.category,
                "name": obj.name,
                "common_name": obj.common_name,
                "calories": obj.calories,
                "protein": obj.protein,
                "fat": obj.fat,
                "carbs": obj.carbs,
                "fiber": obj.fiber,
                "sodium": obj.sodium,
                "sugar": obj.sugar,
                "raw_details": obj.raw_details,
            })

        payload = {
            "version": "1.0",
            "meta": {
                "nutrient_reference_count": len(nutrients),
                "food_additive_count": len(additives),
                "fda_nutrition_count": len(foods),
            },
            "data": {
                "nutrient_references": nutrients,
                "food_additives": additives,
                "fda_nutritions": foods,
            }
        }

        self.stdout.write(f"導出統計: 營養標準 {len(nutrients)} 筆, 添加物 {len(additives)} 筆, FDA 食品成分 {len(foods)} 筆")

        if output_path.endswith(".gz"):
            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"[OK] 成功導出資料至 {output_path} (檔案大小: {size_mb:.2f} MB)"))
