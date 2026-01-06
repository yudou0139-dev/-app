from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from products.views import ProductListView, RecommendView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- 我们开放的 API 接口 ---
    path('api/products/', ProductListView.as_view()),     # 商品列表
    path('api/recommend/', RecommendView.as_view()),    # 猜你喜欢
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # 允许访问图片