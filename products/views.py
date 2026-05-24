from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import Product, UserBehavior, Category, Address, Order, OrderItem, CartItem,ProductReview, Message
from .serializers import ProductSerializer, CategorySerializer, AddressSerializer, OrderSerializer, CartItemSerializer,ProductReviewSerializer, MessageSerializer,ProductSKU
from recommend.algo import item_based_recommendation, get_related_products
from django.db import transaction
import datetime
import random
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q,F

# +++ 接口0 获取所有商品分类 +++
class CategoryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


# 接口1：获取所有商品列表 (+++ 本次修改：增加了 category_id 筛选逻辑 +++)
class ProductListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        keyword = request.query_params.get('keyword', '')
        category_id = request.query_params.get('category_id')
        # +++ 1. 新增：接收指定的商品 ID +++
        product_id = request.query_params.get('id')

        products = Product.objects.all()

        # +++ 2. 核心逻辑：如果传了 id，优先按 id 查（即探路查询）+++
        if product_id:
            products = products.filter(id=product_id)
        # 如果没有传 id，再走搜索或分类筛选的逻辑
        elif keyword:
            products = products.filter(
                Q(name__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(category__name__icontains=keyword)
            )
        elif category_id:
            products = products.filter(category_id=category_id)

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


# 接口2：猜你喜欢 (核心接口)
class RecommendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        user_id = request.query_params.get('user_id')
        preference = request.query_params.get('preference', '')

        # +++ 增加后端终端的打印调试，让一切黑盒操作现原形 +++
        print("\n========== AI 推荐接口被调用 ==========")
        print(f"1. 收到前端用户ID: {user_id}")
        print(f"2. 收到前端偏好词: '{preference}'")

        PREF_MAP = {
            'minimalist': '极简',
            'sports': '运动',
            'business': '商务',
            'street': '街头'
        }
        pref_keyword = PREF_MAP.get(preference, preference)
        print(f"3. 翻译后的搜索词: '{pref_keyword}'")

        products = None
        if user_id:
            products = item_based_recommendation(user_id, pref_keyword)

        if not products:
            if pref_keyword:
                # ==========================================
                # +++ 核心升级：扩大搜索范围！名字、描述、标签只要有“商务”就算命中 +++
                # ==========================================
                products = Product.objects.filter(
                    Q(tags__icontains=pref_keyword) |
                    Q(name__icontains=pref_keyword) |
                    Q(description__icontains=pref_keyword)
                ).order_by('-created_at')[:6]
                print(f"4. 冷启动兜底 - 查到匹配商品数: {len(products)}")

            if not products:
                products = Product.objects.all().order_by('-created_at')[:6]
                print("5. 偏好未匹配到商品，执行最终默认兜底")

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

# 接口3：记录用户行为 (给推荐算法喂数据) —— 【保持原样不动】
class UserBehaviorView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user_id = request.data.get('user_id')
        product_id = request.data.get('product_id')
        action_type = request.data.get('action_type')  # 1浏览 2收藏 3加购 4购买

        if not all([user_id, product_id, action_type]):
            return Response({'error': '参数不完整'}, status=400)

        UserBehavior.objects.create(
            user_id=user_id,
            product_id=product_id,
            action_type=action_type
        )
        return Response({'message': '行为记录成功'})


class FavoriteListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # 同样免除 CSRF 检查

    def get(self, request):
        """获取我的收藏列表"""
        user_id = request.query_params.get('user_id')
        # 假设 action_type=2 代表收藏行为
        # 先在行为表里找到该用户所有 action_type=2 的商品 ID
        favorite_product_ids = UserBehavior.objects.filter(
            user_id=user_id, action_type=2
        ).values_list('product_id', flat=True)

        # 再通过这些 ID 去商品表里把真实商品信息捞出来
        products = Product.objects.filter(id__in=favorite_product_ids)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    def delete(self, request):
        """取消收藏"""
        user_id = request.query_params.get('user_id')
        product_id = request.query_params.get('product_id')

        # 在行为表里删掉这条记录
        deleted_count, _ = UserBehavior.objects.filter(
            user_id=user_id,
            product_id=product_id,
            action_type=2
        ).delete()

        if deleted_count > 0:
            return Response({'message': '已取消收藏'})
        else:
            return Response({'error': '未找到该收藏记录'}, status=404)
# 1. 地址管理接口
class AddressView(APIView):
    permission_classes = [AllowAny]
    # +++ 新增这行：清空默认认证，免除 CSRF 检查 +++
    authentication_classes = []
    def get(self, request):
        """获取用户的收货地址列表"""
        user_id = request.query_params.get('user_id')
        addresses = Address.objects.filter(user_id=user_id)
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

    def post(self, request):
        """新增收货地址"""
        serializer = AddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    #处理删除地址的请求
    def delete(self, request):
        address_id = request.query_params.get('id')
        try:
            address = Address.objects.get(id=address_id)
            address.delete()
            return Response({'message': '地址删除成功'})
        except Address.DoesNotExist:
            return Response({'error': '地址不存在'}, status=404)


# 2. 订单管理接口
class OrderView(APIView):
    permission_classes = [AllowAny]
    # 提前防范：订单接口也要清空认证，否则等下提交订单也会报一模一样的错！
    authentication_classes = []

    @transaction.atomic  # 加事务，防止超时取消时回滚库存出错
    def get(self, request):
        """获取我的订单列表，并包含 30 分钟超时检测"""
        user_id = request.query_params.get('user_id')
        if user_id:
            orders = Order.objects.filter(user_id=user_id).order_by('-created_at')
        else:
            orders = Order.objects.all().order_by('-created_at')

        # 懒加载检查超时订单
        now = timezone.now()
        for order in orders:
            # 如果是“待支付”状态 (status == 1)
            if order.status == 1:
                # 如果当前时间 > 订单创建时间 + 30分钟
                if now > (order.created_at + timedelta(minutes=30)):
                    order.status = 5  # 5 代表“已取消”
                    order.save()  # 更新进数据库

                    # +++ 超时取消：把库存加回到特定的 SKU 里 +++
                    for item in order.items.all():
                        try:
                            sku = ProductSKU.objects.select_for_update().get(
                                product_id=item.product_id, color=item.selected_color, size=item.selected_size
                            )
                            sku.stock += item.quantity
                            sku.save()
                        except ProductSKU.DoesNotExist:
                            # 兼容没有SKU的情况
                            product = Product.objects.select_for_update().get(id=item.product_id)
                            product.stock += item.quantity
                            product.save()

        # 序列化并返回最新的状态
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @transaction.atomic  # 开启数据库事务防错机制
    def post(self, request):
        """核心：提交订单（结算购物车）并扣减库存"""
        data = request.data
        user_id = data.get('user_id')
        address_id = data.get('address_id')
        total_amount = data.get('total_amount')
        items = data.get('items', [])  # 前端传过来的购物车商品数组

        if not all([user_id, address_id, total_amount, items]):
            return Response({'error': '订单参数不完整'}, status=400)

        try:
            # 1. 生成唯一的订单编号
            time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            order_sn = f"ORD{time_str}{random.randint(1000, 9999)}"

            # 2. 创建订单主表
            order = Order.objects.create(
                user_id=user_id,
                address_id=address_id,
                order_sn=order_sn,
                total_amount=total_amount,
                status=1  # 1 代表待支付
            )

            # 3. 循环将购物车商品写入订单明细表，并做清理与记录
            for item in items:
                # 兼容前端可能传 null 的情况，强转为空字符串
                color = item.get('selected_color') or ''
                size = item.get('selected_size') or ''
                quantity = int(item.get('quantity', 1))
                product_id = item['product_id']

                # +++ 下单扣减：锁定对应的 SKU 行并校验库存 +++
                try:
                    sku = ProductSKU.objects.select_for_update().get(
                        product_id=product_id, color=color, size=size
                    )
                    if sku.stock < quantity:
                        raise Exception(f"手慢了，商品【{sku.product.name} - {color}/{size}】库存不足")

                    sku.stock -= quantity
                    sku.save()

                    product = sku.product  # 拿到关联的主商品
                except ProductSKU.DoesNotExist:
                    # 兼容：如果没有生成 SKU，就退回到扣减主商品库存
                    product = Product.objects.select_for_update().get(id=product_id)
                    if product.stock < quantity:
                        raise Exception(f"手慢了，商品【{product.name}】库存不足")
                    product.stock -= quantity
                    product.save()

                # 3.1 正常写入订单明细
                OrderItem.objects.create(
                    order=order,
                    product=product,  # 这里直接传 product 对象
                    price=item['price'],
                    quantity=quantity,
                    selected_color=color,
                    selected_size=size
                )

                # 【+++ 本次新增：执行库存扣减 +++】
                product.stock -= quantity
                product.save()

                # 为推荐算法喂入“购买”行为（保留你的原逻辑）
                UserBehavior.objects.create(
                    user_id=user_id,
                    product_id=product_id,
                    action_type=4  # 4 代表购买，最高权重！
                )

                # 买完之后，清理购物车对应的商品（保留你的原逻辑）
                CartItem.objects.filter(
                    user_id=user_id,
                    product_id=product_id,
                    selected_color=color,
                    selected_size=size
                ).delete()

            return Response({'message': '下单成功', 'order_sn': order_sn}, status=200)

        except Exception as e:
            # 捕获库存不足的异常，事务会自动回滚，之前的操作全部撤销
            return Response({'error': str(e)}, status=400)

    @transaction.atomic  # 手动取消订单也需要保护库存一致性
    def put(self, request):
        """处理修改订单（取消订单）请求"""
        order_sn = request.data.get('order_sn')
        action = request.data.get('action')  # 获取前端想做的操作，比如 'cancel'
        if not order_sn or not action:
            return Response({'error': '缺少必要参数'}, status=400)
        try:
            order = Order.objects.get(order_sn=order_sn)
            if action == 'cancel':
                # 限制：只有“待支付(1)”和“待发货(2)”的订单可以被用户手动取消
                if order.status in [1, 2]:
                    order.status = 5  # 5 代表已取消状态
                    order.save()

                    # +++ 手动取消：把库存加回到特定的 SKU 里 +++
                    for item in order.items.all():
                        try:
                            sku = ProductSKU.objects.select_for_update().get(
                                product_id=item.product_id, color=item.selected_color, size=item.selected_size
                            )
                            sku.stock += item.quantity
                            sku.save()
                        except ProductSKU.DoesNotExist:
                            product = Product.objects.select_for_update().get(id=item.product_id)
                            product.stock += item.quantity
                            product.save()
                        # +++ 【本次新增】：撤回算法打分权重（物理删除购买记录） +++
                        # 必须确保文件顶部已经引入了 UserBehavior 模型！
                        from products.models import UserBehavior  # 如果已在顶部引入可省略此行
                        UserBehavior.objects.filter(
                            user_id=order.user_id,  # 匹配当前下订单的用户
                            product_id=item.product_id,  # 匹配当前循环到的商品
                            action_type=4  # 4 代表最高权重的“购买”行为
                        ).delete()

                    return Response({'message': '订单取消成功，库存已返还'})
                else:
                    return Response({'error': '当前订单状态不支持取消'}, status=400)

            return Response({'error': '无效的操作类型'}, status=400)

        except Order.DoesNotExist:
            return Response({'error': '找不到该订单'}, status=404)

# 处理支付状态的接口
class OrderPaymentView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] # 同样免除 CSRF 检查

    def post(self, request):
        """模拟支付成功，将订单状态改为待发货"""
        order_sn = request.data.get('order_sn')
        try:
            # 去数据库找到这笔订单
            order = Order.objects.get(order_sn=order_sn)
            # 状态 2 代表“待发货”（也就是已付款）
            order.status = 2
            order.save()
            return Response({'message': '支付成功，状态已更新为待发货'})
        except Order.DoesNotExist:
            return Response({'error': '订单不存在'}, status=404)


