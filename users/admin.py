from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


#! 定義一個內聯類別
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Profile Info"

#! 重新定義 UserAdmin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

#! 重新註冊 User 模型
admin.site.unregister(User)
admin.site.register(User, UserAdmin)