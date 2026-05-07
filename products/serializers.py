from rest_framework import serializers
from .models import Product, ProductImage, Category, Address, Order, OrderItem, CartItem, ProductReview, Message


# +++ 1. 新增：商品副图序列化器 +++
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'color_mark'] # 把图片地址和颜色标签暴露给前端

# 2. 修改：原来的商品序列化器
class ProductSerializer(serializers.ModelSerializer):
    # +++ 核心修改：把副图列表嵌套进来，many=True 代表这是一个数组 +++
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        # +++ 确保 available_colors, available_sizes 和 images 都加到了 fields 列表里 +++
        fields = [
            'id', 'name', 'price', 'image', 'description', 'tags',
            'available_colors', 'available_sizes', 'images'
        ]

# 新增分类序列化器
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

# 1. 地址序列化器
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'

# 2. 订单明细序列化器
class OrderItemSerializer(serializers.ModelSerializer):
    # 额外把商品的名字和图片带出去，方便前端列表展示
    product_name = serializers.ReadOnlyField(source='product.name')
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_image', 'price', 'quantity', 'selected_color', 'selected_size']

    def get_product_image(self, obj):
        if obj.product.image:
            # 拼接完整的图片URL前缀 (注意：这里的拼接方式在实际部署时可能要配合 request.build_absolute_uri)
            return obj.product.image.url
        return ''

# 3. 订单主表序列化器
class OrderSerializer(serializers.ModelSerializer):
    # 将订单明细嵌套进主订单中
    items = OrderItemSerializer(many=True, read_only=True)
    # 将地址详情嵌套进订单中
    address_detail = AddressSerializer(source='address', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_sn', 'total_amount', 'status', 'created_at', 'address_detail', 'items']

class CartItemSerializer(serializers.ModelSerializer):
    # 额外把商品的名字、实时价格和图片带出去，方便前端列表展示
    product_name = serializers.ReadOnlyField(source='product.name')
    price = serializers.ReadOnlyField(source='product.price') # 实时读取最新价格
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_name', 'product_image', 'price', 'quantity', 'selected_color', 'selected_size', 'is_checked']

    def get_product_image(self, obj):
        if obj.product.image:
            return obj.product.image.url
        return ''

class ProductReviewSerializer(serializers.ModelSerializer):
    # 把用户的名字带出去，如果想保护隐私，可以在这里做字符串截取，比如 "张**"
    username = serializers.ReadOnlyField(source='user.username')
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = ['id', 'username', 'rating', 'content', 'image_url', 'created_at']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return ''

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'