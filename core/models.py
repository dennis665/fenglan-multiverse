from django.db import models


class BaseModel(models.Model):
    """所有模型通用的基礎欄位"""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        abstract = True  #! 代表這是一個抽象類別，不會在資料庫產生表格
