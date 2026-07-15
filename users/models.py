import os

from allauth.account.signals import email_confirmed
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps

from utils.logger_utils import jinfo


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile", verbose_name=_("使用者"))
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, verbose_name=_("自定義大頭貼"))
    is_employee = models.BooleanField(default=False, verbose_name=_("是否為公司人員"))
    employee_id = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("工號"))

    def __str__(self):
        # * 將單位文字也套用翻譯
        return f"{self.user.username} {_('的個人檔案')}"

    class Meta:
        verbose_name = _("個人檔案")
        verbose_name_plural = _("個人檔案")

    def save(self, *args, **kwargs):
        #! 先執行 Django 原本的儲存動作，確保檔案已經寫入硬碟
        super().save(*args, **kwargs)

        #! 檢查是否有上傳圖片，並且檔案路徑存在
        if self.avatar and os.path.exists(self.avatar.path):
            img_path = self.avatar.path

            try:
                #! 打開圖片
                with Image.open(img_path) as img:
                    #! 設定目標尺寸 (例如 300x300，足夠視網膜螢幕顯示)
                    target_size = (300, 300)

                    #! 如果圖片比目標尺寸大，才需要處理
                    if img.height > target_size[1] or img.width > target_size[0]:
                        #! 智慧裁切與縮放
                        processed_img = ImageOps.fit(
                            img,
                            target_size,
                            method=Image.Resampling.LANCZOS,  # * 使用高品質縮放演算法
                            centering=(0.5, 0.5),  # * 確保對準中心點裁切
                        )

                        #! 如果圖片有旋轉資訊（手機拍攝常見），強制校正轉正
                        processed_img = ImageOps.exif_transpose(processed_img)

                        #! 存回原路徑，覆蓋掉原本的大圖
                        processed_img.save(img_path, optimize=True, quality=85)

            except Exception as e:
                print(f"Error resizing image {img_path}: {e}")


#! 自動化建立 Profile 的信號
@receiver(post_save, sender=User)
def create_user_profile(sender, instance: User, created, **kwargs):
    if created:
        company_domain = settings.CSI_EMAIL
        is_company_staff = False
        if instance.email and instance.email.endswith(company_domain):
            is_company_staff = True
        Profile.objects.create(user=instance, is_employee=is_company_staff)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    #! 加入 hasattr 檢查以增加強健性
    if hasattr(instance, "profile"):
        instance.profile.save()


@receiver(email_confirmed)
def promote_to_employee(request, email_address, **kwargs):
    """
    當 Email 驗證成功後，檢查網域並提升權限
    """
    user = email_address.user
    company_domain = settings.CSI_EMAIL

    if user.email.endswith(company_domain):
        #! 取得該使用者的 Profile 並更新
        if hasattr(user, "profile"):
            profile: Profile = user.profile
            profile.is_employee = True
            profile.save()
            jinfo(f"使用者 {user.username} 已通過 Email 驗證，提升為公司員工。")
