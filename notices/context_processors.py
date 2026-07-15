from django.db.models import Sum
from django.utils import timezone

from .models import ExternalTool, SiteVisit


def external_tools_processor(request):
    #! 將 QuerySet 轉換為 list，確保在迴圈中修改的物件屬性可以成功傳遞到樣板
    tools = list(ExternalTool.objects.filter(is_active=True))

    for tool in tools:
        #! 自動判斷並補齊當前網站的協定與網域
        tool.url = request.build_absolute_uri(tool.url)  # * 直接覆蓋 url 屬性，樣板端完全不需要修改

    return {"external_tools": tools}

def visit_stats(request):
    today = timezone.now().date()

    #! 取得或建立今天的紀錄
    visit_obj, _ = SiteVisit.objects.get_or_create(date=today)

    #! 判斷 Session，避免重複計數
    #! 檢查 Session 中是否有今天的造訪標記
    session_key = f"visited_{today}"
    if not request.session.get(session_key):
        visit_obj.daily_count += 1
        visit_obj.save()

        #! 標記為已造訪，並設定 Session 過期時間為 24 小時
        request.session[session_key] = True
        request.session.set_expiry(86400)

    #! 取得總數 (加總所有日期的 daily_count)
    total_count = SiteVisit.objects.aggregate(Sum("daily_count"))["daily_count__sum"] or 0

    #! 回傳字典，這兩個變數將可以在「全站」任何 HTML 中使用
    return {
        "today_count": visit_obj.daily_count,
        "total_count": total_count,
    }
