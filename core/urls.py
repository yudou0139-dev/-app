from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# 导入所有写好的视图 (去掉了 social 相关的导入)
from products.views import ProductListView, RecommendView, UserBehaviorView
from users.views import RegisterView, LoginView, UpdateProfileView

urlpatterns = [
                  path('admin/', admin.site.urls),

                  # --- 用户模块 API ---
                  path('api/users/register/', RegisterView.as_view()),
                  path('api/users/login/', LoginView.as_view()),
                  path('api/users/profile/update/', UpdateProfileView.as_view()),

                  # --- 商品与推荐模块 API ---
                  path('api/products/', ProductListView.as_view()),  # 获取商品列表
                  path('api/recommend/', RecommendView.as_view()),  # 猜你喜欢
                  path('api/behavior/', UserBehaviorView.as_view()),  # 记录用户操作（加购/购买等）

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)