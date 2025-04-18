# 📁 enterprise_assistant/views/knowledge.py
import json
import os

from common.module.processor.pdf_processor import PdfProcessor
from common.module.processor.vector_store import VectorStoreHandler
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import filters, generics, pagination, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..models import Knowledge
from ..serializers import KnowledgeSerializer

vectorstore = VectorStoreHandler(db_path="chroma_user_db")

class KnowledgePagination(pagination.PageNumberPagination):
    page_size = 5
    page_size_query_param = 'size'
    max_page_size = 50


def standard_response(success=True, message="成功", data=None):
    return Response({
        "success": success,
        "message": message,
        "data": data
    }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)


class KnowledgeListCreateView(generics.ListCreateAPIView):
    queryset = Knowledge.objects.all().order_by("-created_at")
    serializer_class = KnowledgeSerializer
    pagination_class = KnowledgePagination
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [filters.SearchFilter]
    search_fields = ["file", "department"]

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        title = request.GET.get("title")
        department = request.GET.get("department")

        if title:
            queryset = queryset.filter(file__icontains=title)
        if department:
            queryset = queryset.filter(department__icontains=department)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return standard_response(data=serializer.data)

    def post(self, request, *args, **kwargs):
        if "file" not in request.FILES:
            return standard_response(False, "請上傳文件")

        file = request.FILES["file"]
        department = request.data.get("department", "")
        author = request.data.get("author", None)

        # 自動設定 title 為上傳檔案名稱（不含副檔名）
        title = os.path.splitext(file.name)[0]

        knowledge = Knowledge.objects.create(
            file=file,
            title=title,
            department=department,
            author_id=author
        )

        file_path = knowledge.file.path
        processor = PdfProcessor(pdf_path=file_path, knowledge_id=str(knowledge.id))
        result = processor.process()

        # 儲存至向量庫
        for media_type in ["text", "table", "image"]:
            for item in result.get(media_type, []):
                success = vectorstore.add(
                    content=item["content"],
                    page=json.dumps(item["page"] if isinstance(item["page"], list) else [item["page"]]),
                    document_id=knowledge.id,
                    media_type=media_type,
                    source=json.dumps(item["source"] if isinstance(item["source"], list) else [item["source"]])
                )
                if success:
                    print(f"✅ page {item['page']}, content stored to vectorstore")

        # 更新摘要與 chunk 數
        chunks = vectorstore.list(knowledge.id)
        first_chunk = chunks[0]["content"] if chunks else ""
        knowledge.content = first_chunk
        knowledge.chunk = len(chunks)
        knowledge.save()

        print(f"✅ 上傳文件完成，產生 {len(chunks)} 個 chunks 並儲存至向量庫")
        return standard_response(message="文件上傳成功", data=KnowledgeSerializer(knowledge).data)


class KnowledgeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Knowledge.objects.all()
    serializer_class = KnowledgeSerializer
    parser_classes = (MultiPartParser, FormParser)

    def put(self, request, *args, **kwargs):
        knowledge = self.get_object()
        knowledge_id = knowledge.id

        if request.content_type.startswith("application/json"):
            content = request.data.get("content")
            department = request.data.get("department", knowledge.department)

            knowledge.content = content or ""
            knowledge.department = department
            knowledge.save()

            vectorstore = VectorStoreHandler("chroma_user_db")
            vectorstore.delete(knowledge_id)
            vectorstore.add(content, media_type="text", page=1, document_id=knowledge_id, source="manual_update")

            return standard_response(message="已更新並同步向量庫", data=KnowledgeSerializer(knowledge).data)

        if "file" not in request.FILES:
            return standard_response(False, "請上傳新文件")

        old_file_path = os.path.join(settings.MEDIA_ROOT, knowledge.file.name) if knowledge.file else None
        new_file = request.FILES["file"]

        temp_file_path = os.path.join(settings.MEDIA_ROOT, "temp_" + new_file.name)
        with default_storage.open(temp_file_path, 'wb+') as destination:
            for chunk in new_file.chunks():
                destination.write(chunk)

        response = self.update(request, *args, **kwargs)
        knowledge.refresh_from_db()

        if old_file_path and os.path.exists(old_file_path):
            os.remove(old_file_path)

        new_file_path = knowledge.file.path
        processor = PdfProcessor(pdf_path=new_file_path, knowledge_id=str(knowledge_id))
        result = processor.process()
        first_chunk = result["text"][0] if result["text"] else ""
        knowledge.content = first_chunk
        knowledge.chunk = sum(len(result[k]) for k in ["text", "table", "image"])
        knowledge.save()

        return standard_response(message="文件已更新並同步向量庫", data=KnowledgeSerializer(knowledge).data)

    def delete(self, request, *args, **kwargs):
        knowledge = self.get_object()
        file_path = os.path.join(settings.MEDIA_ROOT, knowledge.file.name) if knowledge.file else None
        knowledge_id = knowledge.id

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        vectorstore = VectorStoreHandler("chroma_user_db")
        vectorstore.delete(knowledge_id)
        knowledge.delete()

        return standard_response(message="已刪除知識文件")