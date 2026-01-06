from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Product
from .serializers import ProductSerializer
from recommend.algo import item_based_recommendation


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