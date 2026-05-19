from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from .models import Item, TransferRecord

User = get_user_model()


@login_required
def transfer_create(request):
    """供 Admin 使用的物品轉移發起頁面"""
    if not request.user.is_staff:
        messages.error(request, _("僅限管理員操作"))
        return redirect("/")

    if request.method == "POST":
        item_id = request.POST.get("item_id")
        receiver_id = request.POST.get("receiver_id")

        item = get_object_or_404(Item, id=item_id)
        receiver = get_object_or_404(User, id=receiver_id)

        #! 檢查機制：同一件物品不能同時轉給2人 (不能有重複的 pending 紀錄)
        has_pending = TransferRecord.objects.filter(item=item, status="pending").exists()

        if has_pending:
            messages.error(request, _("該物品目前已有進行中的轉移請求，無法同時發起第二筆轉移。"))
            return redirect("transfer_create")

        TransferRecord.objects.create(item=item, sender=request.user, receiver=receiver)
        messages.success(request, _("轉移請求已建立"))
        return redirect("transfer_history")

    #! 找出所有目前正處於待處理狀態的轉移紀錄物品 ID
    pending_item_ids = TransferRecord.objects.filter(status="pending").values_list(
        "item_id", flat=True
    )

    #! 查詢物品時，直接排除上述已被鎖定的待處理物品
    items = Item.objects.exclude(id__in=pending_item_ids)

    users = User.objects.all()
    return render(request, "transfer_system/transfer_create.html", {"items": items, "users": users})


@login_required
def transfer_history(request):
    """管理員專屬：檢視各物品歷史轉移紀錄清單"""
    if not request.user.is_staff:
        messages.error(request, _("僅限管理員操作"))
        return redirect("/")

    #! 撈取全系統所有的轉移歷史，依發起時間反向排序
    all_records = TransferRecord.objects.all().order_by("-created_at")

    #! 每頁顯示 15 筆紀錄
    paginator = Paginator(all_records, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "transfer_system/transfer_history.html", {"page_obj": page_obj})


@login_required
def transfer_cancel(request, record_id):
    """管理員專屬：取消待處理(pending)的轉移"""
    if not request.user.is_staff:
        messages.error(request, _("僅限管理員操作"))
        return redirect("/")

    if request.method == "POST":
        record = get_object_or_404(TransferRecord, id=record_id, status="pending")
        record.status = "cancelled"
        record.save()
        messages.success(request, _("已成功取消該筆轉移請求"))

    return redirect("transfer_history")


@login_required
def transfer_reply(request, record_id):
    """被轉移者處理轉移請求 (接受或拒絕)"""
    record = get_object_or_404(
        TransferRecord, id=record_id, receiver=request.user, status="pending"
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accept":
            #! 更新紀錄狀態與物品所屬擁有者
            record.status = "accepted"
            record.item.owner = request.user
            record.item.save()
            record.save()
            messages.success(request, _("已接受物品轉移"))
        elif action == "reject":
            record.status = "rejected"
            record.save()
            messages.success(request, _("已拒絕物品轉移"))
        return redirect("/")

    return render(request, "transfer_system/transfer_reply.html", {"record": record})
