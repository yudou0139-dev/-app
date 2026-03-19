from django.contrib import admin
from .models import UserProfile

# 把用户详细资料表注册到后台
admin.site.register(UserProfile)