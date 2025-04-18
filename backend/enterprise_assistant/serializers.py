from enterprise_assistant.models import Knowledge
from rest_framework import serializers


class KnowledgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Knowledge
        fields = [
            "id",
            "file",
            "department",
            "content",
            "chunk",
            "author",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["id", "chunk", "content", "created_at", "updated_at"]
        
class EnterpriseQuerySerializer(serializers.Serializer):
    query = serializers.CharField(help_text="使用者查詢內容", required=True)
    model_type = serializers.ChoiceField(
        choices=[("cloud", "Cloud"), ("local", "Local")],
        default="cloud",
        help_text="使用的模型類型"
    )
    use_retrieval = serializers.BooleanField(
        default=True,
        help_text="是否啟用知識檢索 (RAG)"
    )


class EnterpriseQueryResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    answer = serializers.CharField()
    retrieved_docs = serializers.ListField(
        child=serializers.DictField(),
        help_text="LLM 回答所依據的相關段落內容"
    )

class ChunkSerializer(serializers.Serializer):
    id = serializers.CharField()
    content = serializers.CharField()
    chunk_index = serializers.IntegerField()
    page_number = serializers.ListField(child=serializers.IntegerField())
    media_type = serializers.CharField()
    source = serializers.ListField(child=serializers.CharField()) 