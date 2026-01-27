from .models import ExternalTool


def external_tools_processor(request):
    #! 抓取所有啟用的工具並傳給所有模板
    return {"external_tools": ExternalTool.objects.filter(is_active=True)}
