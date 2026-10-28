from django.core.cache import cache
from django.db.models import F, Sum
from django.utils import timezone

from .models import ExternalTool, SiteVisit

#! 全站每頁都會執行，查詢結果放入快取以減少資料庫負擔
EXTERNAL_TOOLS_CACHE_KEY = "notices:external_tools"
EXTERNAL_TOOLS_CACHE_TTL = 600  # * 後台異動時會主動清除 (見 models.py 的 signal)
TODAY_COUNT_CACHE_TTL = 60
PAST_TOTAL_CACHE_TTL = 3600


def external_tools_processor(request):
    #! 將 QuerySet 轉換為 list，確保在迴圈中修改的物件屬性可以成功傳遞到樣板
    tools = cache.get(EXTERNAL_TOOLS_CACHE_KEY)
    if tools is None:
        tools = list(ExternalTool.objects.filter(is_active=True))
        cache.set(EXTERNAL_TOOLS_CACHE_KEY, tools, EXTERNAL_TOOLS_CACHE_TTL)

    for tool in tools:
        #! 自動判斷並補齊當前網站的協定與網域
        tool.url = request.build_absolute_uri(tool.url)  # * 直接覆蓋 url 屬性，樣板端完全不需要修改

    return {"external_tools": tools}


def visit_stats(request):
    today = timezone.now().date()
    today_cache_key = f"notices:visit_today:{today}"

    #! 判斷 Session，避免重複計數
    #! 檢查 Session 中是否有今天的造訪標記
    session_key = f"visited_{today}"
    if not request.session.get(session_key):
        #! 取得或建立今天的紀錄，並以 F() 原子遞增避免併發時遺失計數
        SiteVisit.objects.get_or_create(date=today)
        SiteVisit.objects.filter(date=today).update(daily_count=F("daily_count") + 1)
        cache.delete(today_cache_key)

        #! 標記為已造訪，並設定 Session 過期時間為 24 小時
        request.session[session_key] = True
        request.session.set_expiry(86400)

    today_count = cache.get(today_cache_key)
    if today_count is None:
        today_count = SiteVisit.objects.filter(date=today).values_list("daily_count", flat=True).first() or 0
        cache.set(today_cache_key, today_count, TODAY_COUNT_CACHE_TTL)

    #! 今天以前的總數當天不會再變動，快取起來只需加上今日數字
    past_total = cache.get_or_set(
        f"notices:visit_past_total:{today}",
        lambda: SiteVisit.objects.filter(date__lt=today).aggregate(Sum("daily_count"))["daily_count__sum"] or 0,
        PAST_TOTAL_CACHE_TTL,
    )

    #! 回傳字典，這兩個變數將可以在「全站」任何 HTML 中使用
    return {
        "today_count": today_count,
        "total_count": past_total + today_count,
    }
