import json
from datetime import datetime

import requests

# Force urllib3 to use IPv4 only to prevent IPv6 DNS timeout (common on Windows)
try:
    import socket

    import urllib3.util.connection as urllib3_cn

    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime, make_aware, now
from django.views.decorators.csrf import csrf_exempt
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexContainer,
    FlexMessage,
    LocationAction,
    MessagingApi,
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    JoinEvent,
    LocationMessageContent,
    MessageEvent,
    TextMessageContent,
)

from utils.logger_utils import jinfo, jinfo_error

from .models import GroupMembership, Itinerary, LineProfile

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
            jinfo(f"🤖 [LINE Bot] 嘗試使用 {model_name} 進行語意解析...")
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
            jinfo_error(e, f"❌ 使用 {model_name} 解析失敗")
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
    # 檢查是否開啟維護模式
    if getattr(settings, "LINE_MAINTENANCE_MODE", False):
        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="🤖 行程小幫手目前系統維護中，暫停服務，敬請見諒。")]
                )
            )
        return

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
        "💡 您好！歡迎使用行程小幫手！\n\n"
        "請直接點擊以下連結進入專屬看板，即可手動新增、編輯備註，或瀏覽您的行程安排：\n"
        f"🔗 行程看板：{liff_url}"
    )

    with ApiClient(configuration) as api_client:
        api_instance = MessagingApi(api_client)
        api_instance.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(
                        text=reply_text,
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyItem(
                                    action=LocationAction(label="📍 傳送定位以建立行程")
                                )
                            ]
                        )
                    )
                ]
            )
        )


@handler.add(JoinEvent)
def handle_join(event):
    """當 Bot 被邀請入群時發送歡迎語與公告教學建議"""
    # 檢查是否開啟維護模式
    if getattr(settings, "LINE_MAINTENANCE_MODE", False):
        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="🤖 行程小幫手目前系統維護中，暫停服務，敬請見諒。")]
                )
            )
        return

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


