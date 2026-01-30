from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


#! 權限檢查：必須是登入狀態且具備工作人員 (is_staff) 以上權限
def staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        #! 核心權限邏輯
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
            messages.warning(request, "您不具備權限，已自動導回首頁。")
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