class CartView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # 免除 CSRF 检查

    def get(self, request):
        """查：获取购物车列表"""
        user_id = request.query_params.get('user_id')
        items = CartItem.objects.filter(user_id=user_id).order_by('-created_at')
        serializer = CartItemSerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request):
        """增：加入购物车（含自动合并同款逻辑）"""
        user_id = request.data.get('user_id')
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        color = request.data.get('selected_color', '')
        size = request.data.get('selected_size', '')

        # 核心逻辑：去购物车里找找看，有没有完全一样的衣服
        cart_item = CartItem.objects.filter(
            user_id=user_id,
            product_id=product_id,
            selected_color=color,
            selected_size=size
        ).first()

        if cart_item:
            # 如果有，数量累加
            cart_item.quantity += quantity
            cart_item.save()
        else:
            # 如果没有，创建新记录
            cart_item = CartItem.objects.create(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                selected_color=color,
                selected_size=size
            )

        return Response({'message': '已加入购物车'})

    def put(self, request):
        """改：修改数量 或 勾选状态"""
        item_id = request.data.get('id')
        try:
            cart_item = CartItem.objects.get(id=item_id)
            if 'quantity' in request.data:
                cart_item.quantity = request.data['quantity']
            if 'is_checked' in request.data:
                cart_item.is_checked = request.data['is_checked']
            cart_item.save()
            return Response({'message': '更新成功'})
        except CartItem.DoesNotExist:
            return Response({'error': '记录不存在'}, status=404)

    def delete(self, request):
        """删：移除商品"""
        item_id = request.query_params.get('id')
        try:
            cart_item = CartItem.objects.get(id=item_id)
            cart_item.delete()
            return Response({'message': '删除成功'})
        except CartItem.DoesNotExist:
            return Response({'error': '记录不存在'}, status=404)


