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

    # 主图（用于列表页显示，也就是第一张图）
    image = models.ImageField(upload_to='products/', verbose_name="商品主图")
    description = models.TextField(verbose_name="商品描述")

    # 风格标签，用于冷启动推荐 (如: 复古, 运动, 极简)
    tags = models.CharField(max_length=200, blank=True, verbose_name="风格标签")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上架时间")

    stock = models.IntegerField(default=100, verbose_name="库存")
    # +++ 【本次新增】商品规格信息 +++
    # 前端就是读取这里的数据来生成那些带有红框的选中按钮的
    available_colors = models.CharField(max_length=255, blank=True, null=True,
                                        help_text="用逗号分隔，例如：淡雾紫,海军蓝,暗夜黑", verbose_name="可选颜色")
    available_sizes = models.CharField(max_length=255, blank=True, null=True, help_text="用逗号分隔，例如：S,M,L,XL",
                                       verbose_name="可选尺码")

    def __str__(self):
        return self.name

    # 动汇总 SKU 库存到总库存 +++
    def save(self, *args, **kwargs):
        # 如果商品已经存在于数据库中（有主键 pk）
        if self.pk:
            from django.db.models import Sum
            # 汇总所有关联 SKU 的库存总和
            total = self.skus.aggregate(Sum('stock'))['stock__sum']
            # 如果算出来有值就更新，没有就算作 0
            self.stock = total if total is not None else 0
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "商品信息"
        verbose_name_plural = verbose_name

class ProductSKU(models.Model):
    """商品规格库存表 (SKU)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='skus', verbose_name="所属商品")
    color = models.CharField(max_length=50, verbose_name="颜色")
    size = models.CharField(max_length=50, verbose_name="尺码")
    stock = models.IntegerField(default=0, verbose_name="库存数量")

    class Meta:
        verbose_name = "规格库存"
        verbose_name_plural = verbose_name
        # 确保同一个商品下，“颜色+尺码”的组合是唯一的
        unique_together = ('product', 'color', 'size')

    def __str__(self):
        return f"{self.product.name} - {self.color} / {self.size} (库存: {self.stock})"


# +++ 【本次新增】3. 商品副图表（实现一对多关联的核心）+++
class ProductImage(models.Model):
    # 外键关联到商品表，related_name='images' 非常重要，它让前端可以通过 product.images 拿到所有图
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE, verbose_name="所属商品")
    # 副图文件
    image = models.ImageField(upload_to='products/detail/', verbose_name="副图")
    # 颜色标记：如果填了“淡雾紫”，前端点淡雾紫就会跳到这张图；如果不填，就作为通用的细节图展示
    color_mark = models.CharField(max_length=50, blank=True, null=True, verbose_name="对应颜色标签",
                                  help_text="留空则为通用细节图")

    def __str__(self):
        return f"{self.product.name} 的副图"

    class Meta:
        verbose_name = "商品副图"
        verbose_name_plural = verbose_name

class ProductDetailImage(models.Model):
    """商品详情图 (专用于详情页底部的长图展示)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='detail_images', verbose_name="所属商品")
    image = models.ImageField(upload_to='products/details/', verbose_name="详情图片")
    order = models.IntegerField(default=0, verbose_name="展示顺序(从小到大)")

    class Meta:
        verbose_name = "商品详情图"
        verbose_name_plural = verbose_name
        ordering = ['order']  # 按照 order 字段从小到大排序，保证长图拼接顺序正确

    def __str__(self):
        return f"{self.product.name} - 详情图"


# 4. 用户行为记录表 (核心！协同过滤算法的数据源)
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

    @property
    def score(self):
        scores = {1: 1, 2: 3, 3: 4, 4: 5}
        return scores.get(self.action_type, 1)

    class Meta:
        verbose_name = "用户行为记录"
        verbose_name_plural = verbose_name


# 5. 收货地址表
class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    receiver_name = models.CharField(max_length=50, verbose_name="收件人姓名")
    phone_number = models.CharField(max_length=20, verbose_name="手机号")
    province = models.CharField(max_length=50, verbose_name="省份")
    city = models.CharField(max_length=50, verbose_name="城市")
    district = models.CharField(max_length=50, verbose_name="区县")
    detail_address = models.CharField(max_length=200, verbose_name="详细地址")
    is_default = models.BooleanField(default=False, verbose_name="是否默认地址")

    class Meta:
        verbose_name = "收货地址"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.receiver_name} - {self.phone_number}"

# 6. 订单主表 (记录订单的总体状态和金额)
class Order(models.Model):
    STATUS_CHOICES = (
        (1, '待支付'),
        (2, '待发货'),
        (3, '已发货'),
        (4, '已完成'),
        (5, '已取消'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    # 注意这里的 on_delete=models.SET_NULL
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, verbose_name="收货地址")
    order_sn = models.CharField(max_length=50, unique=True, verbose_name="订单编号")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="订单总金额")
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name="订单状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "订单信息"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.order_sn

# 7. 订单明细表 (记录这个订单里具体买了哪几件衣服、颜色和尺码)
class OrderItem(models.Model):
    # related_name='items' 方便以后通过 order.items 拿到所有商品
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name="所属订单")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="商品")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="购买时单价")
    quantity = models.IntegerField(default=1, verbose_name="购买数量")
    selected_color = models.CharField(max_length=50, blank=True, null=True, verbose_name="选中颜色")
    selected_size = models.CharField(max_length=50, blank=True, null=True, verbose_name="选中尺码")

    class Meta:
        verbose_name = "订单明细"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.order.order_sn} - {self.product.name}"

# 8. 购物车明细表
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="商品")
    quantity = models.IntegerField(default=1, verbose_name="数量")
    selected_color = models.CharField(max_length=50, blank=True, null=True, verbose_name="选中颜色")
    selected_size = models.CharField(max_length=50, blank=True, null=True, verbose_name="选中尺码")
    # 核心字段：记录用户在购物车里有没有打钩选中这件商品
    is_checked = models.BooleanField(default=True, verbose_name="是否勾选")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="加入时间")

    class Meta:
        verbose_name = "购物车明细"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username}的购物车 - {self.product.name}"


# ==========================================
# 9. 商品评价/买家秀表
# ==========================================
class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="商品")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    # 关联到具体的订单明细，防止用户没买过就乱评，或者重复评价
    order_item = models.ForeignKey(OrderItem, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="订单明细")

    rating = models.IntegerField(default=5, verbose_name="星级评分")
    content = models.TextField(verbose_name="评价内容")
    # 买家秀图片，允许为空（用户可以只写字不传图）
    image = models.ImageField(upload_to='reviews/', blank=True, null=True, verbose_name="买家秀图片")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评价时间")

    class Meta:
        verbose_name = "商品评价"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} 评价了 {self.product.name} ({self.rating}星)"


# ==========================================
# +++ 新增：客服消息表 +++
# ==========================================
class Message(models.Model):
    # 无论谁发，这条消息都归属于这个特定用户（类似于一个专属聊天室）
    user_id = models.IntegerField(help_text="关联的用户ID")

    # 标识是谁发出的：'user' 代表用户发的，'admin' 代表管理员回复的
    sender_type = models.CharField(max_length=10, choices=[('user', '用户'), ('admin', '客服')])

    content = models.TextField(help_text="消息内容")
    is_read = models.BooleanField(default=False, help_text="是否已读")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'