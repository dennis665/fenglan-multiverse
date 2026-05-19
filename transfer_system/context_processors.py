from .models import TransferRecord


def pending_transfers(request):
    """取得當前使用者尚未處理的轉移請求"""
    if request.user.is_authenticated:
        pending_records = TransferRecord.objects.filter(receiver=request.user, status="pending")
        return {"pending_transfers": pending_records}
    return {}