@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location(event):
    """當使用者傳送 LINE 原生定位時，回傳一鍵代入該地點的安排行程 Flex 訊息"""
    # 檢查是否開啟維護模式
    if getattr(settings, "LINE_MAINTENANCE_MODE", False):
        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="🤖 行程小幫手目前系統維護中，暫停服務，敬請見諒。")]
                )
            )
        return

    address = event.message.address
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", None)

    # 清理地址字串，移除「台灣」、「臺灣」、郵遞區號與逗號
    import re
    clean_address = re.sub(r'^\d+\s*(台灣|臺灣|Taiwan)?', '', address)
    clean_address = clean_address.replace("台灣", "").replace("臺灣", "").replace("Taiwan", "")
    clean_address = clean_address.replace(",", " ").strip()
    clean_address = re.sub(r'\b\d{3,5}\b', '', clean_address)
    clean_address = re.sub(r'\s+', ' ', clean_address).strip()

    if not clean_address:
        clean_address = "未指定地點"

    # 建立包含 location 的 LIFF 連結
    import urllib.parse
    liff_url = f"https://liff.line.me/{settings.LINE_LIFF_ID}/create/?location={urllib.parse.quote(clean_address)}"
    if group_id:
        liff_url += f"&groupId={group_id}"
        # 自動註冊群組關係
        profile = LineProfile.objects.filter(line_user_id=user_id).first()
        if profile:
            GroupMembership.objects.get_or_create(user=profile.user, group_id=group_id)

    # 建立精美的定位確認 Flex Message 卡片
    flex_contents = {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1DB446",
            "contents": [
                {
                    "type": "text",
                    "text": "📍 定位成功",
                    "color": "#ffffff",
                    "weight": "bold",
                    "size": "lg"
                }
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "您已傳送了以下位置：",
                    "size": "sm",
                    "color": "#666666"
                },
                {
                    "type": "text",
                    "text": clean_address,
                    "weight": "bold",
                    "size": "md",
                    "wrap": True,
                    "color": "#2c3e50"
                },
                {
                    "type": "text",
                    "text": "點擊下方按鈕，即可自動帶入此地點並快速安排行程！",
                    "size": "xs",
                    "color": "#999999",
                    "wrap": True
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "📅 點此安排行程",
                        "uri": liff_url
                    },
                    "style": "primary",
                    "color": "#1DB446"
                }
            ]
        }
    }

    try:
        flex_container = FlexContainer.from_dict(flex_contents)
        flex_message = FlexMessage(alt_text="📍 行程小幫手 - 定位確認", contents=flex_container)

        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[flex_message]
                )
            )
    except Exception as e:
        jinfo_error(e, "❌ 傳送定位確認 Flex Message 失敗")
        # 降級使用文字回覆
        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"📍 定位成功！\n地址：{clean_address}\n👉 點此安排行程：{liff_url}")]
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
    response = render(request, "line_manager/liff_list.html", context)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


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

    # 獲取群組成員名單對應表，避免 N+1 查詢
    from collections import defaultdict
    group_members_map = defaultdict(list)
    memberships = GroupMembership.objects.filter(group_id__in=user_group_ids).select_related('user__line_profile')
    for m in memberships:
        try:
            name = m.user.line_profile.line_display_name or m.user.username
        except AttributeError:
            name = m.user.username
        group_members_map[m.group_id].append(name)

    tab = data.get("tab", "upcoming")
    try:
        page = int(data.get("page", 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    # 撈取行程：清單一律顯示自己的（包含個人行程以及該用戶所屬群組的所有行程）
    # 依用戶要求：日期新至舊排序 (date_time 降序)
    base_qs = Itinerary.objects.filter(
        Q(user=user) | Q(group_id__in=user_group_ids),
        is_hidden=False
    ).distinct()

    if tab == "upcoming":
        itineraries_qs = base_qs.filter(date_time__gte=current_time).order_by("-date_time")
    elif tab == "unscheduled":
        itineraries_qs = base_qs.filter(date_time__isnull=True).order_by("-id")
    else:
        itineraries_qs = base_qs.filter(date_time__lt=current_time, date_time__isnull=False).order_by("-date_time")

    total_count = itineraries_qs.count()
    page_size = 5
    start = (page - 1) * page_size
    end = start + page_size

    # 資料庫層級分頁：只取出該頁面的 5 筆，節省效能
    sliced_qs = itineraries_qs[start:end]
    has_more = total_count > end

    list_data = []

    type_map = {
        "EAT": "🍴 吃飯聚餐",
        "EXHIBIT": "🎨 逛街展覽",
        "SPORT": "🏸 運動健身",
        "TRAVEL": "🚗 旅遊踏青",
        "MOVIE": "🎬 看電影",
        "OTHER": "🌟 其他活動",
    }

    for item in sliced_qs:
        # 解密加密欄位
        title_dec = item.title
        location_dec = item.location
        notes_dec = item.notes

        # 決定來源屬性（分辨個人與群組共用）
        is_group = False
        group_source = "個人行程"
        group_members = []
        if item.group_id:
            is_group = True
            group_members = group_members_map.get(item.group_id, [])
            from django.core.cache import cache
            cache_key = f"line_group_name_{item.group_id}"
            group_name = cache.get(cache_key)
            if not group_name:
                try:
                    with ApiClient(configuration) as api_client:
                        api_instance = MessagingApi(api_client)
                        summary = api_instance.get_group_summary(item.group_id)
                        group_name = summary.group_name
                        cache.set(cache_key, group_name, timeout=86400)  # 快取 24 小時
                except Exception as e:
                    jinfo_error(e, f"Failed to fetch group summary for {item.group_id}")
                    group_name = f"群組 ({item.group_id[-6:]})"
            group_source = f"群組: {group_name}"

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

        # 解析相關活動連結與有興趣成員 (JSON 格式)
        related_links_list = []
        if item.related_links:
            try:
                related_links_list = json.loads(item.related_links)
            except Exception:
                pass

        interested_users_list = []
        if item.interested_users:
            try:
                interested_users_list = json.loads(item.interested_users)
            except Exception:
                pass

        schedule_data = {
            "id": item.pk,
            "title": title_dec,
            "location": location_dec,
            "notes": notes_dec,
            "activity_type": type_map.get(item.activity_type, "🌟 其他活動"),
            "date_time": localtime(item.date_time).strftime("%Y-%m-%d %H:%M") if item.date_time else "時間待定",
            "is_unscheduled": item.date_time is None,
            "related_links": related_links_list,
            "interested_users": interested_users_list,
            "notify_minutes_before": minutes,
            "notify_text": notify_text if item.date_time else "無提醒",
            "is_notified": item.is_notified,
            "creator": creator_name,
            "is_group": is_group,
            "group_source": group_source,
            "group_members": group_members,
        }
        list_data.append(schedule_data)

    is_temporary = user.username.startswith("line_")

    return JsonResponse(
        {
            "is_bound": True,
            "is_temporary": is_temporary,
            "username": line_profile.line_display_name,
            "list": list_data,
            "has_more": has_more,
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

    if not access_token or not title:
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

    dt = None
    if date_time_str:
        try:
            dt = parse_datetime(date_time_str)
            if not dt:
                dt = datetime.fromisoformat(date_time_str)
            if dt.tzinfo is None:
                dt = make_aware(dt)
        except Exception:
            return JsonResponse({"error": "Invalid date_time format"}, status=400)

    # 取得活動連結
    related_links_data = data.get("related_links", [])
    related_links_str = json.dumps(related_links_data, ensure_ascii=False)

    itinerary = Itinerary.objects.create(
        user=line_profile.user,
        group_id=group_id if group_id else None,
        title=title,
        location=location if location else "待定",
        notes=notes,
        activity_type=activity_type,
        date_time=dt,
        related_links=related_links_str,
        notify_minutes_before=notify_minutes,
    )

    if group_id:
        type_map = {
            "EAT": "🍴 吃飯聚餐",
            "EXHIBIT": "🎨 逛街展覽",
            "SPORT": "🏸 運動健身",
            "TRAVEL": "🚗 旅遊踏青",
            "MOVIE": "🎬 看電影",
            "OTHER": "🌟 其他活動",
        }
        act_type = type_map.get(activity_type, "🌟 其他活動")
        dt_display = dt.strftime("%Y-%m-%d %H:%M") if dt else "時間待定"

        flex_contents = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📢 新群組行程通知",
                        "weight": "bold",
                        "color": "#1DB446",
                        "size": "sm"
                    },
                    {
                        "type": "text",
                        "text": title,
                        "weight": "bold",
                        "size": "xl",
                        "margin": "md"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
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
                                    {"type": "text", "text": "類型", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                    {"type": "text", "text": act_type, "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "時間", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                    {"type": "text", "text": dt_display, "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "地點", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                    {"type": "text", "text": location if location else "待定", "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "發起人", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                    {"type": "text", "text": line_profile.line_display_name or line_profile.user.username, "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "🔗 開啟行程看板",
                            "uri": f"https://liff.line.me/{settings.LINE_LIFF_ID}/?groupId={group_id}"
                        }
                    }
                ]
            }
        }

        try:
            from linebot.v3.messaging import (
                FlexContainer,
                FlexMessage,
                PushMessageRequest,
            )
            with ApiClient(configuration) as api_client:
                api_instance = MessagingApi(api_client)
                api_instance.push_message(
                    PushMessageRequest(
                        to=group_id,
                        messages=[
                            FlexMessage(
                                alt_text=f"📢 新群組行程【{title}】已排定！",
                                contents=FlexContainer.from_dict(flex_contents)
                            )
                        ]
                    )
                )
        except Exception as e:
            jinfo_error(e, "❌ 群組行程建立推播通知失敗")

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


@csrf_exempt
def api_get_itinerary_detail(request, pk):
    """API 端點：取得單一行程詳細資料（供修改頁面預填使用）"""
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

    # 檢查是否為該群組成員或本人
    can_view = False
    if itinerary.user == line_profile.user:
        can_view = True
    elif itinerary.group_id:
        if GroupMembership.objects.filter(user=line_profile.user, group_id=itinerary.group_id).exists():
            can_view = True

    if not can_view:
        return JsonResponse({"error": "Permission Denied"}, status=403)

    from django.utils.timezone import localtime
    related_links_list = []
    if itinerary.related_links:
        try:
            related_links_list = json.loads(itinerary.related_links)
        except Exception:
            pass

    interested_users_list = []
    if itinerary.interested_users:
        try:
            interested_users_list = json.loads(itinerary.interested_users)
        except Exception:
            pass

    dt_str = localtime(itinerary.date_time).strftime("%Y-%m-%dT%H:%M") if itinerary.date_time else ""
    is_expired = itinerary.date_time <= now() if itinerary.date_time else False

    return JsonResponse({
        "status": "success",
        "id": itinerary.pk,
        "title": itinerary.title,
        "location": itinerary.location,
        "notes": itinerary.notes,
        "activity_type": itinerary.activity_type,
        "date_time": dt_str,
        "related_links": related_links_list,
        "interested_users": interested_users_list,
        "notify_minutes_before": itinerary.notify_minutes_before,
        "is_expired": is_expired
    })


@csrf_exempt
def api_update_itinerary(request, pk):
    """API 端點：修改行程"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        title = data.get("title")
        location = data.get("location")
        activity_type = data.get("activity_type", "OTHER")
        date_time_str = data.get("date_time")
        notify_minutes = int(data.get("notify_minutes_before", 1440))
        notes = data.get("notes", "")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not title:
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

    itinerary = Itinerary.objects.filter(pk=pk).first()
    if not itinerary:
        return JsonResponse({"error": "Itinerary not found"}, status=404)

    # 檢查權限
    can_edit = False
    if itinerary.user == line_profile.user:
        can_edit = True
    elif itinerary.group_id:
        if GroupMembership.objects.filter(user=line_profile.user, group_id=itinerary.group_id).exists():
            can_edit = True

    if not can_edit:
        return JsonResponse({"error": "Permission Denied"}, status=403)

    # 檢查是否過期
    if itinerary.date_time and itinerary.date_time <= now():
        return JsonResponse({"error": "Cannot edit expired itineraries"}, status=400)

    dt = None
    if date_time_str:
        try:
            dt = parse_datetime(date_time_str)
            if not dt:
                dt = datetime.fromisoformat(date_time_str)
            if dt.tzinfo is None:
                dt = make_aware(dt)
        except Exception:
            return JsonResponse({"error": "Invalid date_time format"}, status=400)

    # 取得活動連結
    related_links_data = data.get("related_links", [])
    related_links_str = json.dumps(related_links_data, ensure_ascii=False)

    # 更新欄位
    itinerary.title = title
    itinerary.location = location if location else "待定"
    itinerary.notes = notes
    itinerary.activity_type = activity_type
    itinerary.date_time = dt
    itinerary.related_links = related_links_str
    itinerary.notify_minutes_before = notify_minutes
    itinerary.is_notified = False  # 重設通知標記以重新輪詢發送
    itinerary.save()

    return JsonResponse({"status": "success"})


@csrf_exempt
def api_send_guide_message(request):
    """API 端點：點擊定位時由 Bot 發送步驟引導訊息到聊天室"""
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

    # 驗證 Access Token
    import requests
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    profile_data = res.json()
    line_user_id = profile_data["userId"]

    # 決定目標 (優先發送到群組，否則發送給個人)
    target_id = group_id if group_id else line_user_id

    # 引導文字
    guide_text = (
        "📢 行程小幫手引導定位中...\n\n"
        "請點選對話框左下角「+」 ➡️ 「位置資訊」選取地點並傳送。\n\n"
        "傳送位置後，點擊對話框中新出現的卡片按鈕，即可自動帶回所有剛才填寫的行程資訊！"
    )

    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.push_message(
                PushMessageRequest(
                    to=target_id,
                    messages=[TextMessage(text=guide_text)]
                )
            )
        return JsonResponse({"status": "success"})
    except Exception as e:
        jinfo_error(e, "❌ 發送定位引導訊息失敗")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def api_join_unscheduled_itinerary(request, pk):
    """API 端點：對時間未定的行程表達興趣 (👍 我有興趣/加入)"""
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

    # 驗證 LINE Token
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    profile_data = res.json()
    line_user_id = profile_data["userId"]
    line_display_name = profile_data.get("displayName", "LINE 用戶")

    line_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
    if not line_profile:
        return JsonResponse({"error": "Account not bound"}, status=403)

    itinerary = Itinerary.objects.filter(pk=pk).first()
    if not itinerary:
        return JsonResponse({"error": "Itinerary not found"}, status=404)

    # 解析並更新有興趣的成員列表
    interested_users_list = []
    if itinerary.interested_users:
        try:
            interested_users_list = json.loads(itinerary.interested_users)
        except Exception:
            pass

    if line_display_name not in interested_users_list:
        interested_users_list.append(line_display_name)
        itinerary.interested_users = json.dumps(interested_users_list, ensure_ascii=False)

    # 用戶於群組點入表達興趣時，同步更新行程的群組 ID
    if group_id and not itinerary.group_id:
        itinerary.group_id = group_id

    itinerary.save()

    return JsonResponse({
        "status": "success",
        "interested_users": interested_users_list
    })


@csrf_exempt
def api_set_unscheduled_time(request, pk):
    """API 端點：決定時間未定行程的最終時間，並升級為正式共享行程，推送 LINE 群組通知"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        date_time_str = data.get("date_time")
        group_id = data.get("group_id")  # 新傳入的群組 ID，方便在群組內定案時寫入
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not date_time_str:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # 驗證 LINE Token
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.line.me/v2/profile", headers=headers)
    if res.status_code != 200:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    profile_data = res.json()
    line_user_id = profile_data["userId"]
    _line_display_name = profile_data.get("displayName", "LINE 用戶")

    line_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
    if not line_profile:
        return JsonResponse({"error": "Account not bound"}, status=403)

    itinerary = Itinerary.objects.filter(pk=pk).first()
    if not itinerary:
        return JsonResponse({"error": "Itinerary not found"}, status=404)

    try:
        dt = parse_datetime(date_time_str)
        if not dt:
            dt = datetime.fromisoformat(date_time_str)
        if dt.tzinfo is None:
            dt = make_aware(dt)
    except Exception:
        return JsonResponse({"error": "Invalid date_time format"}, status=400)

    itinerary.date_time = dt
    if group_id:
        itinerary.group_id = group_id
    itinerary.is_notified = False
    itinerary.save()

    # 主動發送 Flex Message 通知群組或個人
    target_id = itinerary.group_id if itinerary.group_id else line_user_id

    # 組合有興趣名單字串
    interested_users_list = []
    if itinerary.interested_users:
        try:
            interested_users_list = json.loads(itinerary.interested_users)
        except Exception:
            pass

    interested_str = "、".join(interested_users_list) if interested_users_list else "尚無"

    # 行程類型對照
    type_map = {
        "EAT": "🍴 吃飯聚餐",
        "EXHIBIT": "🎨 逛街展覽",
        "SPORT": "🏸 運動健身",
        "TRAVEL": "🚗 旅遊踏青",
        "MOVIE": "🎬 看電影",
        "OTHER": "🌟 其他活動",
    }
    act_type = type_map.get(itinerary.activity_type, "🌟 其他活動")

    # 組織推播 Flex Message 卡片
    flex_contents = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🎉 行程定案推播通知",
                    "weight": "bold",
                    "color": "#1DB446",
                    "size": "sm"
                },
                {
                    "type": "text",
                    "text": itinerary.title,
                    "weight": "bold",
                    "size": "xl",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "md"
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
                                {"type": "text", "text": "類型", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                {"type": "text", "text": act_type, "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {"type": "text", "text": "定案時間", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                {"type": "text", "text": dt.strftime("%Y-%m-%d %H:%M"), "wrap": True, "color": "#ff4d4f", "weight": "bold", "size": "sm", "flex": 5}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {"type": "text", "text": "地點", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                {"type": "text", "text": itinerary.location, "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "spacing": "sm",
                            "contents": [
                                {"type": "text", "text": "參與成員", "color": "#aaaaaa", "size": "sm", "flex": 2},
                                {"type": "text", "text": interested_str, "wrap": True, "color": "#666666", "size": "sm", "flex": 5}
                            ]
                        }
                    ]
                }
            ]
        }
    }

    try:
        from linebot.v3.messaging import FlexContainer, FlexMessage, PushMessageRequest
        with ApiClient(configuration) as api_client:
            api_instance = MessagingApi(api_client)
            api_instance.push_message(
                PushMessageRequest(
                    to=target_id,
                    messages=[
                        FlexMessage(
                            alt_text=f"📢 行程【{itinerary.title}】已定案！",
                            contents=FlexContainer.from_dict(flex_contents)
                        )
                    ]
                )
            )
    except Exception as e:
        jinfo_error(e, "❌ 定案推播通知失敗")

    return JsonResponse({"status": "success"})


