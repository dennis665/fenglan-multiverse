from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("notices"):
    from django.views.generic import DetailView, ListView

    from .models import Announcement


class NoticeListView(ListView):
    model = Announcement
    template_name = "notices/list.html"  # * 記得建立這個 HTML 檔案
    context_object_name = "notices"
    paginate_by = 10

    def get_queryset(self):
        #! 僅顯示啟用中的公告
        return Announcement.objects.filter(is_active=True)


class NoticeDetailView(DetailView):
    model = Announcement
    template_name = "notices/detail.html"
