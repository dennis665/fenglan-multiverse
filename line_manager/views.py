import json
from datetime import datetime

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, now, localtime
from django.views.decorators.csrf import csrf_exempt
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import JoinEvent, MessageEvent, TextMessageContent

from django.db.models import Q
from .models import Itinerary, LineProfile, GroupMembership

#! 初始化 LINE SDK 配置
configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)


def parse_itinerary_with_gemini(text):
    """呼叫 Gemini 進行自然語言解析，提取結構化的行程資料"""
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    current_time_str = now().strftime("%Y-%m-%d %H:%M:%S")
    current_year = now().year

    system_instruction = f"""
    你是一位行程時間解析專家。
    請仔細閱讀使用者的輸入內容，將其解析並整理成以下的 JSON 格式，且「絕對不要」包含任何 markdown 標記 (如 ```json) 或任何說明文字：
    {{
        "title": "行程標題 (如：吃拉麵、看展覽、羽球運動，最多 50 字)",
        "date_time": "西元日期與時間，格式為 YYYY-MM-DDTHH:MM:SS，如果使用者沒提到年份，請以當前年份 {current_year} 為主。如果使用者只說時間沒說日期，預設為當前日期，反之亦然。時間如果使用者沒說，預設為當日中午 12:00:00",
        "location": "行程地點 (如：中山站、大安運動中心，找不到則預設為 待定)",
        "activity_type": "活動類型代碼，必須是以下其中一個：EAT (吃飯聚餐), EXHIBIT (逛街展覽), SPORT (運動健身), TRAVEL (旅遊踏青), OTHER (其他活動)",
        "notify_days_before": 提前通知天數 (整數，如 1 代表前 1 天，使用者沒提到則預設為 1),
        "notes": "行程備註或解析說明"
    }}
    當前系統時間為：{current_time_str}
    """

    fallback_models = [
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite-preview",
    ]

    for model_name in fallback_models:
        try:
            print(f"🤖 [LINE Bot] 嘗試使用 {model_name} 進行語意解析...")
            response = client.models.generate_content(
                model=model_name,
                config={"system_instruction": system_instruction},
                contents=text,
            )
            raw_text = response.text.strip() if response.text else ""

            # 清洗 Markdown 格式
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed_data = json.loads(raw_text.strip())
            return parsed_data
        except Exception as e:
            print(f"❌ 使用 {model_name} 解析失敗: {e}")
            continue
    return None


def make_itinerary_flex_message(itinerary_data, liff_url):
    """組裝 LINE Flex Message 圖文卡片"""
    type_map = {
        "EAT": "🍴 吃飯聚餐",
        "EXHIBIT": "🎨 逛街展覽",
        "SPORT": "🏸 運動健身",
        "TRAVEL": "🚗 旅遊踏青",
        "OTHER": "🌟 其他活動",
    }
    act_type = type_map.get(itinerary_data.get("activity_type"), "🌟 其他活動")

    flex_json = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📅 行程小幫手",
                    "weight": "bold",
                    "color": "#1DB446",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": itinerary_data.get("title", "未命名行程"),
                    "weight": "bold",
                    "size": "xxl",
                    "margin": "md",
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "類型",
                                    "color": "#aaaaaa",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": act_type,
                                    "wrap": True,
                                    "color": "#666666",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "時間",
                                    "color": "#aaaaaa",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": itinerary_data.get("date_time", "").replace("T", " "),
                                    "wrap": True,
                                    "color": "#666666",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "地點",
                                    "color": "#aaaaaa",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": itinerary_data.get("location", "待定"),
                                    "wrap": True,
                                    "color": "#666666",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "提醒",
                                    "color": "#aaaaaa",
                                    "size": "sm",
                                    "flex": 2,
                                },
                                {
                                    "type": "text",
                                    "text": f"提前 {itinerary_data.get('notify_days_before', 1)} 天通知",
                                    "wrap": True,
                                    "color": "#666666",
                                    "size": "sm",
                                    "flex": 5,
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1DB446",
                    "action": {"type": "uri", "label": "查看與編輯行程", "uri": liff_url},
                }
            ],
            "flex": 0,
        },
    }
    return flex_json