@csrf_exempt
def api_hide_itinerary(request, pk):
    """API 端點：將指定的行程標記為隱藏 (例如：隱藏歷史行程)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

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

    # 檢查權限：群組共享行程凡綁定者皆有權隱藏，個人行程限本人
    can_hide = False
    if itinerary.user == line_profile.user:
        can_hide = True
    elif itinerary.group_id:
        if GroupMembership.objects.filter(user=line_profile.user, group_id=itinerary.group_id).exists():
            can_hide = True

    if not can_hide:
        return JsonResponse({"error": "Permission Denied"}, status=403)

    itinerary.is_hidden = True
    itinerary.save()

    return JsonResponse({"status": "success"})


import time

_token_cache = {}  # key: access_token, value: (line_user_id, display_name, expire_time)


def _verify_token_with_cache(access_token):
    """自帶 10 分鐘快取的 LINE Token 驗證，避免高頻重複請求 LINE API"""
    if not access_token:
        return None, None
    now_ts = time.time()
    if access_token in _token_cache:
        line_user_id, display_name, expire = _token_cache[access_token]
        if now_ts < expire:
            return line_user_id, display_name

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        res = requests.get("https://api.line.me/v2/profile", headers=headers, timeout=5)
        if res.status_code == 200:
            profile_data = res.json()
            line_user_id = profile_data["userId"]
            display_name = profile_data.get("displayName", "LINE 用戶")
            _token_cache[access_token] = (line_user_id, display_name, now_ts + 600)
            return line_user_id, display_name
    except Exception as e:
        jinfo_error(e, "❌ LINE Token 驗證請求失敗")
    return None, None


def _get_or_create_profile(line_user_id, display_name="LINE 用戶"):
    """當前 LINE 帳號如未曾建立過 Profile，在此進行靜默自動註冊"""
    line_profile = LineProfile.objects.filter(line_user_id=line_user_id).first()
    if not line_profile:
        new_username = f"line_{line_user_id[:15]}"
        user = User.objects.filter(username=new_username).first()
        if not user:
            user = User.objects.create_user(username=new_username)
        line_profile = LineProfile.objects.create(
            user=user, line_user_id=line_user_id, line_display_name=display_name
        )
    return line_profile


@csrf_exempt
def api_get_friends(request):
    """API 端點：取得目前的好友列表與其他可供新增的會員列表 (支援名稱搜尋且僅曝露 LINE 顯示名稱)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        query = data.get("query", "").strip()
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    from .models import Friendship

    # 目前的好友 (只顯示 LINE 名稱)
    friendships = Friendship.objects.filter(user=user).select_related("friend__line_profile")
    friends_list = []
    friend_ids = []
    for f in friendships:
        friend_ids.append(f.friend.id)
        try:
            display_name = f.friend.line_profile.line_display_name or "未知 LINE 用戶"
        except AttributeError:
            display_name = "未知 LINE 用戶"
        friends_list.append({"id": f.friend.id, "display_name": display_name})

    # 其他已加入 LINE 的所有會員 (排除自己與現有好友，支援模糊搜尋)
    others_qs = LineProfile.objects.exclude(user=user).exclude(user__id__in=friend_ids)
    if query:
        others_qs = others_qs.filter(line_display_name__icontains=query)

    # 限制數量 (最多 30 個項目)
    others_qs = others_qs[:30]

    others_list = []
    for o in others_qs:
        others_list.append({"id": o.user.id, "display_name": o.line_display_name or "未設定名稱"})

    return JsonResponse({"status": "success", "friends": friends_list, "others": others_list})


@csrf_exempt
def api_add_friend(request):
    """API 端點：新增好友"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        friend_id = data.get("friend_id")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not friend_id:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    friend_user = User.objects.filter(id=friend_id).first()
    if not friend_user:
        return JsonResponse({"error": "Friend user not found"}, status=404)

    if user == friend_user:
        return JsonResponse({"error": "Cannot add yourself as a friend"}, status=400)

    from .models import Friendship

    # 雙向建立好友關係
    Friendship.objects.get_or_create(user=user, friend=friend_user)
    Friendship.objects.get_or_create(user=friend_user, friend=user)

    return JsonResponse({"status": "success"})


@csrf_exempt
def api_get_dramas(request):
    """API 端點：取得使用者的追劇進度清單或收到的推薦清單"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        tab = data.get("tab", "my_dramas")  # my_dramas, recommendations
        page = int(data.get("page", 1))
        if page < 1:
            page = 1
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    page_size = 6
    start = (page - 1) * page_size
    end = start + page_size

    from django.utils.timezone import localtime

    from .models import DramaRecommendation, UserDramaProgress

    list_data = []
    if tab == "my_dramas":
        progress_qs = (
            UserDramaProgress.objects.filter(user=user)
            .select_related("drama__creator__line_profile")
            .order_by("-updated_at")
        )
        q = data.get("q", "").strip().lower()
        cat = data.get("category", "").strip()

        # 記憶體內過濾與解密比對
        filtered_progress = []
        for p in progress_qs:
            d = p.drama
            if cat and d.category != cat:
                continue
            if q and q not in d.title.lower():
                continue
            filtered_progress.append(p)

        total_count = len(filtered_progress)
        sliced_qs = filtered_progress[start:end]
        has_more = total_count > end

        for p in sliced_qs:
            d = p.drama
            try:
                creator_name = d.creator.line_profile.line_display_name or "未知 LINE 用戶"
            except AttributeError:
                creator_name = "未知 LINE 用戶"

            links = []
            if d.info_links:
                try:
                    links = json.loads(d.info_links)
                except Exception:
                    pass

            list_data.append(
                {
                    "progress_id": p.pk,
                    "drama_id": d.pk,
                    "title": d.title,
                    "category": d.category,
                    "total_seasons": d.total_seasons,
                    "total_episodes": d.total_episodes,
                    "info_links": links,
                    "current_season": p.current_season,
                    "current_episode": p.current_episode,
                    "is_tracked": p.is_tracked,
                    "creator": creator_name,
                    "updated_at": localtime(d.updated_at).strftime("%Y-%m-%d %H:%M"),
                }
            )
    elif tab == "all_dramas":
        from .models import Drama
        dramas_qs = Drama.objects.all().select_related("creator__line_profile").order_by("-updated_at")

        q = data.get("q", "").strip().lower()
        cat = data.get("category", "").strip()

        # 記憶體內過濾與解密比對
        filtered_dramas = []
        for d in dramas_qs:
            if cat and d.category != cat:
                continue
            if q and q not in d.title.lower():
                continue
            filtered_dramas.append(d)

        total_count = len(filtered_dramas)
        sliced_dramas = filtered_dramas[start:end]
        has_more = total_count > end

        tracked_drama_ids = set(UserDramaProgress.objects.filter(user=user).values_list("drama_id", flat=True))

        for d in sliced_dramas:
            try:
                creator_name = d.creator.line_profile.line_display_name or "未知 LINE 用戶"
            except AttributeError:
                creator_name = "未知 LINE 用戶"

            links = []
            if d.info_links:
                try:
                    links = json.loads(d.info_links)
                except Exception:
                    pass

            list_data.append(
                {
                    "drama_id": d.pk,
                    "title": d.title,
                    "category": d.category,
                    "total_seasons": d.total_seasons,
                    "total_episodes": d.total_episodes,
                    "info_links": links,
                    "creator": creator_name,
                    "is_added": d.pk in tracked_drama_ids,
                    "updated_at": localtime(d.updated_at).strftime("%Y-%m-%d %H:%M"),
                }
            )
    else:
        rec_qs = (
            DramaRecommendation.objects.filter(to_user=user, is_accepted=False)
            .select_related("drama__creator__line_profile", "from_user__line_profile")
            .order_by("-created_at")
        )
        total_count = rec_qs.count()
        sliced_qs = rec_qs[start:end]
        has_more = total_count > end

        for r in sliced_qs:
            d = r.drama
            try:
                from_name = r.from_user.line_profile.line_display_name or "未知 LINE 用戶"
            except AttributeError:
                from_name = "未知 LINE 用戶"

            links = []
            if d.info_links:
                try:
                    links = json.loads(d.info_links)
                except Exception:
                    pass

            list_data.append(
                {
                    "recommendation_id": r.pk,
                    "drama_id": d.pk,
                    "title": d.title,
                    "category": d.category,
                    "total_seasons": d.total_seasons,
                    "total_episodes": d.total_episodes,
                    "info_links": links,
                    "from_user": from_name,
                    "recommend_notes": r.recommend_notes,
                    "created_at": localtime(r.created_at).strftime("%Y-%m-%d %H:%M"),
                }
            )

    return JsonResponse({"status": "success", "list": list_data, "has_more": has_more})


