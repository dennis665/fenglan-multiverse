import time
from decimal import Decimal

import yfinance as yf
from django.core.management.base import BaseCommand
from django.db import connection

from invest.models import Stock, StockPrice


class Command(BaseCommand):
    help = "從 Yahoo Finance 批量更新「所有」標的之最新股價"

    def handle(self, *args, **kwargs):
        #! 在向資料庫索取任何資料之前，強制斷開並清理已經失效的舊連線！
        connection.close_old_connections()

        #! 轉成 list 以便取得總數與迴圈處理
        stocks_to_update = list(Stock.objects.filter(is_active=True))
        total_stocks = len(stocks_to_update)

        self.stdout.write(self.style.SUCCESS(f"準備更新 {total_stocks} 檔標的報價..."))

        #! 先將資料庫已有的 StockPrice 撈出來轉成字典
        #! 這樣就不需要在迴圈裡一直去資料庫 SELECT 查詢了
        existing_prices = {sp.stock.pk: sp for sp in StockPrice.objects.filter(stock__in=stocks_to_update)}

        #! 準備三個陣列，用來「暫存」要寫入資料庫的物件
        prices_to_create = []
        prices_to_update = []
        stocks_to_deactivate = []

        for index, stock in enumerate(stocks_to_update, 1):
            yf_symbol = f"{stock.symbol}.TW" if stock.exchange == "TWSE" else f"{stock.symbol}.TWO"

            try:
                ticker = yf.Ticker(yf_symbol)
                current_price = Decimal(str(ticker.fast_info.last_price))
                prev_close = Decimal(str(ticker.fast_info.previous_close))

                daily_change = current_price - prev_close
                if prev_close > 0:
                    daily_change_percent = (daily_change / prev_close) * Decimal("100")
                else:
                    daily_change_percent = Decimal("0")

                #! 優化 3：判斷是要「更新」還是「新增」，然後塞進對應的陣列中
                if stock.pk in existing_prices:
                    sp = existing_prices[stock.pk]
                    sp.current_price = round(current_price, 2)
                    sp.daily_change = round(daily_change, 2)
                    sp.daily_change_percent = round(daily_change_percent, 2)
                    prices_to_update.append(sp)
                else:
                    prices_to_create.append(
                        StockPrice(
                            stock=stock,
                            current_price=round(current_price, 2),
                            daily_change=round(daily_change, 2),
                            daily_change_percent=round(daily_change_percent, 2),
                        )
                    )

                #! 加上進度條顯示，讓你知道它沒當機
                self.stdout.write(f"[{index}/{total_stocks}] ✅ {stock.symbol} | 股價: {current_price:.2f}")

                #! 因為資料庫時間省下來了，這裡的保護機制可以稍微縮短到 0.1 ~ 0.2 秒
                time.sleep(0.1)

            except Exception:
                self.stdout.write(self.style.ERROR(f"[{index}/{total_stocks}] ❌ 更新 {stock.symbol} 失敗"))
                stock.is_active = False
                stocks_to_deactivate.append(stock)
                time.sleep(0.5)  # * 遇到錯誤時休息久一點再繼續

        #! 迴圈結束後，執行最終的「批量資料庫寫入」
        self.stdout.write(self.style.WARNING("\n⏳ 網路抓取完畢，開始將資料批量寫入資料庫..."))

        if prices_to_create:
            #! batch_size=500 代表每 500 筆打包成一個 SQL 語句發送，避免 SQL 太長爆炸
            StockPrice.objects.bulk_create(prices_to_create, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"✅ 成功批量新增 {len(prices_to_create)} 筆報價"))

        if prices_to_update:
            StockPrice.objects.bulk_update(
                prices_to_update, ["current_price", "daily_change", "daily_change_percent"], batch_size=500
            )
            self.stdout.write(self.style.SUCCESS(f"✅ 成功批量更新 {len(prices_to_update)} 筆報價"))

        if stocks_to_deactivate:
            Stock.objects.bulk_update(stocks_to_deactivate, ["is_active"], batch_size=500)
            self.stdout.write(self.style.WARNING(f"🚫 已批量停用 {len(stocks_to_deactivate)} 檔無效標的"))

        self.stdout.write(self.style.SUCCESS("🎉 所有報價更新完成！"))
