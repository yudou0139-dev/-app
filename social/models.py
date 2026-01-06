from django.db import models
from django.contrib.auth.models import User
from products.models import Product

class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="作者")
    content = models.TextField(verbose_name="帖子内容")
    image = models.ImageField(upload_to='social_posts/', verbose_name="穿搭图片")
    # 关联商品 (关键点：社交电商的闭环，用户发帖可以关联一个商品)
    related_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联商品")
    likes = models.IntegerField(default=0, verbose_name="点赞数")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")

    def __str__(self):
        return f"{self.author.username}: {self.content[:20]}"

    class Meta:
        verbose_name = "穿搭帖子"
        verbose_name_plural = verbose_name