@csrf_exempt
def api_create_drama(request):
    """API 端點：建立新的追劇主檔並自動加入使用者的進度清單"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        title = data.get("title")
        category = data.get("category", "其他")
        total_seasons = int(data.get("total_seasons", 1))
        total_episodes = int(data.get("total_episodes", 0))
        links = data.get("info_links", [])
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not title:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    from .models import Drama, UserDramaProgress

    # 檢查同名劇集（解密比對）
    existing_titles = {d.title.strip() for d in Drama.objects.all()}
    if title.strip() in existing_titles:
        return JsonResponse({"error": f"劇名『{title}』已存在，請勿重複建立！"}, status=400)

    drama = Drama.objects.create(
        title=title,
        category=category,
        total_seasons=total_seasons,
        total_episodes=total_episodes,
        info_links=json.dumps(links, ensure_ascii=False),
        creator=user,
    )

    # 預設建立進度
    UserDramaProgress.objects.create(
        user=user, drama=drama, current_season=1, current_episode=1, is_tracked=False
    )

    return JsonResponse({"status": "success", "drama_id": drama.id})


@csrf_exempt
def api_update_drama_progress(request, pk):
    """API 端點：更新使用者個人的追劇進度（季/集）或追蹤狀態"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        current_season = data.get("current_season")
        current_episode = data.get("current_episode")
        is_tracked = data.get("is_tracked")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    from .models import UserDramaProgress

    progress = UserDramaProgress.objects.filter(user=user, drama_id=pk).first()
    if not progress:
        return JsonResponse({"error": "Progress not found"}, status=404)

    if current_season is not None:
        progress.current_season = int(current_season)
    if current_episode is not None:
        progress.current_episode = int(current_episode)
    if is_tracked is not None:
        progress.is_tracked = bool(is_tracked)

    progress.save()
    return JsonResponse({"status": "success"})


@csrf_exempt
def api_update_drama(request, pk):
    """API 端點：修改劇集的共享資訊。如連結有更新，將會推播通知其他追蹤該劇的好友"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        title = data.get("title")
        category = data.get("category")
        total_seasons = data.get("total_seasons")
        total_episodes = data.get("total_episodes")
        links = data.get("info_links")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    from .models import Drama, UserDramaProgress

    drama = Drama.objects.filter(pk=pk).first()
    if not drama:
        return JsonResponse({"error": "Drama not found"}, status=404)

    # 偵測連結是否異動
    links_changed = False
    old_links_str = drama.info_links or "[]"
    new_links_str = json.dumps(links, ensure_ascii=False) if links is not None else old_links_str

    if links is not None:
        try:
            old_list = json.loads(old_links_str)
            if old_list != links:
                links_changed = True
        except Exception:
            links_changed = True

    if title is not None:
        drama.title = title
    if category is not None:
        drama.category = category
    if total_seasons is not None:
        drama.total_seasons = int(total_seasons)
    if total_episodes is not None:
        drama.total_episodes = int(total_episodes)
    if links is not None:
        drama.info_links = new_links_str

    drama.save()

    # 如果有連結更新，發送 LINE 推播給有勾選追蹤的其他會員
    if links_changed:
        trackers = (
            UserDramaProgress.objects.filter(drama=drama, is_tracked=True)
            .select_related("user__line_profile")
        )
        if trackers.exists():
            editor_name = line_profile.line_display_name or user.username

            # 發送 Flex 卡片推播
            flex_contents = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🌟 追蹤劇集連結更新通知",
                            "weight": "bold",
                            "color": "#1DB446",
                            "size": "sm",
                        },
                        {
                            "type": "text",
                            "text": f"【{drama.title}】的相關資訊連結已更新！",
                            "weight": "bold",
                            "size": "md",
                            "margin": "md",
                            "wrap": True,
                        },
                        {"type": "separator", "margin": "md"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "margin": "md",
                            "spacing": "xs",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"更新者: {editor_name}",
                                    "size": "xs",
                                    "color": "#666666",
                                },
                                {
                                    "type": "text",
                                    "text": "請開啟追劇看板，於劇集卡片下方點擊新連結查看詳情！",
                                    "size": "xs",
                                    "color": "#888888",
                                    "wrap": True,
                                },
                            ],
                        },
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#1DB446",
                            "height": "sm",
                            "action": {
                                "type": "uri",
                                "label": "📺 開啟追劇看板",
                                "uri": f"https://liff.line.me/{settings.LINE_LIFF_ID}/?page=drama",
                            },
                        }
                    ],
                },
            }

            try:
                from linebot.v3.messaging import (
                    FlexContainer,
                    FlexMessage,
                    PushMessageRequest,
                )

                for t in trackers:
                    tracker_line_id = t.user.line_profile.line_user_id
                    if tracker_line_id:
                        with ApiClient(configuration) as api_client:
                            api_instance = MessagingApi(api_client)
                            api_instance.push_message(
                                PushMessageRequest(
                                    to=tracker_line_id,
                                    messages=[
                                        FlexMessage(
                                            alt_text=f"🌟 劇集【{drama.title}】相關連結已更新！",
                                            contents=FlexContainer.from_dict(flex_contents),
                                        )
                                    ],
                                )
                            )
            except Exception as e:
                jinfo_error(e, "❌ 追蹤者連結更新通知發送失敗")

    return JsonResponse({"status": "success"})


@csrf_exempt
def api_recommend_drama(request):
    """API 端點：向多個好友發送追劇推薦"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        drama_id = data.get("drama_id")
        friend_ids = data.get("friend_ids", [])
        recommend_notes = data.get("recommend_notes", "")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not drama_id or not friend_ids:
        return JsonResponse({"error": "Missing required fields"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    from .models import Drama, DramaRecommendation

    drama = Drama.objects.filter(pk=drama_id).first()
    if not drama:
        return JsonResponse({"error": "Drama not found"}, status=404)

    from_name = line_profile.line_display_name or user.username

    success_names = []
    skipped_names = []

    from .models import UserDramaProgress
    for fid in friend_ids:
        friend_user = User.objects.filter(id=fid).first()
        if not friend_user:
            continue

        try:
            friend_name = friend_user.line_profile.line_display_name or friend_user.username
        except AttributeError:
            friend_name = friend_user.username

        # 1. 防呆：檢查對方是否已在追此劇
        if UserDramaProgress.objects.filter(user=friend_user, drama=drama).exists():
            skipped_names.append(f"{friend_name} (已在追此劇)")
            continue

        # 2. 防呆：檢查是否已推薦過且對方尚未接受
        if DramaRecommendation.objects.filter(to_user=friend_user, drama=drama, is_accepted=False).exists():
            skipped_names.append(f"{friend_name} (已推薦過，等待接受中)")
            continue

        # 3. 建立推薦紀錄
        DramaRecommendation.objects.create(
            from_user=user,
            to_user=friend_user,
            drama=drama,
            recommend_notes=recommend_notes,
        )
        success_names.append(friend_name)

        # 推送 LINE 訊息通知被推薦的好友
        try:
            friend_line_id = friend_user.line_profile.line_user_id
            if friend_line_id:
                flex_contents = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "📬 收到好友追劇推薦",
                                "weight": "bold",
                                "color": "#1DB446",
                                "size": "sm",
                            },
                            {
                                "type": "text",
                                "text": f"【{drama.title}】",
                                "weight": "bold",
                                "size": "lg",
                                "margin": "md",
                            },
                            {"type": "separator", "margin": "md"},
                            {
                                "type": "box",
                                "layout": "vertical",
                                "margin": "md",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": f"推薦人: {from_name}",
                                        "size": "xs",
                                        "color": "#666666",
                                    },
                                    {
                                        "type": "text",
                                        "text": f"推薦語: {recommend_notes}"
                                        if recommend_notes
                                        else "推薦這部劇給您！",
                                        "size": "xs",
                                        "color": "#888888",
                                        "wrap": True,
                                        "margin": "xs",
                                    },
                                ],
                            },
                        ],
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "button",
                                "style": "primary",
                                "color": "#1DB446",
                                "height": "sm",
                                "action": {
                                    "type": "uri",
                                    "label": "📺 查看推薦清單",
                                    "uri": f"https://liff.line.me/{settings.LINE_LIFF_ID}/?page=drama",
                                },
                            }
                        ],
                    },
                }

                from linebot.v3.messaging import (
                    FlexContainer,
                    FlexMessage,
                    PushMessageRequest,
                )

                with ApiClient(configuration) as api_client:
                    api_instance = MessagingApi(api_client)
                    api_instance.push_message(
                        PushMessageRequest(
                            to=friend_line_id,
                            messages=[
                                FlexMessage(
                                    alt_text=f"📬 好友 {from_name} 推薦了劇集【{drama.title}】給您！",
                                    contents=FlexContainer.from_dict(flex_contents),
                                )
                            ],
                        )
                    )
        except Exception as e:
            jinfo_error(e, f"❌ 傳送好友推薦通知失敗 to {friend_user.username}")

    if not success_names and skipped_names:
        return JsonResponse({
            "status": "error",
            "error": "、".join(skipped_names)
        })

    return JsonResponse({
        "status": "success",
        "success_list": success_names,
        "skipped_list": skipped_names
    })


@csrf_exempt
def api_accept_recommendation(request, pk):
    """API 端點：接受好友的推薦，將其加入自己的追劇進度表中"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    # 驗證 LINE Token
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user
    from .models import DramaRecommendation, UserDramaProgress

    rec = DramaRecommendation.objects.filter(pk=pk, to_user=user).first()
    if not rec:
        return JsonResponse({"error": "Recommendation not found"}, status=404)

    # 標記已接受
    rec.is_accepted = True
    rec.save()

    # 建立個人的追劇進度
    UserDramaProgress.objects.get_or_create(
        user=user,
        drama=rec.drama,
        defaults={"current_season": 1, "current_episode": 1, "is_tracked": False},
    )

    return JsonResponse({"status": "success"})

@csrf_exempt
def api_search_existing_dramas(request):
    """API 端點：搜尋資料庫中已存在的劇集，以供新增時自動填寫"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        query = data.get("q", "").strip().lower()
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    from .models import Drama
    dramas = Drama.objects.all().order_by("-id")

    results = []
    for d in dramas:
        if query and query not in d.title.lower():
            continue

        links = []
        if d.info_links:
            try:
                links = json.loads(d.info_links)
            except Exception:
                pass
        results.append({
            "id": d.id,
            "title": d.title,
            "category": d.category,
            "total_seasons": d.total_seasons,
            "total_episodes": d.total_episodes,
            "info_links": links
        })
        if len(results) >= 10:
            break

    return JsonResponse({"status": "success", "results": results})