@csrf_exempt
def line_webhook(request):
    """接收 LINE Webhook 事件的主端點"""
    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    signature = request.headers.get("X-Line-Signature") or request.META.get("HTTP_X_LINE_SIGNATURE")
    body = request.body.decode("utf-8")

    if not signature:
        return HttpResponse("Signature missing", status=400)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return HttpResponse("Invalid signature", status=400)

    return HttpResponse("OK")


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """處理收到的文字訊息：暫停 Gemini AI 解析，改為直接回傳看板連結"""
    text = event.message.text.strip()
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", None)

    # 判斷是否需要觸發小幫手
    is_triggered = False

    if group_id:
        # 群組模式下，需包含 "小幫手" 關鍵字
        if "小幫手" in text:
            is_triggered = True
    else:
        # 個人一對一對話，一律觸發
        is_triggered = True

    if not is_triggered:
        return

    # 建立 LIFF 看板連結
    liff_url = f"https://liff.line.me/{settings.LINE_LIFF_ID}"
    if group_id:
        liff_url += f"?groupId={group_id}"
        # 如果用戶在群組內呼叫小幫手，且已經綁定帳號，自動記錄群組關係
        profile = LineProfile.objects.filter(line_user_id=user_id).first()
        if profile:
            GroupMembership.objects.get_or_create(user=profile.user, group_id=group_id)

    reply_text = (
        "💡 您好！目前已暫停使用文字自動分析行程功能。\n\n"
        "請直接點擊以下連結進入專屬看板，即可手動新增、編輯備註，或瀏覽您的行程安排：\n"
        f"🔗 行程看板：{liff_url}"
    )

    with ApiClient(configuration) as api_client:
        api_instance = MessagingApi(api_client)
        api_instance.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]
            )
        )


@handler.add(JoinEvent)
def handle_join(event):
    """當 Bot 被邀請入群時發送歡迎語與公告教學建議"""
    group_id = getattr(event.source, "group_id", None)
    liff_url = f"https://liff.line.me/{settings.LINE_LIFF_ID}"
    if group_id:
        liff_url += f"?groupId={group_id}"

    with ApiClient(configuration) as api_client:
        api_instance = MessagingApi(api_client)
        welcome_text = (
            "👋 您好！我是行程小幫手！\n"
            "========================\n"
            "我已被成功邀請進入此群組，以下為大家介紹我的功能：\n\n"
            "💡 帳號安全綁定（極重要）\n"
            "請群組成員點擊下方連結完成綁定：\n"
            f"🔗 連結：{liff_url}\n"
            "（您可以選擇綁定既有的網站帳戶，或一鍵建立新帳戶。稍後亦可在選單中進行綁定。）\n\n"
            "✍️ 如何新增行程(此功能施工中)：\n"
            "在對話中呼叫「小幫手」加上行程內容，我會自動用語意分析幫大家記錄，例如：\n"
            "「小幫手 下週六晚上 6 點約在中山區吃飯聚餐，前 2 天通知我」\n\n"
            "📅 共享日曆看板：\n"
            "完成綁定的成員可以點擊上方連結直接打開群組共享行事曆與時間軸，共同新增、編輯備註或刪除行程。\n\n"
            "📌 溫馨提醒：\n"
            "因 LINE API 限制無法自動釘選訊息，建議管理員「手動將此條教學訊息設為公告」，方便大家隨時查閱喔！"
        )
        api_instance.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token, messages=[TextMessage(text=welcome_text)]
            )
        )


# ==============================================================================
# LIFF 網頁控制與資料 API
# ==============================================================================


def liff_itinerary_list(request):
    """LIFF 行程清單首頁（載入前端 LIFF 網頁，在 LINE App 中呈現）"""
    context = {
        "liff_id": settings.LINE_LIFF_ID,
    }
    return render(request, "line_manager/liff_list.html", context)


def liff_itinerary_create(request):
    """LIFF 新增行程網頁"""
    context = {
        "liff_id": settings.LINE_LIFF_ID,
    }
    return render(request, "line_manager/liff_create.html", context)


def liff_bind_account(request):
    """LIFF 綁定既有帳號網頁"""
    context = {
        "liff_id": settings.LINE_LIFF_ID,
    }
    return render(request, "line_manager/liff_bind.html", context)


