from django.urls import path
from .upload import DocumentListCreateView, DocumentDetailView, UserQueryView

urlpatterns = [
    # 文本 CRUD（新增 & 列表）
    path("document/", DocumentListCreateView.as_view(), name="document-list-create"),
    # 文本 單一文件 CRUD（詳細資訊、更新、刪除）
    path("document/<int:pk>/", DocumentDetailView.as_view(), name="document-detail"),  # ✅ 修正這裡
    # 查詢 API（LLM + RAG）
    path("query_user/", UserQueryView.as_view(), name="query-user"),
]