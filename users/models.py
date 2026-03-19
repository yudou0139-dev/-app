from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    # 与内置的 User 表一对一关联
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="关联用户")

    # 核心权益标识
    is_vip = models.BooleanField(default=False, verbose_name="是否为VIP会员")

    # 用户偏好数据 (用于算法冷启动)
    height = models.IntegerField(null=True, blank=True, verbose_name="身高(cm)")
    weight = models.IntegerField(null=True, blank=True, verbose_name="体重(kg)")

    STYLE_CHOICES = (
        ('minimalist', '极简风'),
        ('sports', '运动风'),
        ('business', '商务风'),
        ('street', '街头风'),
    )
    style_preference = models.CharField(max_length=20, choices=STYLE_CHOICES, null=True, blank=True,
                                        verbose_name="风格偏好")

    def __str__(self):
        return f"{self.user.username} 的资料"

    class Meta:
        verbose_name = "用户详细资料"
        verbose_name_plural = verbose_name