@csrf_exempt
def api_join_drama(request, pk):
    """API 端點：將資料庫已存在的劇集加入個人追劇清單"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from .models import Drama, UserDramaProgress
    drama = Drama.objects.filter(pk=pk).first()
    if not drama:
        return JsonResponse({"error": "Drama not found"}, status=404)

    progress, created = UserDramaProgress.objects.get_or_create(
        user=user,
        drama=drama,
        defaults={"current_season": 1, "current_episode": 1, "is_tracked": False}
    )

    return JsonResponse({"status": "success", "already_exists": not created})


@csrf_exempt
def api_get_categories(request):
    """API 端點：取得目前資料庫中所有唯一的劇集分類與對應數量"""
    from .models import Drama, UserDramaProgress

    # 取得所有的劇集分類
    categories_qs = Drama.objects.values_list("category", flat=True)

    # 計算資料庫中全部劇集的分類數量
    all_counts = {}
    for cat in categories_qs:
        if cat:
            clean_cat = cat.strip()
            if clean_cat:
                all_counts[clean_cat] = all_counts.get(clean_cat, 0) + 1

    # 確保預設分類存在於 all_counts 中
    for default_cat in ["2026年7月新番", "動畫", "美劇", "日劇", "韓劇", "其他"]:
        if default_cat not in all_counts:
            all_counts[default_cat] = 0

    categories = list(all_counts.keys())

    # 檢查是否有傳入 access_token 以計算該使用者的追劇分類數量
    my_counts = {cat: 0 for cat in categories}
    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        if access_token:
            line_user_id, display_name = _verify_token_with_cache(access_token)
            if line_user_id:
                line_profile = _get_or_create_profile(line_user_id, display_name)
                user = line_profile.user

                # 取得使用者追劇中的分類與數量 (包含所有在個人追劇列表中的劇集)
                progress_qs = UserDramaProgress.objects.filter(user=user).values_list("drama__category", flat=True)
                for cat in progress_qs:
                    if cat:
                        clean_cat = cat.strip()
                        if clean_cat in my_counts:
                            my_counts[clean_cat] += 1
                        else:
                            my_counts[clean_cat] = 1
    except Exception:
        pass

    # 排序分類列表
    categories.sort()

    response = JsonResponse({
        "status": "success",
        "categories": categories,
        "all_counts": all_counts,
        "my_counts": my_counts
    })
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def liff_drama(request):
    """追劇行程 LIFF 頁面渲染視圖"""
    context = {
        "liff_id": settings.LINE_LIFF_ID,
    }
    response = render(request, "line_manager/liff_drama.html", context)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def liff_pet(request):
    """LINE Bot 寵物系統 LIFF 頁面渲染視圖"""
    context = {
        "liff_id": settings.LINE_LIFF_ID,
    }
    response = render(request, "line_manager/liff_pet.html", context)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@csrf_exempt
def api_line_pet_status(request):
    import traceback
    with open('django_api_call.log', 'a', encoding='utf-8') as log_f:
        log_f.write('api_line_pet_status called\n')
    
    """API 端點：取得 LINE 寵物系統首頁所需的完整狀態資料"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            access_token = data.get("access_token")
        except Exception:
            return JsonResponse({"error": "Invalid request body"}, status=400)
    elif request.method == "GET":
        access_token = request.GET.get("access_token")
    else:
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from datetime import date

    from django.utils.timezone import now

    from pet_system.models import (
        LinePet,
        LinePetExpedition,
        LinePetInventory,
        LinePetProfile,
        TowerProgress,
        UserAccessory,
    )
    from pet_system.views import ACCESSORY_SHOP

    # 取得或初始化
    profile, _ = LinePetProfile.objects.get_or_create(user=user)
    inventory, _ = LinePetInventory.objects.get_or_create(user=user)
    active_pet = LinePet.objects.filter(user=user, is_active=True).first()

    pet_data = None
    if active_pet:
        # 定義像素化渲染路徑
        pixel_img = "/static/pet_system/images/pet_egg.webp"
        if active_pet.pet_type == "DRAGON" and active_pet.stage == 0:
            pixel_img = "/static/pet_system/images/Mythical Beast Green Dragon Egg.webp"
        if active_pet.pet_type == "DRAGON":
            if active_pet.stage == 1:
                pixel_img = "/static/pet_system/images/baby_dragon.webp"
            elif active_pet.stage == 2:
                pixel_img = "/static/pet_system/images/growth_dragon.webp"
            elif active_pet.stage == 3:
                pixel_img = "/static/pet_system/images/complete_dragon.webp"
            elif active_pet.stage == 4:
                if active_pet.personality == "CHUBBY":
                    pixel_img = "/static/pet_system/images/pixel_chubby_dragon.webp"
                elif active_pet.personality == "BRAVE":
                    pixel_img = "/static/pet_system/images/pixel_star_dragon.webp"
                else:
                    pixel_img = "/static/pet_system/images/pixel_emerald_dragon.webp"
        else:  # PUPPY
            if active_pet.stage == 1:
                pixel_img = "/static/pet_system/images/baby_puppy.webp"
            elif active_pet.stage == 2:
                pixel_img = "/static/pet_system/images/growth_puppy.webp"
            elif active_pet.stage == 3:
                pixel_img = "/static/pet_system/images/complete_puppy.webp"
            elif active_pet.stage == 4:
                if active_pet.personality == "CHUBBY":
                    pixel_img = "/static/pet_system/images/pixel_chubby_puppy.webp"
                elif active_pet.personality == "BRAVE":
                    pixel_img = "/static/pet_system/images/pixel_star_puppy.webp"
                else:
                    pixel_img = "/static/pet_system/images/pixel_emerald_puppy.webp"

        pet_data = {
            "id": active_pet.id,
            "name": active_pet.name,
            "pet_type": active_pet.pet_type,
            "pet_type_display": active_pet.get_pet_type_display(),
            "stage": active_pet.stage,
            "stage_display": active_pet.get_stage_display(),
            "growth_progress": active_pet.growth_progress,
            "image": pixel_img,
            "equipped_head": active_pet.equipped_head,
            "equipped_face": active_pet.equipped_face,
            "equipped_back": active_pet.equipped_back,
            "personality": active_pet.personality,
            "personality_display": active_pet.get_personality_display(),
        }

    # 查詢所有待機中 (is_active=False) 的寵物
    inactive_pets = LinePet.objects.filter(user=user, is_active=False)
    inactive_pets_data = []
    for pet in inactive_pets:
        pixel_img = "/static/pet_system/images/pet_egg.webp"
        if pet.pet_type == "DRAGON" and pet.stage == 0:
            pixel_img = "/static/pet_system/images/Mythical Beast Green Dragon Egg.webp"
        if pet.pet_type == "DRAGON":
            if pet.stage == 1:
                pixel_img = "/static/pet_system/images/baby_dragon.webp"
            elif pet.stage == 2:
                pixel_img = "/static/pet_system/images/growth_dragon.webp"
            elif pet.stage == 3:
                pixel_img = "/static/pet_system/images/complete_dragon.webp"
            elif pet.stage == 4:
                if pet.personality == "CHUBBY":
                    pixel_img = "/static/pet_system/images/pixel_chubby_dragon.webp"
                elif pet.personality == "BRAVE":
                    pixel_img = "/static/pet_system/images/pixel_star_dragon.webp"
                else:
                    pixel_img = "/static/pet_system/images/pixel_emerald_dragon.webp"
        else:  # PUPPY
            if pet.stage == 1:
                pixel_img = "/static/pet_system/images/baby_puppy.webp"
            elif pet.stage == 2:
                pixel_img = "/static/pet_system/images/growth_puppy.webp"
            elif pet.stage == 3:
                pixel_img = "/static/pet_system/images/complete_puppy.webp"
            elif pet.stage == 4:
                if pet.personality == "CHUBBY":
                    pixel_img = "/static/pet_system/images/pixel_chubby_puppy.webp"
                elif pet.personality == "BRAVE":
                    pixel_img = "/static/pet_system/images/pixel_star_puppy.webp"
                else:
                    pixel_img = "/static/pet_system/images/pixel_emerald_puppy.webp"

        inactive_pets_data.append(
            {
                "id": pet.id,
                "name": pet.name,
                "pet_type": pet.pet_type,
                "pet_type_display": pet.get_pet_type_display(),
                "stage": pet.stage,
                "stage_display": pet.get_stage_display(),
                "growth_progress": pet.growth_progress,
                "image": pixel_img,
                "equipped_head": pet.equipped_head,
                "equipped_face": pet.equipped_face,
                "equipped_back": pet.equipped_back,
                "personality": pet.personality,
                "personality_display": pet.get_personality_display(),
            }
        )

    from pet_system.models import GoogleFitToken

    token_obj = GoogleFitToken.objects.filter(user=user).first()
    has_google_fit = token_obj is not None
    google_email = token_obj.google_email if token_obj else None

    # 獲取爬塔與裝飾配件進度
    tower, _ = TowerProgress.objects.get_or_create(user=user)
    unlocked_accessories = list(
        UserAccessory.objects.filter(user=user).values_list("accessory_id", flat=True)
    )
    has_daily_claim_today = profile.last_daily_claim == date.today()

    # 獲取當前出戰寵物的探索任務
    active_pet_expedition = None
    if active_pet:
        exp = LinePetExpedition.objects.filter(pet__user=user).exclude(status="CLAIMED").first()
        if exp:
            if exp.status == "ACTIVE" and now() >= exp.end_time:
                exp.status = "COMPLETED"
                exp.save()
            active_pet_expedition = {
                "id": exp.id,
                "duration_hours": exp.duration_hours,
                "end_time": exp.end_time.isoformat(),
                "status": exp.status,
                "seconds_left": max(0, int((exp.end_time - now()).total_seconds())),
            }

    return JsonResponse(
        {
            "status": "success",
            "coins": profile.pet_gold_coins,
            "last_sync_date": str(profile.last_sync_date) if profile.last_sync_date else "無",
            "last_sync_steps": profile.last_sync_steps,
            "has_google_fit": has_google_fit,
            "google_email": google_email,
            "has_daily_claim_today": has_daily_claim_today,
            "tower_floor": tower.current_floor,
            "unlocked_accessories": unlocked_accessories,
            "accessory_shop": ACCESSORY_SHOP,
            "active_pet_expedition": active_pet_expedition,
            "inventory": {
                "eggs_dragon": inventory.eggs_dragon,
                "eggs_puppy": inventory.eggs_puppy,
                "evo_potions": inventory.evo_potions,
            },
            "active_pet": pet_data,
            "inactive_pets": inactive_pets_data,
        }
    )

    from pet_system.models import GoogleFitToken

    token_obj = GoogleFitToken.objects.filter(user=user).first()
    has_google_fit = token_obj is not None
    google_email = token_obj.google_email if token_obj else None

    return JsonResponse(
        {
            "status": "success",
            "coins": profile.pet_gold_coins,
            "last_sync_date": str(profile.last_sync_date) if profile.last_sync_date else "無",
            "last_sync_steps": profile.last_sync_steps,
            "has_google_fit": has_google_fit,
            "google_email": google_email,
            "inventory": {
                "eggs_dragon": inventory.eggs_dragon,
                "eggs_puppy": inventory.eggs_puppy,
                "evo_potions": inventory.evo_potions,
            },
            "active_pet": pet_data,
            "inactive_pets": inactive_pets_data,
        }
    )


