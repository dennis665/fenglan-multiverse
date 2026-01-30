from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from google import genai

from notices.models import AISystemSetting, Announcement, TicketRecord


@login_required
def profile_view(request):
    #! 處理使用者點擊「更新照片」的 POST 請求
    if request.method == "POST":
        avatar_file = request.FILES.get("avatar")
        if avatar_file:
            profile = request.user.profile
            profile.avatar = avatar_file
            profile.save()
            messages.success(request, "大頭貼更新成功！")
            return redirect("profile")
    #! 因為使用了 socialaccount，我們可以在模板中拿到 Google 的資料
    return render(request, "core/profile.html")


def portal_ai_bot(request):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    if request.method == "POST":
        user_query = request.POST.get("message")

        #! 從 DB 讀取後台設定的指令
        ai_setting = AISystemSetting.objects.filter(is_active=True).last()
        base_instruction = ai_setting.instruction_text if ai_setting else "你是一位親切的助手。"
        web_info = ai_setting.website_info if ai_setting else ""

        #! 從 DB 讀取最新 5 則公告（即時學習內容）
        latest_notices = Announcement.objects.all().order_by("-created_at")[:5]
        notice_context = "\n".join([f"- {n.title}: {n.content[:50]}..." for n in latest_notices])

        #! 組合最終指令
        dynamic_instruction = f"""
        {base_instruction}

        ### 網站功能與資訊：
        {web_info}

        ### 最新公告資訊（請根據以下內容回答）：
        {notice_context if notice_context else "目前暫無公告。"}
        
        請記住，如果使用者問的問題在上述資訊之外，請委婉告知你只負責 CSI Portal 的相關諮詢。
        """

        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                config={"system_instruction": dynamic_instruction},
                contents=user_query,
            )
            return JsonResponse({"reply": response.text})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


def lucky_draw(request):
    return render(request, "core/lucky_draw.html")


def ticket_pull(request):
    #! 權限檢查：必須是登入狀態且具備工作人員 (is_staff) 以上權限
    if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
        messages.warning(request, "您不具備存取「發文簿系統」的權限，已自動導回首頁。")
        return redirect("home")

    if request.method == "POST":
        matter = request.POST.get("matter")
        applicant = request.POST.get("applicant")

        #! 計算民國年 (西元年 - 1911)
        now = timezone.now()
        minguo_year = now.year - 1911

        #! 定義前綴 (請自行更換這 5 個字，例如 'CSITW')
        dispatch_word = settings.DISPATCH_WORD

        #! 搜尋「今年」已發出的最後一筆號碼
        year_prefix = f"{dispatch_word}{minguo_year}"
        last_ticket = (
            TicketRecord.objects.filter(serial_number__startswith=year_prefix).order_by("serial_number").last()
        )

        if last_ticket:
            #! 抓取最後 3 位數字並加 1 (例如 '001' -> 1 -> 2)
            last_no = int(last_ticket.serial_number[-3:])
            new_no = last_no + 1
        else:
            #! 每年重製：今年第一筆從 1 開始
            new_no = 1

        #! 格式化為 11 位字元：前綴(5) + 年(3) + 編號(000, 3位)
        new_serial = f"{dispatch_word}{minguo_year}{new_no:03d}"

        #! 存檔
        TicketRecord.objects.create(serial_number=new_serial, matter=matter, applicant=applicant)

        return render(
            request, "core/ticket_success.html", {"serial": new_serial, "matter": matter, "applicant": applicant}
        )

    #! 取最新3筆歷史紀錄
    history = TicketRecord.objects.all().order_by("-date", "-id")[:3]
    return render(request, "core/ticket_pull.html", {"history": history})