from django.contrib import admin
from .models import Category, Product, UserBehavior

# 把这三个表注册到后台
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(UserBehavior)