@csrf_exempt
def api_line_pet_sync_steps(request):
    """API 端點：同步 iOS 走路步數，並折算為金幣 (每 100 步折算 1 金幣)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        steps = int(data.get("steps", 0))
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)
    if steps < 0:
        return JsonResponse({"error": "Steps cannot be negative"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from datetime import date

    from pet_system.models import LinePetProfile

    profile, _ = LinePetProfile.objects.get_or_create(user=user)

    today = date.today()
    coins_added = 0

    # 設置每日上限步數 20,000 步 (即每日最多拿 200 金幣)
    effective_steps = min(steps, 20000)

    if profile.last_sync_date == today:
        # 同一天重複同步：只計算步數差值增量
        if effective_steps > profile.last_sync_steps:
            diff = effective_steps - profile.last_sync_steps
            coins_added = diff // 100
            profile.pet_gold_coins += coins_added
            profile.last_sync_steps = effective_steps
            profile.save()
    else:
        # 新的一天：重新累算今日步數
        coins_added = effective_steps // 100
        profile.pet_gold_coins += coins_added
        profile.last_sync_date = today
        profile.last_sync_steps = effective_steps
        profile.save()

    return JsonResponse(
        {
            "status": "success",
            "coins_added": coins_added,
            "total_coins": profile.pet_gold_coins,
            "synced_steps": steps,
        }
    )


@csrf_exempt
def api_line_pet_buy_item(request):
    """API 端點：以 LINE 寵物金幣購買蛋或進化藥水"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        item_type = data.get("item_type")  # EGG_DRAGON, EGG_PUPPY, EVO_POTION
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not item_type:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    # 定義售價
    prices = {"EGG_DRAGON": 50, "EGG_PUPPY": 50, "EVO_POTION": 10}
    if item_type not in prices:
        return JsonResponse({"error": "Invalid item type"}, status=400)

    cost = prices[item_type]
    from django.db import transaction

    from pet_system.models import LinePetInventory, LinePetProfile

    with transaction.atomic():
        profile, _ = LinePetProfile.objects.get_or_create(user=user)
        inventory, _ = LinePetInventory.objects.get_or_create(user=user)

        if profile.pet_gold_coins < cost:
            return JsonResponse({"error": "金幣餘額不足！"}, status=400)

        profile.pet_gold_coins -= cost
        profile.save()

        if item_type == "EGG_DRAGON":
            inventory.eggs_dragon += 1
            msg = "成功購買幻獸綠龍蛋！"
        elif item_type == "EGG_PUPPY":
            inventory.eggs_puppy += 1
            msg = "成功購買烈火幼犬蛋！"
        elif item_type == "EVO_POTION":
            inventory.evo_potions += 1
            msg = "成功購買奇蹟進化藥水！"
        else:
            return JsonResponse({"error": "Invalid item type"}, status=400)
        
        inventory.save()

    return JsonResponse(
        {
            "status": "success",
            "message": msg,
            "inventory": {
                "eggs_dragon": inventory.eggs_dragon,
                "eggs_puppy": inventory.eggs_puppy,
                "evo_potions": inventory.evo_potions,
            },
        }
    )


@csrf_exempt
def api_line_pet_evolve(request):
    """API 端點：進行 LINE 寵物進化形態升級"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from pet_system.models import LinePet

    pet = LinePet.objects.filter(user=user, is_active=True).first()
    if not pet:
        return JsonResponse({"error": "找不到出戰中的寵物"}, status=404)

    if pet.growth_progress < 100:
        return JsonResponse({"error": "成長值未達 100%，無法進化！"}, status=400)

    if pet.stage >= 4:
        return JsonResponse({"error": "寵物已達到最大進化型態！"}, status=400)

    pet.stage += 1
    if pet.stage < 4:
        pet.growth_progress = 0
    else:
        pet.growth_progress = 100

    # 進化改名與分支性格
    if pet.stage == 1:
        pet.name = "綠色雛龍" if pet.pet_type == "DRAGON" else "烈火幼犬"
    elif pet.stage == 2:
        pet.name = "成長體綠龍" if pet.pet_type == "DRAGON" else "成長體火犬"
    elif pet.stage == 3:
        pet.name = "完全體綠龍" if pet.pet_type == "DRAGON" else "完全體火犬"
    elif pet.stage == 4:
        if pet.feed_items_consumed == 0 and pet.potions_consumed == 0:
            pet.personality = "CHUBBY"
            pet.name = "肥嘟嘟守護龍" if pet.pet_type == "DRAGON" else "肥嘟嘟烈火犬"
        elif pet.potions_consumed > pet.feed_items_consumed:
            pet.personality = "BRAVE"
            pet.name = "烈焰星光龍" if pet.pet_type == "DRAGON" else "地獄烈焰犬"
        else:
            pet.personality = "NORMAL"
            pet.name = "自然翡翠龍" if pet.pet_type == "DRAGON" else "麒麟火犬"
    pet.save()

    return JsonResponse(
        {
            "status": "success",
            "message": f"恭喜！寵物成功進化為：{pet.name}！",
            "stage": pet.stage,
            "name": pet.name,
        }
    )


@csrf_exempt
def liff_pet_google_login(request):
    """將用戶重導向至 Google OAuth2 授權畫面，請求 Google Fit 步數讀取權限"""
    access_token = request.GET.get("access_token")
    if not access_token:
        return HttpResponse("LINE Access Token 缺失", status=400)

    google_app = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    client_id = google_app.get("client_id")
    if not client_id:
        return HttpResponse("系統未設定 GOOGLE_CLIENT_ID", status=500)

    # 取得當前網頁的 host 以動態建立 redirect_uri
    redirect_uri = request.build_absolute_uri(reverse("line_manager:liff_pet_google_callback"))

    # 授權 URL
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/fitness.activity.read email",
        "access_type": "offline",
        "prompt": "select_account consent",
        "state": access_token,  # 傳遞 LINE access_token 用以在 callback 辨識使用者
    }

    from urllib.parse import urlencode

    return redirect(f"{auth_url}?{urlencode(params)}")


@csrf_exempt
def liff_pet_google_callback(request):
    """Google 授權完成後的 CallBack 端點：交換 Token 並保存"""
    code = request.GET.get("code")
    access_token = request.GET.get("state")  # state 中帶的是 LINE access_token

    if not code or not access_token:
        return HttpResponse("授權參數缺失", status=400)

    # 驗證 LINE 使用者
    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return HttpResponse("驗證 LINE 憑證失敗", status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    # 交換 Google Token
    google_app = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    client_id = google_app.get("client_id")
    client_secret = google_app.get("secret")
    redirect_uri = request.build_absolute_uri(reverse("line_manager:liff_pet_google_callback"))

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    res = requests.post(token_url, data=data)
    if res.status_code != 200:
        return HttpResponse(f"Google 授權交換失敗：{res.text}", status=400)

    res_json = res.json()
    g_access_token = res_json.get("access_token")
    g_refresh_token = res_json.get(
        "refresh_token"
    )  # offline 且 prompt=consent 時 Google 一定會給 refresh_token
    expires_in = res_json.get("expires_in", 3600)

    import time

    from pet_system.models import GoogleFitToken

    # 嘗試呼叫 Google Userinfo API 獲取使用者 Email
    g_email = None
    try:
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        userinfo_res = requests.get(
            userinfo_url, headers={"Authorization": f"Bearer {g_access_token}"}
        )
        if userinfo_res.status_code == 200:
            g_email = userinfo_res.json().get("email")
    except Exception as e:
        print("Failed to fetch Google UserInfo:", e)

    # 保存或更新 (使用安全 filter+init 機製，避開 MySQL 的 get_or_create 插入 null IntegrityError)
    token_obj = GoogleFitToken.objects.filter(user=user).first()
    if not token_obj:
        token_obj = GoogleFitToken(user=user)

    token_obj.access_token = g_access_token
    token_obj.google_email = g_email
    if g_refresh_token:
        token_obj.refresh_token = g_refresh_token
    token_obj.expires_at = time.time() + expires_in
    token_obj.save()

    # 建立一個精美的成功跳導向 HTML，解決部分 Android Chrome 下 liff.line.me 重導向空白頁的問題
    success_html = f"""
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Google Fit 連結成功</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: #fff;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                padding: 20px;
            }}
            .glass-card {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 24px;
                border: 1px solid rgba(255, 255, 255, 0.15);
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                padding: 40px;
                text-align: center;
                max-width: 450px;
                width: 100%;
            }}
            .success-icon {{
                font-size: 60px;
                color: #38ef7d;
                margin-bottom: 20px;
                animation: scaleIn 0.5s ease;
            }}
            .btn-back {{
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                color: white;
                border: none;
                border-radius: 50px;
                font-weight: bold;
                padding: 12px 30px;
                transition: all 0.3s ease;
                text-decoration: none;
                display: inline-block;
                margin-top: 20px;
                box-shadow: 0 4px 15px rgba(56, 239, 125, 0.4);
            }}
            .btn-back:hover {{
                transform: translateY(-2px);
                opacity: 0.95;
            }}
            @keyframes scaleIn {{
                0% {{ transform: scale(0); }}
                100% {{ transform: scale(1); }}
            }}
        </style>
    </head>
    <body>
        <div class="glass-card">
            <div class="success-icon"><i class="fa-solid fa-circle-check"></i></div>
            <h4 class="fw-bold mb-2">Google Fit 連結成功！</h4>
            <p class="small text-white-50 mb-4">帳號已成功綁定。我們正嘗試自動開啟 LINE 返回遊戲，若手機沒有反應，請點擊下方按鈕或手動回 LINE 檢視。</p>
            <a href="line://app/{settings.LINE_LIFF_ID}?page=pet&google_success=1" class="btn-back">
                <i class="fa-brands fa-line me-2"></i>開啟 LINE 返回遊戲
            </a>
        </div>
        <script>
            // 嘗試自動呼叫 LINE App 原生連結進行跳轉
            setTimeout(function() {{
                window.location.href = "line://app/{settings.LINE_LIFF_ID}?page=pet&google_success=1";
            }}, 1200);
        </script>
    </body>
    </html>
    """
    return HttpResponse(success_html)


@csrf_exempt
def api_line_pet_sync_google_fit(request):
    """API 端點：拉取 Google Fit 步數並進行同步"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from pet_system.models import GoogleFitToken, LinePetProfile

    token_obj = GoogleFitToken.objects.filter(user=user).first()
    if not token_obj:
        return JsonResponse({"error": "unlinked", "message": "尚未連結 Google Fit"}, status=400)

    google_app = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})
    client_id = google_app.get("client_id")
    client_secret = google_app.get("secret")

    import time

    # 檢查並自動刷新 token
    now = time.time()
    if token_obj.expires_at <= now + 60:
        if not token_obj.refresh_token:
            return JsonResponse(
                {"error": "unlinked", "message": "Google Fit 憑證已過期，請重新綁定！"}, status=400
            )

        # 刷新 Google token
        token_url = "https://oauth2.googleapis.com/token"
        refresh_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token_obj.refresh_token,
            "grant_type": "refresh_token",
        }
        ref_res = requests.post(token_url, data=refresh_data)
        if ref_res.status_code == 200:
            ref_json = ref_res.json()
            token_obj.access_token = ref_json["access_token"]
            token_obj.expires_at = time.time() + ref_json["expires_in"]
            token_obj.save()
        else:
            return JsonResponse(
                {"error": "unlinked", "message": "Google 授權過期且刷新失敗，請重新綁定！"},
                status=400,
            )

    # 開始向 Google Fit API 取得今日步數
    from datetime import date, datetime

    today = date.today()
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    fit_url = "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate"
    headers = {
        "Authorization": f"Bearer {token_obj.access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "aggregateBy": [{"dataTypeName": "com.google.step_count.delta"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": start_ms,
        "endTimeMillis": end_ms,
    }

    try:
        fit_res = requests.post(fit_url, json=body, headers=headers)
        if fit_res.status_code != 200:
            return JsonResponse(
                {"error": "api_error", "message": f"Google Fit API 回傳錯誤: {fit_res.text}"},
                status=400,
            )

        fit_json = fit_res.json()
        buckets = fit_json.get("bucket", [])
        total_steps = 0
        for b in buckets:
            dataset = b.get("dataset", [])
            for ds in dataset:
                point = ds.get("point", [])
                for p in point:
                    value = p.get("value", [])
                    for v in value:
                        int_val = v.get("intVal")
                        fp_val = v.get("fpVal")
                        if int_val is not None:
                            total_steps += int_val
                        elif fp_val is not None:
                            total_steps += int(fp_val)
    except Exception as e:
        return JsonResponse(
            {"error": "api_error", "message": f"連線 Google Fit 失敗: {e}"}, status=500
        )

    # 執行步數折算與存摺同步
    profile, _ = LinePetProfile.objects.get_or_create(user=user)
    coins_added = 0

    # 設置每日上限步數 20,000 步 (即每日最多拿 200 金幣)
    effective_steps = min(total_steps, 20000)

    if profile.last_sync_date == today:
        if effective_steps > profile.last_sync_steps:
            diff = effective_steps - profile.last_sync_steps
            coins_added = diff // 100
            profile.pet_gold_coins += coins_added
            profile.last_sync_steps = effective_steps
            profile.save()
    else:
        coins_added = effective_steps // 100
        profile.pet_gold_coins += coins_added
        profile.last_sync_date = today
        profile.last_sync_steps = effective_steps
        profile.save()

    return JsonResponse(
        {
            "status": "success",
            "coins_added": coins_added,
            "total_coins": profile.pet_gold_coins,
            "synced_steps": total_steps,
        }
    )


