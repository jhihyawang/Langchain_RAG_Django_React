from django.urls import path
from .views import KnowledgeListCreateView, KnowledgeDetailView
from .rag.llm_client import EnterpriseQueryView
from .rag.vectorstores import (
    ChunkListCreateView,
    ChunkDetailView
)
urlpatterns = [
    # 知識庫 CRUD
    path("knowledge/", KnowledgeListCreateView.as_view(), name="knowledge-list-create"),
    path("knowledge/<int:pk>/", KnowledgeDetailView.as_view(), name="knowledge-detail"),
    # 取得某知識文件的所有 chunks（編輯頁載入）
    path("knowledge/<int:pk>/chunks/", ChunkListCreateView.as_view(), name="knowledge-chunks"),
    path("knowledge/chunk/<str:chunk_id>/", ChunkDetailView.as_view(), name="chunk-detail"),
    # 企業知識庫查詢 API（LLM + RAG）
    path("query_enterprise/", EnterpriseQueryView.as_view(), name="query-enterprise"),
]