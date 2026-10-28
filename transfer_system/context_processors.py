from .models import TransferRecord


def pending_transfers(request):
    """取得當前使用者尚未處理的轉移請求"""
    if request.user.is_authenticated:
        #! 一併帶出樣板會用到的 sender / item，避免額外的延遲查詢
        pending_records = TransferRecord.objects.filter(receiver=request.user, status="pending").select_related(
            "sender", "item"
        )
        return {"pending_transfers": pending_records}
    return {}