@csrf_exempt
def api_line_pet_switch_active(request):
    """API 端點：切換召喚出戰的 LINE 寵物"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        pet_id = data.get("pet_id")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not pet_id:
        return JsonResponse({"error": "Parameters missing"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from pet_system.models import LinePet

    pet = LinePet.objects.filter(user=user, id=pet_id).first()
    if not pet:
        return JsonResponse({"error": "pet_not_found", "message": "找不到該寵物"}, status=404)

    # 切換出戰
    pet.is_active = True
    pet.save()  # LinePet 的 save 方法中會自動將該使用者的其它寵物 is_active 設為 False

    return JsonResponse({"status": "success", "message": f"成功召喚 {pet.name} 出戰！"})


@csrf_exempt
def api_line_pet_unlink_google_fit(request):
    """API 端點：解除綁定並刪除用戶的 Google Fit Token"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from pet_system.models import GoogleFitToken

    GoogleFitToken.objects.filter(user=user).delete()

    return JsonResponse({"status": "success", "message": "已成功解除 Google Fit 帳號連結！"})


@csrf_exempt
def api_line_pet_claim_daily_login(request):
    """API 端點：領取每日登入金幣 (50 金幣)"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from datetime import date

    from pet_system.models import LinePetProfile

    profile, _ = LinePetProfile.objects.get_or_create(user=user)

    today = date.today()
    if profile.last_daily_claim == today:
        return JsonResponse({"error": "您今天已經領取過每日登入獎勵囉！"}, status=400)

    profile.pet_gold_coins += 50
    profile.last_daily_claim = today
    profile.save()

    return JsonResponse(
        {
            "status": "success",
            "message": "成功領取每日登入獎勵 50 金幣！",
            "coins": profile.pet_gold_coins,
        }
    )


@csrf_exempt
def api_line_pet_buy_accessory(request):
    """API 端點：以 LINE 寵物金幣購買飾品配件"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        accessory_id = data.get("accessory_id")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not accessory_id:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    from pet_system.views import ACCESSORY_SHOP

    if accessory_id not in ACCESSORY_SHOP:
        return JsonResponse({"error": "商品不存在！"}, status=400)

    price = ACCESSORY_SHOP[accessory_id]["price"]

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from django.db import transaction

    from pet_system.models import LinePetProfile, UserAccessory

    with transaction.atomic():
        profile, _ = LinePetProfile.objects.select_for_update().get_or_create(user=user)

        # 檢查是否已擁有
        owned = UserAccessory.objects.filter(user=user, accessory_id=accessory_id).exists()
        if owned:
            return JsonResponse({"error": "您已經擁有該裝飾品囉，不須重複購買！"}, status=400)

        if profile.pet_gold_coins < price:
            return JsonResponse(
                {"error": "您的寵物金幣餘額不足，快去同步計步或挑戰關卡賺取！"}, status=400
            )

        # 扣款並發貨
        profile.pet_gold_coins -= price
        profile.save()

        UserAccessory.objects.create(user=user, accessory_id=accessory_id, quantity=1)

    return JsonResponse(
        {
            "status": "success",
            "message": f"成功購買裝飾品：{ACCESSORY_SHOP[accessory_id]['name']}！",
            "coins": profile.pet_gold_coins,
        }
    )


@csrf_exempt
def api_line_pet_equip_accessory(request):
    """API 端點：穿戴或卸下 LINE 寵物的裝扮配件"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        slot = data.get("slot")  # head, face, back
        accessory_id = data.get("accessory_id")  # 可為空字串，代表脫下
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not slot:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    if slot not in ["head", "face", "back"]:
        return JsonResponse({"error": "無效的裝備槽位！"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from pet_system.models import LinePet, UserAccessory
    from pet_system.views import ACCESSORY_SHOP

    pet = LinePet.objects.filter(user=user, is_active=True).first()
    if not pet:
        return JsonResponse({"error": "找不到出戰中的寵物"}, status=404)

    if accessory_id:
        # 檢查玩家是否擁有此配件
        owned = UserAccessory.objects.filter(user=user, accessory_id=accessory_id).exists()
        if not owned:
            return JsonResponse({"error": "您尚未擁有該配件，請先到商城購買！"}, status=400)

        # 檢查槽位是否匹配
        if ACCESSORY_SHOP.get(accessory_id, {}).get("slot") != slot:
            return JsonResponse({"error": "裝備槽位與配件類型不相符！"}, status=400)

    # 進行裝備/脫下
    if slot == "head":
        pet.equipped_head = accessory_id or None
    elif slot == "face":
        pet.equipped_face = accessory_id or None
    elif slot == "back":
        pet.equipped_back = accessory_id or None

    pet.save()

    return JsonResponse({"status": "success", "message": "已成功更新寵物裝備！"})


@csrf_exempt
def api_line_pet_tower_battle(request):
    """API 端點：LINE 寵物闖關爬塔結算"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        victory = data.get("victory") == True
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from django.db import transaction

    from pet_system.models import LinePetProfile, TowerProgress

    tower, _ = TowerProgress.objects.get_or_create(user=user)

    if not victory:
        return JsonResponse(
            {
                "status": "success",
                "message": "挑戰失敗！請提升寵物屬性或裝備後再次嘗試！",
                "current_floor": tower.current_floor,
            }
        )

    # 獲得金幣 = 當前層數 * 10
    reward_coins = tower.current_floor * 10

    with transaction.atomic():
        profile, _ = LinePetProfile.objects.select_for_update().get_or_create(user=user)
        profile.pet_gold_coins += reward_coins
        profile.save()

        tower.current_floor += 1
        tower.save()

    return JsonResponse(
        {
            "status": "success",
            "message": f"恭喜挑戰成功！進入第 {tower.current_floor} 層！獲得寵物金幣 x{reward_coins}！",
            "reward_coins": reward_coins,
            "new_floor": tower.current_floor,
            "coins": profile.pet_gold_coins,
        }
    )


