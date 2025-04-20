# 📁 enterprise_assistant/views/knowledge.py
import json
import os
import shutil
from threading import Thread

from common.modules.processor.pdf_processor import PdfProcessor
from common.modules.processor.vector_store import VectorStoreHandler
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import filters, generics, pagination, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..models import Knowledge
from ..serializers import KnowledgeSerializer
from .tasks import process_pdf_background

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

        # 先儲存檔案與基本資料
        knowledge = Knowledge.objects.create(
            file=file,
            department=department,
            author_id=author,
            title=os.path.splitext(file.name)[0],
            processing_status="pending"
        )

        # 加入背景任務
        process_pdf_background(knowledge.id)

        # ✅ 回應成功（不等待）
        return standard_response(message="檔案已上傳，背景處理中", data=KnowledgeSerializer(knowledge).data)

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
        result = processor.optimized_process()
        first_chunk = result["text"][0] if result["text"] else ""
        knowledge.content = first_chunk
        knowledge.chunk = sum(len(result[k]) for k in ["text", "table", "image"])
        knowledge.save()

        return standard_response(message="文件已更新並同步向量庫", data=KnowledgeSerializer(knowledge).data)

    def delete(self, request, *args, **kwargs):
        knowledge = self.get_object()
        file_name = os.path.basename(knowledge.file.name) if knowledge.file else None
        knowledge_id = knowledge.id
        filename_without_ext = os.path.splitext(file_name)[0]

        # 原始上傳檔案的完整路徑
        original_file_path = os.path.join(settings.MEDIA_ROOT, "knowledge_files", file_name) if file_name else None

        # 對應的 extract_data 子資料夾
        extract_dir = os.path.join(settings.MEDIA_ROOT, "extract_data", filename_without_ext) if filename_without_ext else None

        try:
            # 1️⃣ 刪除 DB 資料
            knowledge.delete()

            # 2️⃣ 刪除向量資料庫內容
            vectorstore.delete(knowledge_id)

            # 3️⃣ 刪除 extract_data 資料夾
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
                print(f"✅ 已刪除資料夾：{extract_dir}")
            else:
                print(f"❌ 未找到 extract_data 資料夾：{extract_dir}")

            # 4️⃣ 刪除原始上傳檔案
            if original_file_path and os.path.exists(original_file_path):
                os.remove(original_file_path)
                print(f"✅ 已刪除檔案：{original_file_path}")
            else:
                print(f"❌ 未找到檔案：{original_file_path}")

            return standard_response(message="已刪除知識文件")

        except Exception as e:
            return standard_response(message=f"刪除過程中出現錯誤: {str(e)}", status="error")
