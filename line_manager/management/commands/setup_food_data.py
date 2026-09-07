import os
from django.core.management import call_command
from django.core.management.base import BaseCommand
from line_manager.models import NutrientReference, FoodAdditive, FDANutrition


class Command(BaseCommand):
    help = "一鍵初始化與設置伺服器端食品營養庫、添加物危害百科及營養標準資料"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-fetch",
            action="store_true",
            help="強制直接從衛福部官方重新爬取，跳過本機 package 匯入"
        )

    def handle(self, *args, **options):
        self.stdout.write("==================================================")
        self.stdout.write("[START] Starting Food Nutrition and Additives One-Click Setup...")
        self.stdout.write("==================================================")

        # 0. 執行資料庫遷移確認
        self.stdout.write("Step 0: Checking line_manager migrations...")
        call_command("migrate", "line_manager")

        package_path_gz = "food_data_package.json.gz"
        package_path_json = "food_data_package.json"
        force_fetch = options.get("force_fetch", False)

        has_package = (os.path.exists(package_path_gz) or os.path.exists(package_path_json)) and not force_fetch

        if has_package:
            target_pkg = package_path_gz if os.path.exists(package_path_gz) else package_path_json
            self.stdout.write(f"\n[PACKAGE] Detected snapshot package [{target_pkg}], importing directly...")
            call_command("import_food_data", input=target_pkg)
        else:
            self.stdout.write("\n[ONLINE] Initializing directly via TFDA official sources...")
            
            # 1. 營養標準
            self.stdout.write("\nStep 1/3: Initializing DRIs nutrition references...")
            call_command("init_nutrient_references")

            # 2. 食品添加物
            self.stdout.write("\nStep 2/3: Initializing 17-class food additives knowledge base...")
            call_command("init_food_additives")

            # 3. FDA 食品營養成分
            self.stdout.write("\nStep 3/3: Fetching and parsing FDA food nutrition database...")
            call_command("fetch_fda_nutrition")

        # 最終統計與核對
        c_nut = NutrientReference.objects.count()
        c_add = FoodAdditive.objects.count()
        c_fda = FDANutrition.objects.count()

        self.stdout.write("\n==================================================")
        self.stdout.write("[DONE] All food databases setup completed successfully!")
        self.stdout.write(f"  * DRIs Nutrition Standards: {c_nut} records")
        self.stdout.write(f"  * Food Additives & Hazards: {c_add} records")
        self.stdout.write(f"  * FDA Food Nutrition Items: {c_fda} records")
        self.stdout.write("==================================================")
