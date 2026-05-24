import openpyxl
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import admin
from django.db.models import Sum, F, FloatField
from .models import Category, Product, ProductImage, ProductDetailImage, ProductSKU, UserBehavior, Address, Order, OrderItem, CartItem, ProductReview, Message
# 1. 注册分类
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


# 2. 商品副图内联
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
# 新增一个详情图的内联配置
class ProductDetailImageInline(admin.TabularInline):
    model = ProductDetailImage
    extra = 2  # 默认提供2个空白上传框

# 1. 新增 SKU 的内联配置
class ProductSKUInline(admin.TabularInline):
    model = ProductSKU
    extra = 0  # 不默认添加空行，用我们下面的动作一键生成

# 3. 注册商品
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # 告诉 Django 后台要展示哪些列
    list_display = ['name', 'category', 'price', 'stock','get_total_sales', 'get_total_revenue', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['stock', 'price']    # 允许在列表页直接编辑库存和价格

    inlines = [ProductImageInline, ProductDetailImageInline, ProductSKUInline]

    actions = ['generate_skus', 'export_sku_summary_excel']

    @admin.action(description='⚡ 根据颜色和尺码自动生成SKU规格')
    def generate_skus(self, request, queryset):
        for product in queryset:
            # 提取颜色和尺码
            colors = [c.strip() for c in product.available_colors.split(',')] if product.available_colors else []
            sizes = [s.strip() for s in product.available_sizes.split(',')] if product.available_sizes else []

            for c in colors:
                for s in sizes:
                    # 如果该组合不存在，则创建，默认库存为 0
                    ProductSKU.objects.get_or_create(product=product, color=c, size=s)

        self.message_user(request, "✅ SKU 规格已成功生成，请进入商品编辑页下方分配具体库存数量！")

    # +++ 本次新增：导出 Excel 核心逻辑 +++
    @admin.action(description='📊 导出选中商品的 SKU 销售统计 (Excel)')
    def export_sku_summary_excel(self, request, queryset):
        # 1. 创建 Excel 工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "SKU销售统计"

        # 2. 写入表头
        ws.append(['商品ID', '商品名称', '颜色', '尺码', '累计销量(件)', '剩余库存(件)', '累计销售额(元)'])

        # 3. 遍历选中的商品
        for product in queryset:
            # 获取该商品所有的 SKU
            for sku in product.skus.all():
                # 查询该 SKU 在有效订单（已付款、已发货、已完成）中的销售记录
                valid_items = OrderItem.objects.filter(
                    product=product,
                    selected_color=sku.color,
                    selected_size=sku.size,
                    order__status__in=[2, 3, 4]
                )

                # 聚合计算：总销量 和 总销售额
                aggregated = valid_items.aggregate(
                    total_qty=Sum('quantity'),
                    total_rev=Sum(F('price') * F('quantity'), output_field=FloatField())
                )

                sold_count = aggregated['total_qty'] or 0
                revenue = aggregated['total_rev'] or 0.0

                # 将数据追加到 Excel 中
                ws.append([
                    product.id,
                    product.name,
                    sku.color,
                    sku.size,
                    sold_count,
                    sku.stock,
                    round(revenue, 2)  # 保留两位小数
                ])

        # 4. 生成响应返回文件，触发浏览器下载
        filename = f"SKU_Sales_Summary_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)

        return response

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