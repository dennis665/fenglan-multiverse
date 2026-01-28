from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from google import genai


@login_required
def profile_view(request):
    #! 因為使用了 socialaccount，我們可以在模板中拿到 Google 的資料
    return render(request, "core/profile.html")


def portal_ai_bot(request):
    #! 初始化 Client
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    if request.method == "POST":
        user_query = request.POST.get("message")

        #! 定義系統指令：這是 AI 的知識來源
        system_instruction = """
        你現在是 CSI Portal 入口網的專屬小助手。
        回覆時請遵守以下排版規範：
        1. **使用標題**：重要分類請用 ### 或 ####。
        2. **條列化**：盡量使用 * 或 1. 2. 3. 列表。
        3. **適度加粗**：關鍵字使用 **關鍵字**。
        4. **使用分割線**：不同主題之間可以使用 --- 分隔。
        5. **加入表情符號**：在標題或段落開頭加入適合的 Emoji 增加親切感。
        本網站功能包含：
        1. 系統公告：查看 CSI 伺服器的最新通知。
        2. 測試專區：僅限管理者與測試員，包含 Squash TM、Redmine 等連結。
        3. 外部工具：可在後台動態新增工具並顯示圖示 (使用 FontAwesome)。
        請簡短、親切地回答使用者的疑問。
        """

        try:
            #! 使用最新的 Gemini 3 Flash 模型
            response = client.models.generate_content(
                model="gemini-flash-latest",  #! 2026/01/21 更新之別名
                config={"system_instruction": system_instruction},
                contents=user_query,
            )
            return JsonResponse({"reply": response.text})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)
