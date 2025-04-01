from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# 設定 Swagger Schema
schema_view = get_schema_view(
    openapi.Info(
        title="Copilot API",
        default_version="v1",
        description="Copilot API 文件",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="admin@example.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),  # 允許所有人存取
)

# ✅ 合併所有路由，確保 API 和 Swagger 都可用
urlpatterns = [
    path("admin/", admin.site.urls),  # Django Admin
    path("api/", include("enterprise_assistant.urls")),  # 確保 /api/ 導入 enterprise_assistant
    path("api/", include("general_assistant.urls")),  # 確保 /api/ 導入 enterprise_assistant
    # Swagger 路由
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),  
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),  
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),  
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # 確保 MEDIA_URL 可用
