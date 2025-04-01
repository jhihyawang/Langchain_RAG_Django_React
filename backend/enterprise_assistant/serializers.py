from rest_framework import serializers
from .models import Knowledge, AdminUser
import os
import urllib.parse
from pathlib import Path

class KnowledgeSerializer(serializers.ModelSerializer):
    filename = serializers.SerializerMethodField()  # ✅ 解析檔案名稱

    class Meta:
        model = Knowledge
        fields = ["id", "filename", "file", "department", "content", "created_at", "updated_at", "author"]

    def get_filename(self, obj):
        """解析 `file` URL，取得純檔名"""
        if obj.file:
            parsed_url = urllib.parse.urlparse(obj.file.url)
            return os.path.basename(urllib.parse.unquote(parsed_url.path))
        return None

# 定義 LLM Request 和 Response 的 Serializer
class EnterpriseQuerySerializer(serializers.Serializer):
    query = serializers.CharField(help_text="使用者輸入的查詢問題")
    model_type = serializers.ChoiceField(choices=["cloud", "local"], default="cloud", help_text="選擇 LLM 模型（cloud 或 local）")
    
class EnterpriseQueryResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    answer = serializers.CharField()
    retrieved_docs = serializers.ListField(
        child=serializers.DictField(),
        help_text="檢索到的相關文件資訊"
    )

class AdminUserSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = AdminUser
        fields = ["id", "user", "department", "is_superadmin"]