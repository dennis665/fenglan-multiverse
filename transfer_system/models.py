from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField, transition

User = get_user_model()


class Item(models.Model):
    """物品資料表"""

    name = models.CharField(max_length=255, verbose_name=_("物品名稱"))
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="owned_items", verbose_name=_("擁有者")
    )
    description = models.TextField(blank=True, verbose_name=_("物品描述"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("建立時間"))

    class Meta:
        verbose_name = _("物品")
        verbose_name_plural = _("物品")

    def __str__(self):
        return self.name


class TransferRecord(models.Model):
    """轉移紀錄資料表"""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, verbose_name=_("轉移物品"))
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transfers_sent", verbose_name=_("轉出者")
    )
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="transfers_received", verbose_name=_("接收者")
    )
    status = FSMField(
        default="pending",
        protected=True,  # * 禁止非狀態機方法直接修改此欄位
        verbose_name=_("狀態"),
    )  # pyright: ignore[reportCallIssue]
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("發起時間"))

    class Meta:
        verbose_name = _("轉移紀錄")
        verbose_name_plural = _("轉移紀錄")

    def __str__(self):
        return f"{self.item.name} - {self.status}"

    @transition(field=status, source="pending", target="accepted")
    def accept(self):
        """接受轉移：推進狀態並連動更新物品擁有者"""
        self.item.owner = self.receiver
        self.item.save()

    @transition(field=status, source="pending", target="rejected")
    def reject(self):
        """拒絕轉移：僅變更工作流狀態"""
        pass

    @transition(field=status, source="pending", target="cancelled")
    def cancel(self):
        """管理員取消：僅變更工作流狀態"""
        pass
