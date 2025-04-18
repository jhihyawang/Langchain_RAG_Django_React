from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # API Modules
    path("api/", include("enterprise_assistant.urls")),
    path("api/", include("general_assistant.urls")),

    # API Schema & Docs (OpenAPI)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Media files (uploaded document access)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
