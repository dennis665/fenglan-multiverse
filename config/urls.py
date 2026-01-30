"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.views.static import serve

from core.views import lucky_draw, portal_ai_bot, profile_view, ticket_pull

urlpatterns = [
    # ? =================================頁面=================================
    #! 首頁
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    #! 後台
    path("admin/", admin.site.urls),
    #! 帳號個人檔案跳轉
    path("accounts/", lambda request: redirect("profile", permanent=False)),
    path("accounts/", include("allauth.urls")),
    #! 個人檔案
    path("accounts/profile/", profile_view, name="profile"),
    #! 公告消息
    path("notices/", include("notices.urls")),
    #! 幸運抽獎
    path("lucky-draw/", lucky_draw, name="lucky_draw"),
    #! 發文簿系統
    path("ticket-pull/", ticket_pull, name="ticket_pull"),
    # ? ======================================================================
    #! ICON
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "images/favicon.ico")),
    # ? =================================API==================================
    #! 智能客服
    path("ai-chat/", portal_ai_bot, name="portal_ai_bot"),
    # ? ======================================================================
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif not settings.DEBUG:
    urlpatterns += [
        #! 手動強制開啟媒體檔案路徑，不論 DEBUG 狀態為何
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
        #! 如果連 CSS/JS 都不見了，也補上這一行
        re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    ]