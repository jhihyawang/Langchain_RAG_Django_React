from django.urls import path
from enterprise_assistant.views.query import EnterpriseQueryView

from .views.chunk import ChunkDetailView, ChunkListCreateView
from .views.knowledge import KnowledgeDetailView, KnowledgeListCreateView

urlpatterns = [
    # 知識檔案 CRUD
    path("knowledge/", KnowledgeListCreateView.as_view(), name="knowledge-list-create"),
    path("knowledge/<int:pk>/", KnowledgeDetailView.as_view(), name="knowledge-detail"),

    # Chunk 操作
    path("knowledge/<int:pk>/chunks/", ChunkListCreateView.as_view(), name="knowledge-chunks"),
    path("knowledge/chunk/<str:chunk_id>/", ChunkDetailView.as_view(), name="chunk-detail"),

    # 查詢 API
    path("query_user/", EnterpriseQueryView.as_view(), name="enterprise-query"),
]
