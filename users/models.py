import os

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from PIL import Image, ImageOps


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, verbose_name="自定義大頭貼")

    def __str__(self):
        return f"{self.user.username} 的個人檔案"

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
                        #! ImageOps.fit 會保持比例，從中心裁切出一個正方形，然後縮放到指定大小
                        #! 這是製作大頭貼最完美的方法
                        processed_img = ImageOps.fit(
                            img,
                            target_size,
                            method=Image.Resampling.LANCZOS,  # * 使用高品質縮放演算法
                            centering=(0.5, 0.5),  # * 確保對準中心點裁切
                        )

                        #! 如果圖片有旋轉資訊（手機拍攝常見），強制校正轉正
                        processed_img = ImageOps.exif_transpose(processed_img)

                        #! 存回原路徑，覆蓋掉原本的大圖
                        #! optimize=True 幫你壓縮檔案大小，quality=85 保持良好畫質
                        processed_img.save(img_path, optimize=True, quality=85)

            except Exception as e:
                print(f"Error resizing image {img_path}: {e}")


#! 自動化建立 Profile 的信號
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
