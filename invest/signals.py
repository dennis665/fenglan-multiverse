from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Holding, Transaction


def recalculate_holding(portfolio, stock):
    """
    重新計算指定投資組合中，某檔股票的總股數與平均成本。
    這支程式會撈出所有歷史交易紀錄，按照時間順序從頭推演一次。
    （這樣做最安全，即使使用者「修改」或「刪除」了過去的歷史紀錄，也能算出正確的當前狀態）
    """
    #! 按照交易日期與建立時間「由舊到新」排序
    transactions = Transaction.objects.filter(portfolio=portfolio, stock=stock).order_by("trade_date", "created_at")

    total_shares = Decimal("0")
    average_cost = Decimal("0")

    for tx in transactions:
        if tx.transaction_type == "BUY":
            #! 買入：重新攤平計算平均成本
            current_total_value = total_shares * average_cost
            #! 單筆交易總成本 = (股數 * 單價) + 手續費 + 稅金
            tx_total_cost = (tx.shares * tx.price_per_share) + tx.fee + tx.tax

            total_shares += tx.shares
            if total_shares > Decimal("0"):
                average_cost = (current_total_value + tx_total_cost) / total_shares

        elif tx.transaction_type == "SELL":
            #! 賣出：減少庫存，平均成本保持不變
            total_shares -= tx.shares
            if total_shares <= Decimal("0"):
                total_shares = Decimal("0")
                average_cost = Decimal("0")

        #! DIVIDEND (股息) 通常不影響持股數量與持有成本（除非是配股），這裡先略過

    #! 更新或建立 Holding 紀錄
    Holding.objects.update_or_create(
        portfolio=portfolio, stock=stock, defaults={"total_shares": total_shares, "average_cost": average_cost}
    )


#! 監聽 Transaction 的「儲存後」與「刪除後」事件
@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def update_holding_on_transaction_change(sender, instance, **kwargs):
    """當有一筆交易被新增、修改或刪除時，觸發重新計算"""
    recalculate_holding(instance.portfolio, instance.stock)
