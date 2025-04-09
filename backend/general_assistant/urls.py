from django.urls import path
from django.urls import path
from .views import DocumentListCreateView, DocumentDetailView,UserQueryView
from .rag.vectorstores import (
    ChunkListCreateView,
    ChunkDetailView
)

urlpatterns = [
    # 文本 CRUD（新增 & 列表）
    path("document/", DocumentListCreateView.as_view(), name="document-list-create"),

    # 文本 單一文件 CRUD（詳細資訊、更新、刪除）
    path("document/<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    # 取得某知識文件的所有 chunks（編輯頁載入）
    path("document/<int:pk>/chunks/", ChunkListCreateView.as_view(), name="knowledge-chunks"),
    path("document/chunk/<str:chunk_id>/", ChunkDetailView.as_view(), name="chunk-detail"),
    # 查詢 API（LLM + RAG）
    path("query_user/", UserQueryView.as_view(), name="query-user"),
]