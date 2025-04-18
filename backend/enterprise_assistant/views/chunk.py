from common.module.processor.vector_store import VectorStoreHandler
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from enterprise_assistant.models import Knowledge
from enterprise_assistant.serializers import ChunkSerializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


def standard_response(success=True, message="成功", data=None):
    return Response({
        "success": success,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)

vectorstore = VectorStoreHandler("chroma_user_db")

class ChunkListCreateView(APIView):
    """
    GET: 取得特定文件 (knowledge_id) 的所有向量 chunks
    """
    def get(self, request, pk):
        knowledge = get_object_or_404(Knowledge, pk=pk)
        chunks = vectorstore.list(document_id=knowledge.id)

        try:
            serializer = ChunkSerializer(chunks, many=True)
            return Response({
                "knowledge_id": knowledge.id,
                "title": knowledge.title,
                "chunks": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ChunkDetailView(APIView):
    """
    PUT: 修改單一 chunk 的內容
    DELETE: 刪除單一 chunk
    """

    def put(self, request, chunk_id):
        content = request.data.get("content")
        if not content:
            return standard_response(False, "請提供新的內容")
        
        new_chunk_id = vectorstore.update(chunk_id, content)

        if not new_chunk_id:
            return standard_response(False, "更新失敗或找不到 chunk")

        # 根據新 chunk 的 metadata 找到 document_id
        metadata = vectorstore.get_chunk_metadata_by_id(new_chunk_id)
        knowledge_id = metadata.get("document_id") if metadata else None

        if knowledge_id:
            try:
                knowledge = Knowledge.objects.get(id=knowledge_id)
                chunks = vectorstore.list(document_id=knowledge_id)
                first_chunk = chunks[0]["content"] if chunks else ""
                knowledge.content = first_chunk
                knowledge.updated_at = now()
                knowledge.chunk = len(chunks)
                knowledge.save(update_fields=["content", "chunk", "updated_at"])
            except Knowledge.DoesNotExist:
                return standard_response(False, "找不到對應的知識文件")

        return standard_response(message="✅ 已更新 chunk")

    def delete(self, request, chunk_id):
        deleted = vectorstore.delete_chunk_by_id(chunk_id)
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return standard_response(False, "刪除失敗")