@csrf_exempt
def api_line_pet_start_expedition(request):
    """API 端點：開始派遣 LINE 寵物探索"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        hours = int(data.get("hours", 1))
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or hours not in [1, 2, 4, 20]:
        return JsonResponse({"error": "Missing parameters or invalid hours"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from datetime import timedelta

    from django.utils.timezone import now

    from pet_system.models import LinePet, LinePetExpedition

    pet = LinePet.objects.filter(user=user, is_active=True).first()
    if not pet:
        return JsonResponse({"error": "目前沒有出戰的寵物！"}, status=400)

    # 檢查是否有未完成的派遣
    exists = LinePetExpedition.objects.filter(pet=pet).exclude(status="CLAIMED").exists()
    if exists:
        return JsonResponse({"error": "該寵物已在探索中，或是正等待領取獎勵！"}, status=400)

    end_time = now() + timedelta(hours=hours)
    LinePetExpedition.objects.create(
        pet=pet, duration_hours=hours, end_time=end_time, status="ACTIVE"
    )

    return JsonResponse(
        {
            "status": "success",
            "message": f"成功召喚 {pet.name} 出發探索！預計時長 {hours} 小時。",
            "end_time": end_time.isoformat(),
        }
    )


@csrf_exempt
def api_line_pet_cancel_expedition(request):
    """API 端點：取消探索派遣"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from pet_system.models import LinePet, LinePetExpedition

    pet = LinePet.objects.filter(user=user, is_active=True).first()
    if not pet:
        return JsonResponse({"error": "找不到出戰中的寵物"}, status=400)

    exp = LinePetExpedition.objects.filter(pet__user=user, status="ACTIVE").first()
    if not exp:
        return JsonResponse({"error": "沒有正在進行的探索任務可供取消"}, status=400)

    exp.delete()
    return JsonResponse({"status": "success", "message": "已成功取消探索派遣，寵物已歸隊。"})


@csrf_exempt
def api_line_pet_claim_expedition(request):
    """API 端點：領取探索派遣獎勵"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token:
        return JsonResponse({"error": "Access token required"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    import random

    from django.db import transaction
    from django.utils.timezone import now

    from pet_system.models import (
        LinePet,
        LinePetExpedition,
        LinePetInventory,
        LinePetProfile,
        UserAccessory,
    )
    from pet_system.views import ACCESSORY_SHOP

    pet = LinePet.objects.filter(user=user, is_active=True).first()
    if not pet:
        return JsonResponse({"error": "找不到出戰中的寵物"}, status=400)

    exp = LinePetExpedition.objects.filter(pet__user=user).exclude(status="CLAIMED").first()
    if not exp:
        return JsonResponse({"error": "沒有可領取的探索獎勵！"}, status=400)

    # 自動更新逾期狀態為 COMPLETED
    if exp.status == "ACTIVE" and now() >= exp.end_time:
        exp.status = "COMPLETED"
        exp.save()

    if exp.status != "COMPLETED":
        return JsonResponse({"error": "探索尚未結束，請耐心等待！"}, status=400)

    # 計算隨機獎勵
    coins_earned = 0
    won_accessory = None
    won_potion = False
    accessories_pool = list(ACCESSORY_SHOP.keys())

    if exp.duration_hours == 1:
        coins_earned = random.randint(10, 20)
        if random.random() < 0.10:
            won_accessory = random.choice(accessories_pool)
        if random.random() < 0.02:
            won_potion = True
    elif exp.duration_hours == 2:
        coins_earned = random.randint(25, 45)
        if random.random() < 0.20:
            won_accessory = random.choice(accessories_pool)
        if random.random() < 0.05:
            won_potion = True
    elif exp.duration_hours == 4:
        coins_earned = random.randint(60, 100)
        if random.random() < 0.40:
            won_accessory = random.choice(accessories_pool)
        if random.random() < 0.15:
            won_potion = True
    elif exp.duration_hours == 20:
        coins_earned = random.randint(350, 500)
        won_accessory = random.choice(accessories_pool)
        if random.random() < 0.40:
            won_potion = True

    with transaction.atomic():
        profile, _ = LinePetProfile.objects.select_for_update().get_or_create(user=user)
        profile.pet_gold_coins += coins_earned
        profile.save()

        if won_accessory:
            acc, _ = UserAccessory.objects.get_or_create(user=user, accessory_id=won_accessory)
            acc.quantity += 1
            acc.save()

        if won_potion:
            inv, _ = LinePetInventory.objects.get_or_create(user=user)
            inv.evo_potions += 1
            inv.save()

        exp.status = "CLAIMED"
        exp.save()

    acc_name = ACCESSORY_SHOP.get(won_accessory, {}).get("name", "") if won_accessory else ""

    return JsonResponse(
        {
            "status": "success",
            "message": f"探索完成！獲得金幣 x{coins_earned}"
            + (f"，飾品：{acc_name}" if won_accessory else "")
            + ("，進化藥水 x1" if won_potion else "")
            + "！",
            "coins_earned": coins_earned,
            "accessory_won": won_accessory,
            "accessory_won_display": acc_name,
            "potion_won": won_potion,
            "coins": profile.pet_gold_coins,
        }
    )


# ==========================================
# 使用道具 (例如使用奇蹟進化藥水)
# ==========================================
@csrf_exempt
def api_line_pet_use_item(request):
    """API 供用戶使用道具（如奇蹟進化藥水）"""
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        item_type = data.get("item_type")  # EVO_POTION
    except Exception:
        return JsonResponse({"error": "Invalid request body"}, status=400)

    if not access_token or not item_type:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    line_user_id, display_name = _verify_token_with_cache(access_token)
    if not line_user_id:
        return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)

    line_profile = _get_or_create_profile(line_user_id, display_name)
    user = line_profile.user

    from django.db import transaction
    from pet_system.models import LinePet, LinePetInventory

    with transaction.atomic():
        inventory, _ = LinePetInventory.objects.get_or_create(user=user)

        if item_type == "EVO_POTION":
            if inventory.evo_potions < 1:
                return JsonResponse({"error": "背包中沒有奇蹟進化藥水！"}, status=400)

            pet = LinePet.objects.filter(user=user, is_active=True).first()
            if not pet:
                return JsonResponse({"error": "目前沒有出戰寵物，請先讓出戰寵物在庭院中顯示！"}, status=400)

            if pet.stage >= 4:
                return JsonResponse({"error": "寵物已達最大進化階段，無法使用進化藥水！"}, status=400)

            inventory.evo_potions -= 1
            inventory.save()

            pet.growth_progress = min(pet.growth_progress + 20, 100)
            pet.potions_consumed += 1
            pet.save()
            msg = f"成功使用奇蹟進化藥水！目前成長進度：{pet.growth_progress}%"
        else:
            return JsonResponse({"error": "Invalid item type"}, status=400)

    return JsonResponse(
        {
            "status": "success",
            "message": msg,
            "inventory": {
                "eggs_dragon": inventory.eggs_dragon,
                "eggs_puppy": inventory.eggs_puppy,
                "evo_potions": inventory.evo_potions,
            },
        }
    )



# ==========================================
# 領取更版維護金幣 100
# ==========================================
@csrf_exempt
def api_line_pet_claim_maintenance_gift(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        access_token = data.get("access_token")
        if not access_token:
            return JsonResponse({"status": "error", "error": "Access token required"}, status=400)
        
        # 驗證用戶
        line_user_id, display_name = _verify_token_with_cache(access_token)
        if not line_user_id:
            return JsonResponse({"error": "Invalid LINE Access Token"}, status=401)
        
        line_profile = _get_or_create_profile(line_user_id, display_name)
        user = line_profile.user
        if not user:
            return JsonResponse({"status": "error", "error": "Invalid token"}, status=401)
        
        # 檢查是否已領取 (JSON 快取防重領)
        claimed_file = "claimed_maintenance_gift_users.json"
        claimed_users = []
        import os
        if os.path.exists(claimed_file):
            try:
                with open(claimed_file, 'r') as f:
                    claimed_users = json.load(f)
            except:
                pass
        
        if user.id in claimed_users:
            return JsonResponse({"status": "error", "error": "您已領取過維護禮包囉！"}, status=400)
        
        # 給予 100 金幣
        from pet_system.models import LinePetProfile
        profile, _ = LinePetProfile.objects.get_or_create(user=user)
        profile.pet_gold_coins += 100
        profile.save()
        
        # 標記為已領取
        claimed_users.append(user.id)
        with open(claimed_file, 'w') as f:
            json.dump(claimed_users, f)
            
        return JsonResponse({
            "status": "success",
            "message": "🎉 成功領取更版維護禮包！恭喜獲得 100 寵物金幣！"
        })
        
    except Exception as e:
        import traceback
        with open("django_error.log", "a", encoding="utf-8") as f:
            f.write("=== api_line_pet_claim_maintenance_gift error ===\n")
            traceback.print_exc(file=f)
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
