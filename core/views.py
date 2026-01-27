from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def profile_view(request):
    #! 因為使用了 socialaccount，我們可以在模板中拿到 Google 的資料
    return render(request, "core/profile.html")
