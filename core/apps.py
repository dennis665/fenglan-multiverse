from django.apps import AppConfig, apps
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    name = 'core'
    verbose_name = _("核心系統")

    def ready(self):
        """
        當 Django 啟動且所有 App 都載入完成後，會自動執行此函式。
        我們在這裡動態修改第三方套件的顯示名稱！
        """
        try:
            #! 攔截 django-apscheduler 的 AppConfig 並套用翻譯
            apscheduler_app = apps.get_app_config("django_apscheduler")
            apscheduler_app.verbose_name = _("排程任務管理")

            #! 攔截裡面的 DjangoJob 資料表名稱
            job_model = apscheduler_app.get_model("DjangoJob")
            job_model._meta.verbose_name = _("背景任務")
            job_model._meta.verbose_name_plural = _("背景任務")

            #! 修改 DjangoJob 的欄位名稱
            job_id_field = job_model._meta.get_field("id")
            job_id_field.verbose_name = _("任務 ID")
            job_id_field.help_text = _("此任務的唯一識別碼。")

            job_next_run_field = job_model._meta.get_field("next_run_time")
            job_next_run_field.verbose_name = _("下次執行時間")
            job_next_run_field.help_text = _("排定下次執行此任務的日期與時間。")

            job_state_field = job_model._meta.get_field("job_state")
            job_state_field.verbose_name = _("任務狀態 (二進位)")

            #! 攔截裡面的 DjangoJobExecution 資料表名稱
            execution_model = apscheduler_app.get_model("DjangoJobExecution")
            execution_model._meta.verbose_name = _("執行紀錄")
            execution_model._meta.verbose_name_plural = _("執行紀錄")

            #! 修改 DjangoJobExecution 的欄位名稱
            exec_id_field = execution_model._meta.get_field("id")
            exec_id_field.verbose_name = _("紀錄 ID")
            exec_id_field.help_text = _("此任務執行紀錄的唯一 ID。")

            exec_job_field = execution_model._meta.get_field("job")
            exec_job_field.verbose_name = _("所屬任務")
            exec_job_field.help_text = _("此執行紀錄關聯的排程任務。")

            exec_status_field = execution_model._meta.get_field("status")
            exec_status_field.verbose_name = _("執行狀態")
            exec_status_field.help_text = _("此任務執行的當前狀態。")

            exec_run_time_field = execution_model._meta.get_field("run_time")
            exec_run_time_field.verbose_name = _("執行時間")
            exec_run_time_field.help_text = _("此任務開始執行的日期與時間。")

            exec_duration_field = execution_model._meta.get_field("duration")
            exec_duration_field.verbose_name = _("耗時 (秒)")
            exec_duration_field.help_text = _("此任務的總執行時間 (以秒為單位)。")

            exec_finished_field = execution_model._meta.get_field("finished")
            exec_finished_field.verbose_name = _("完成時間戳")
            exec_finished_field.help_text = _("此任務完成時的時間戳記。")

            exec_exception_field = execution_model._meta.get_field("exception")
            exec_exception_field.verbose_name = _("異常訊息")
            exec_exception_field.help_text = _("任務執行期間發生的異常詳細資訊 (若有的話)。")

            exec_traceback_field = execution_model._meta.get_field("traceback")
            exec_traceback_field.verbose_name = _("錯誤追蹤")
            exec_traceback_field.help_text = _("任務執行期間發生異常的追蹤紀錄 (若有的話)。")
        #! 如果系統還沒安裝此套件，就略過避免報錯
        except LookupError:
            pass