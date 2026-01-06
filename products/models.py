from django.db import models
from django.contrib.auth.models import User


# 1. 商品分类表
class Category(models.Model):
    name = models.CharField(max_length=50, verbose_name="分类名称")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "商品分类"
        verbose_name_plural = verbose_name


# 2. 商品表
class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="所属分类")
    name = models.CharField(max_length=100, verbose_name="商品名称")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="价格")
    # upload_to会自动把图片存到 media/products/ 目录下
    image = models.ImageField(upload_to='products/', verbose_name="商品主图")
    description = models.TextField(verbose_name="商品描述")
    # 风格标签，用于冷启动推荐 (如: 复古, 运动, 极简)
    tags = models.CharField(max_length=200, blank=True, verbose_name="风格标签")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上架时间")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "商品信息"
        verbose_name_plural = verbose_name


# 3. 用户行为记录表 (核心！协同过滤算法的数据源)
class UserBehavior(models.Model):
    ACTION_CHOICES = (
        (1, '浏览'),
        (2, '收藏'),
        (3, '加入购物车'),
        (4, '购买'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="商品")
    action_type = models.IntegerField(choices=ACTION_CHOICES, verbose_name="行为类型")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="发生时间")

    # 这是一个属性方法，把行为转换成“评分权重”
    # 比如：买了(5分) > 加购(4分) > 收藏(3分) > 浏览(1分)
    @property
    def score(self):
        scores = {1: 1, 2: 3, 3: 4, 4: 5}
        return scores.get(self.action_type, 1)

    class Meta:
        verbose_name = "用户行为记录"
        verbose_name_plural = verbose_name