import requests
import urllib3
from django.core.management.base import BaseCommand

from invest.models import Stock

#! 關閉因為 verify=False 而產生的擾人警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Command(BaseCommand):
    help = "從台灣證券交易所 OpenAPI 取得並更新上市股票/ETF清單"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("正在連線至證交所 OpenAPI 獲取資料..."))

        #! 證交所 OpenAPI：每日收盤行情 (包含所有上市代碼與名稱)
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

        try:
            #! 加上 verify=False 略過憑證檢查
            response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            data = response.json()

            created_count = 0
            updated_count = 0

            for item in data:
                symbol = item.get("Code")
                name = item.get("Name")

                if not symbol or not name:
                    continue

                #! 簡單的分類邏輯：台股 ETF 通常是 00 開頭
                category = "ETF" if symbol.startswith("00") else "STOCK"

                #! 使用 update_or_create 確保不會重複新增，同時能更新名稱
                obj, created = Stock.objects.update_or_create(
                    symbol=symbol,
                    defaults={
                        "name": name,
                        "exchange": "TWSE",  # * 台灣證券交易所
                        "category": category,
                        "is_active": True,
                    },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            self.stdout.write(self.style.SUCCESS(f"✅ 匯入完成！新增: {created_count} 筆, 更新: {updated_count} 筆"))

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"連線失敗，請檢查網路狀態：{e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"發生未預期的錯誤：{e}"))
