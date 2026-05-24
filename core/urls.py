from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# +++ 修改导入：在这里加上了 CategoryListView +++
from users.views import RegisterView, LoginView, UpdateProfileView
from products.views import ProductListView, RecommendView, UserBehaviorView, CategoryListView, FavoriteListView, AddressView, OrderView, OrderPaymentView, CartView, ProductReviewView,MessageView, RelatedProductView
urlpatterns = [
    path('admin/', admin.site.urls),

    # --- 用户模块 API ---
    path('api/users/register/', RegisterView.as_view()),
    path('api/users/login/', LoginView.as_view()),
    path('api/users/profile/update/', UpdateProfileView.as_view()),

    # --- 商品与推荐模块 API ---
    path('api/categories/', CategoryListView.as_view()),  # +++ 本次新增：获取分类列表 +++
    path('api/products/', ProductListView.as_view()),     # 获取商品列表 (现在支持筛选了)
    path('api/recommend/', RecommendView.as_view()),      # 猜你喜欢
    path('api/behavior/', UserBehaviorView.as_view()),    # 记录用户操作（加购/购买等）
    path('api/favorites/', FavoriteListView.as_view()), # 获取收藏夹列表

    path('api/address/', AddressView.as_view()), # 地址增查
    path('api/orders/', OrderView.as_view()),    # 订单增查
    path('api/pay/', OrderPaymentView.as_view()),   #支付接口
    path('api/cart/', CartView.as_view()),    #加上这个购物车接口
    path('api/reviews/', ProductReviewView.as_view()),
    path('api/messages/', MessageView.as_view()),

    path('api/products/related/', RelatedProductView.as_view()),# 详情页底部的关联推荐接口

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)