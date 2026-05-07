from django.contrib import admin
from .models import Category, Product, ProductImage, UserBehavior, Address, Order, OrderItem, CartItem,ProductReview, Message
from django.db.models import Sum, F, FloatField

# 1. 注册分类
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


# 2. 商品副图内联
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3


# 3. 注册商品
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # 告诉 Django 后台要展示哪些列
    list_display = ['name', 'category', 'price', 'get_total_sales', 'get_total_revenue', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'description']
    inlines = [ProductImageInline]

    def get_total_sales(self, obj):
        """动态计算：累计销量 (只计算已付款及之后的订单)"""
        # status__in=[2, 3, 4] 代表：待发货、已发货、已完成 (排除了待支付和已取消)
        valid_items = OrderItem.objects.filter(
            product=obj,
            order__status__in=[2, 3, 4]
        )
        # 把这些有效订单里的 quantity (购买数量) 全部加起来
        total = valid_items.aggregate(total_qty=Sum('quantity'))['total_qty']
        return total if total else 0

    # 给这一列起个漂亮的中文列名
    get_total_sales.short_description = '📈 累计销量 (件)'

    def get_total_revenue(self, obj):
        """动态计算：总销售额 (售价 × 数量)"""
        valid_items = OrderItem.objects.filter(
            product=obj,
            order__status__in=[2, 3, 4]
        )
        # 考虑到商品可能会调价，我们必须用用户当时购买的价格 (item.price) 乘以 数量
        total = valid_items.aggregate(
            revenue=Sum(F('price') * F('quantity'), output_field=FloatField())
        )['revenue']

        return f"￥{total:.2f}" if total else "￥0.00"

    get_total_revenue.short_description = '💰 总销售额'


# 4. 注册行为记录
@admin.register(UserBehavior)
class UserBehaviorAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'action_type', 'timestamp']
    list_filter = ['action_type']


# ==========================================
# +++ 下面是本次新增的订单系统后台配置 +++
# ==========================================

# 5. 注册收货地址
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    # 列表页展示的字段
    list_display = ['user', 'receiver_name', 'phone_number', 'province', 'city', 'is_default']
    # 右侧的过滤侧边栏
    list_filter = ['is_default', 'province']
    # 顶部的搜索框（可以按姓名和手机号搜索）
    search_fields = ['receiver_name', 'phone_number']


# 6. 订单明细内联（挂载到订单主表里）
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # 订单明细通常是用户买多少生成多少，后台不需要默认多出空白行


# 7. 注册订单信息
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_sn', 'user', 'total_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_sn', 'user__username']

    # 核心：把订单明细嵌进来
    inlines = [OrderItemInline]

    # 保护机制：订单号和创建时间是系统生成的，后台人员不应该随意修改
    readonly_fields = ['order_sn', 'created_at']

# 8. 注册购物车
@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'quantity', 'selected_color', 'selected_size', 'is_checked', 'created_at']
    list_filter = ['is_checked', 'created_at']

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'content', 'created_at']
    list_filter = ['rating', 'created_at']

# +++ 本次新增：把客服消息表注册到后台 +++
admin.site.register(Message)