@csrf_exempt
def api_get_itineraries(request):
    """API 端點：取得該使用者/群組的行程"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        group_id = data.get("group_id")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    # 向 LINE 驗證 Token 並取得 line_user_id
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    profile_data = res.json()
    line_user_id = profile_data["userId"]

    # 取得 Django 用戶
    line_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
    if not line_profile:
        return JsonResponse({"is_bound": False, "message": "User not bound"}, status=200)

    user = line_profile.user
    current_time = now()

    # 如果有傳入 group_id，記錄當前用戶與該群組的成員關係
    if group_id:
        GroupMembership.objects.get_or_create(user=user, group_id=group_id)

    # 取得該用戶加入的所有群組 ID
    user_group_ids = list(GroupMembership.objects.filter(user=user).values_list("group_id", flat=True))

    # 撈取行程：清單一律顯示自己的（包含個人行程以及該用戶所屬群組的所有行程）
    itineraries_qs = Itinerary.objects.filter(
        Q(user=user) | Q(group_id__in=user_group_ids)
    ).distinct().order_by("date_time")

    upcoming = []
    history = []

    type_map = {
        "EAT": "🍴 吃飯聚餐",
        "EXHIBIT": "🎨 逛街展覽",
        "SPORT": "🏸 運動健身",
        "TRAVEL": "🚗 旅遊踏青",
        "OTHER": "🌟 其他活動",
    }

    for item in itineraries_qs:
        # 解密加密欄位
        title_dec = item.title
        location_dec = item.location
        notes_dec = item.notes

        # 讀取建立者的 LINE 暱稱，若無則顯示系統帳號名稱
        try:
            creator_name = item.user.line_profile.line_display_name or item.user.username
        except AttributeError:
            creator_name = item.user.username

        # 將通知時間（分鐘）轉化為易讀的中文字串
        minutes = item.notify_minutes_before
        if minutes == 0:
            notify_text = "行程開始時"
        elif minutes < 60:
            notify_text = f"提前 {minutes} 分鐘"
        elif minutes < 1440:
            notify_text = f"提前 {minutes // 60} 小時"
        elif minutes % 1440 == 0:
            notify_text = f"提前 {minutes // 1440} 天"
        else:
            notify_text = f"提前 {minutes} 分鐘"

        schedule_data = {
            "id": item.pk,
            "title": title_dec,
            "location": location_dec,
            "notes": notes_dec,
            "activity_type": type_map.get(item.activity_type, "🌟 其他活動"),
            "date_time": localtime(item.date_time).strftime("%Y-%m-%d %H:%M"),
            "notify_minutes_before": minutes,
            "notify_text": notify_text,
            "is_notified": item.is_notified,
            "creator": creator_name,
        }

        if item.date_time >= current_time:
            upcoming.append(schedule_data)
        else:
            history.append(schedule_data)

    is_temporary = user.username.startswith("line_")

    return JsonResponse(
        {
            "is_bound": True,
            "is_temporary": is_temporary,
            "username": line_profile.line_display_name,
            "upcoming": upcoming,
            "history": history,
        }
    )


@csrf_exempt
def api_create_itinerary(request):
    """API 端點：透過 LIFF 網頁端新增行程"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        group_id = data.get("group_id")
        title = data.get("title")
        location = data.get("location")
        activity_type = data.get("activity_type", "OTHER")
        date_time_str = data.get("date_time")
        notify_minutes = int(data.get("notify_minutes_before", 1440))
        notes = data.get("notes", "")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not title or not date_time_str:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # 驗證 LINE Token
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_user_id = res.json()["userId"]
    line_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
    if not line_profile:
        return JsonResponse({"error": "Account not bound"}, status=403)

    try:
        dt = parse_datetime(date_time_str)
        if not dt:
            dt = datetime.fromisoformat(date_time_str)
        if dt.tzinfo is None:
            dt = make_aware(dt)
    except Exception:
        return JsonResponse({"error": "Invalid date_time format"}, status=400)

    itinerary = Itinerary.objects.create(
        user=line_profile.user,
        group_id=group_id if group_id else None,
        title=title,
        location=location if location else "待定",
        notes=notes,
        activity_type=activity_type,
        date_time=dt,
        notify_minutes_before=notify_minutes,
    )

    return JsonResponse({"status": "success", "id": itinerary.pk})


