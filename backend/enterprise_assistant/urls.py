from django.urls import path
from .views import KnowledgeListCreateView, KnowledgeDetailView, EnterpriseQueryView

urlpatterns = [
    # 知識庫 CRUD
    path("knowledge/", KnowledgeListCreateView.as_view(), name="knowledge-list-create"),
    path("knowledge/<int:pk>/", KnowledgeDetailView.as_view(), name="knowledge-detail"),

    # 企業知識庫查詢 API（LLM + RAG）
    path("query_enterprise/", EnterpriseQueryView.as_view(), name="query-enterprise"),
]