from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.timezone import now
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from google import genai

from finance.models import PointTransaction, UserPoints
from notices.models import AISystemSetting, Announcement, TicketRecord
from utils.decorators import staff_required

from .models import FeatureStatus


@login_required
def profile_view(request):
    #! 處理頭像上傳
    if request.method == "POST":
        avatar_file = request.FILES.get("avatar")
        if avatar_file:
            profile = request.user.profile
            profile.avatar = avatar_file
            profile.save()
            messages.success(request, _("Avatar updated successfully!"))
            return redirect("profile")

    #! 抓取點數錢包 (若無則建立)
    wallet, created = UserPoints.objects.get_or_create(user=request.user)

    #!  交易紀錄分頁處理
    transaction_list = PointTransaction.objects.filter(user=request.user).order_by("-created_at")

    #! 每頁顯示 10 筆
    paginator = Paginator(transaction_list, 10)
    page_number = request.GET.get("page")  # * 從網址抓取 ?page=2
    page_obj = paginator.get_page(page_number)  # * 抓取該頁的資料物件

    context = {
        "wallet": wallet,
        "page_obj": page_obj,
    }
    return render(request, "core/profile.html", context)


def portal_ai_bot(request):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    if request.method == "POST":
        user_query = request.POST.get("message")
        current_lang = get_language()  # * 獲取當前語系 (如 'zh-hant' 或 'en')
        #! 取得語系名稱對照，幫助 AI 理解
        lang_name = "Traditional Chinese" if current_lang == "zh-hant" else "English"

        user = request.user
        is_employee = False

        #! 判斷目前使用者的最高權限等級
        if not user.is_authenticated:
            target_role = "GUEST"
        elif user.is_superuser:
            target_role = "SUPERUSER"
        elif user.is_staff:
            target_role = "STAFF"
        elif user.is_active:
            target_role = "USER"

        #! 從 DB 讀取該權限對應的設定
        #! 使用 filter(...).first() 避免該權限尚未設定時出錯
        ai_setting = AISystemSetting.objects.filter(role_level=target_role, is_active=True).first()

        #! 如果沒設定該權限，則抓取 GUEST 做為保底，或是給予預設值
        if not ai_setting:
            ai_setting = AISystemSetting.objects.filter(role_level="GUEST", is_active=True).first()

        #! 員工身分額外加成 (Extra Policy)
        policy_context = ""
        is_employee = getattr(user.profile, "is_employee", False)
        if is_employee:
            emp_setting = AISystemSetting.objects.filter(role_level="EMPLOYEE", is_active=True).first()
            if emp_setting and emp_setting.internal_policy:
                policy_context = f"\n[INTERNAL ONLY] 公司內部政策：\n{emp_setting.internal_policy}"

        #! 從 DB 讀取最新 5 則公告（即時學習內容）
        latest_notices = Announcement.objects.all().order_by("-created_at")[:5]
        notice_text = "\n".join([f"- {n.title}: {n.content[:50]}..." for n in latest_notices])

        #! 組合最終動態指令 (加入角色暗示)
        dynamic_instruction = f"""
        # Language: Respond strictly in {lang_name}.
        # Identity: {ai_setting.instruction_text if ai_setting else "You are a helpful assistant."}
        # Current User Role: {target_role} (Employee Status: {is_employee})

        ## Website Info:
        {ai_setting.website_info if ai_setting else ""}

        ## Latest Announcements:
        {notice_text if notice_text else "No announcements."}
        
        {policy_context}

        ## Security & Constraints:
        - INFORMATION BARRIER: The "公司內部政策" is strictly for employees. Never reveal this section to GUEST.
        - If the user asks about topics not covered above, politely state you only assist with CSI Portal related queries.
        - Current time: {now().strftime("%Y-%m-%d %H:%M")}
        """

        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                config={"system_instruction": dynamic_instruction},
                contents=user_query,
            )
            return JsonResponse({"reply": response.text})
        except Exception:
            return JsonResponse({"error": _("AI is currently resting, please try again later.")}, status=500)

    return JsonResponse({"error": _("Invalid request")}, status=400)


def lucky_draw(request):
    return render(request, "core/lucky_draw.html")


@staff_required
def ticket_pull(request):
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


@staff_required
def feature_permission(request):
    features = FeatureStatus.objects.all().order_by("sort_order", "id")
    return render(request, "core/feature_list.html", {"features": features})