class ProductReviewView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        """查：获取某件商品的所有评价"""
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': '缺少商品ID'}, status=400)

        # 按时间倒序，最新的评价排在最前面
        reviews = ProductReview.objects.filter(product_id=product_id).order_by('-created_at')
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def post(self, request):
        """增：发布新评价 (支持带图上传)"""
        user_id = request.data.get('user_id')
        product_id = request.data.get('product_id')
        # 获取图片文件，注意这里用的是 request.FILES
        image = request.FILES.get('image')
        rating = request.data.get('rating', 5)
        content = request.data.get('content', '')

        if not all([user_id, product_id, content]):
            return Response({'error': '缺少必要参数（用户、商品或评价内容）'}, status=400)

        # 创建评价记录
        ProductReview.objects.create(
            user_id=user_id,
            product_id=product_id,
            rating=rating,
            content=content,
            image=image # Django 会自动处理图片的保存
        )
        return Response({'message': '评价发布成功'})


# ==========================================
# +++ 新增：客服消息沟通接口 +++
# ==========================================
class MessageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        """获取当前用户与客服的所有聊天记录"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': '缺少用户ID'}, status=400)

        # 按时间正序排列（最早的在上面，最新的在下面，符合聊天软件习惯）
        messages = Message.objects.filter(user_id=user_id).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request):
        """用户或客服发送新消息"""
        user_id = request.data.get('user_id')
        content = request.data.get('content')
        # 默认是用户发出的
        sender_type = request.data.get('sender_type', 'user')

        if not all([user_id, content]):
            return Response({'error': '消息内容不能为空'}, status=400)

        Message.objects.create(
            user_id=user_id,
            content=content,
            sender_type=sender_type
        )
        return Response({'message': '发送成功'}, status=201)


# 关联推荐接口
# 文件位置：views.py -> 找到 关联推荐接口 (RelatedProductView)

class RelatedProductView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        """获取商品详情页底部的关联推荐"""
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': '缺少商品ID'}, status=400)

        # 1. 调用你 algo.py 里的推荐算法
        related_products = get_related_products(product_id, top_n=4)

        # 2. 如果算法返回为空（新项目常见），则执行兜底逻辑
        if not related_products.exists():
            target_product = Product.objects.filter(id=product_id).first()
            if target_product:
                # 随机推荐同分类下的其他4件商品
                related_products = Product.objects.filter(
                    category=target_product.category
                ).exclude(id=product_id).order_by('?')[:4]
            else:
                related_products = Product.objects.all().order_by('?')[:4]

        serializer = ProductSerializer(related_products, many=True)
        return Response(serializer.data)