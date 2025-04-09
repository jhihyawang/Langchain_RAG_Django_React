from django.urls import path
from .views import KnowledgeListCreateView, KnowledgeDetailView, EnterpriseQueryView
from .views import ChunkUpdateView

urlpatterns = [
    # 知識庫 CRUD
    path("knowledge/", KnowledgeListCreateView.as_view(), name="knowledge-list-create"),
    path("knowledge/<int:pk>/", KnowledgeDetailView.as_view(), name="knowledge-detail"),
    path("knowledge/chunk/<str:chunk_id>/", ChunkUpdateView.as_view(), name="chunk-update"),
    # 企業知識庫查詢 API（LLM + RAG）
    path("query_enterprise/", EnterpriseQueryView.as_view(), name="query-enterprise"),
]