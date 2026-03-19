from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Product
from .serializers import ProductSerializer
from recommend.algo import item_based_recommendation
from .models import UserBehavior

# 接口1：获取所有商品列表
class ProductListView(APIView):
    def get(self, request):
        products = Product.objects.all().order_by('-created_at')
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


# 接口2：猜你喜欢 (核心接口)
class RecommendView(APIView):
    def get(self, request):
        # 暂时模拟一个用户ID (因为还没做App登录，假设是用户ID=1)
        # 实际上线时用 request.user.id
        user_id = 1

        # 调用刚才写的算法
        products = item_based_recommendation(user_id)

        # 如果算法没算出结果（比如新用户），就默认推荐最新的 6 个商品（热底托底策略）
        if not products:
            products = Product.objects.all().order_by('-created_at')[:6]

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


# 接口3：记录用户行为 (给推荐算法喂数据)
class UserBehaviorView(APIView):
    def post(self, request):
        # 实际项目中通常从 request.user.id 获取，为了方便App联调先从传参获取
        user_id = request.data.get('user_id')
        product_id = request.data.get('product_id')
        action_type = request.data.get('action_type') # 1浏览 2收藏 3加购 4购买

        if not all([user_id, product_id, action_type]):
            return Response({'error': '参数不完整'}, status=400)

        # 写入数据库，算法会自动去这个表里抓取数据
        UserBehavior.objects.create(
            user_id=user_id,
            product_id=product_id,
            action_type=action_type
        )
        return Response({'message': '行为记录成功'})