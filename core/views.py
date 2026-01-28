from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from google import genai

from notices.models import AISystemSetting, Announcement


@login_required
def profile_view(request):
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