@csrf_exempt
def api_delete_itinerary(request, pk):
    """API 端點：刪除行程"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    # 驗證 LINE Token
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_user_id = res.json()["userId"]
    line_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
    if not line_profile:
        return JsonResponse({"error": "Account not bound"}, status=403)

    itinerary = Itinerary.objects.filter(pk=pk).first()
    if not itinerary:
        return JsonResponse({"error": "Itinerary not found"}, status=404)

    # 檢查是否為該群組成員或本人（群組行程允許群組成員刪除，私密行程僅限本人）
    if itinerary.group_id:
        # 群組行程，凡綁定之帳號皆有權限刪除
        itinerary.delete()
    else:
        # 個人行程限本人
        if itinerary.user != line_profile.user:
            return JsonResponse({"error": "Permission Denied"}, status=403)
        itinerary.delete()

    return JsonResponse({"status": "success"})


@csrf_exempt
def api_bind_account(request):
    """API 端點：綁定 LINE 用戶與 Django 帳號"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        action = data.get("action")  # 'bind' or 'auto_register'
        username = data.get("username")
        password = data.get("password")
        group_id = data.get("group_id")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    # 驗證 LINE Token
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    profile_data = res.json()
    line_user_id = profile_data["userId"]
    line_display_name = profile_data.get("displayName", "LINE 用戶")

    # 如果是綁定當前 Session 用戶 (例如透過 Google OAuth 登入的用戶)
    if action == "bind_current_user":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "您尚未在網站中登入帳號"}, status=400)

        user = request.user

        # 移轉行程資料：如果這個 LINE 帳號之前已經綁定過舊的虛擬帳號，我們把舊帳號底下的行程移轉給新的 Google 登入帳號
        old_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
        if old_profile:
            old_user = old_profile.user
            if old_user != user:
                # 轉移舊行程到新用戶
                Itinerary.objects.filter(user=old_user).update(user=user)
                # 刪除舊 Profile 綁定
                old_profile.delete()
                # 刪除舊的臨時虛擬帳戶，以清空 auth_user
                if old_user.username.startswith("line_"):
                    old_user.delete()
            else:
                return JsonResponse({"status": "success", "username": user.username})

        # 確保該新 User 沒有綁定過其他的 LINE 帳號
        LineProfile.objects.filter(user=user).delete()

        # 建立新的 LINE 個人連結
        LineProfile.objects.create(
            user=user, line_user_id=line_user_id, line_display_name=line_display_name
        )
        if group_id:
            GroupMembership.objects.get_or_create(user=user, group_id=group_id)
        return JsonResponse({"status": "success", "username": user.username})

    # 檢查是否已綁定 (當未提供 action 時)
    if not action:
        existing = LineProfile.objects.filter(line_user_id=line_user_id).first()
        if existing:
            return JsonResponse({"status": "success", "username": existing.user.username})

    if action == "bind":
        # 驗證 Django 既有帳密
        from django.contrib.auth import authenticate

        user = authenticate(username=username, password=password)
        if not user:
            return JsonResponse({"error": "帳號或密碼錯誤"}, status=400)

        # 移轉行程資料：如果之前有臨時的虛擬帳戶，將其行程移轉，並刪除該臨時帳戶
        old_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
        if old_profile:
            old_user = old_profile.user
            if old_user != user:
                # 轉移舊行程到新用戶
                Itinerary.objects.filter(user=old_user).update(user=user)
                # 刪除舊 Profile 綁定
                old_profile.delete()
                # 刪除舊的臨時虛擬帳戶，以清空 auth_user
                if old_user.username.startswith("line_"):
                    old_user.delete()

        # 進行綁定
        # 如果該 User 已與其他 LINE 綁定，先解除
        LineProfile.objects.filter(user=user).delete()
        LineProfile.objects.create(
            user=user, line_user_id=line_user_id, line_display_name=line_display_name
        )
        if group_id:
            GroupMembership.objects.get_or_create(user=user, group_id=group_id)
        return JsonResponse({"status": "success", "username": user.username})

    elif action == "auto_register":
        # 一鍵建立全新帳號
        new_username = f"line_{line_user_id[:15]}"
        user = User.objects.filter(username=new_username).first()
        if not user:
            user = User.objects.create_user(username=new_username)

        LineProfile.objects.create(
            user=user, line_user_id=line_user_id, line_display_name=line_display_name
        )
        if group_id:
            GroupMembership.objects.get_or_create(user=user, group_id=group_id)
        return JsonResponse({"status": "success", "username": user.username})

    return JsonResponse({"error": "Invalid Action"}, status=400)
