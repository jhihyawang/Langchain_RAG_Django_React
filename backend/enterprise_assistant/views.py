from rest_framework import generics, status, filters, pagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import Knowledge
from .serializers import KnowledgeSerializer,EnterpriseQuerySerializer,EnterpriseQueryResponseSerializer
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .rag.vectorstores import (
    enterprise_vectorstore,
    extract_text_from_pdf_with_pages,
    add_to_enterprise_vectorstore,
    delete_from_enterprise_vectorstore,
    list_from_enterprise_vectorstore
)

class KnowledgePagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'size'
    max_page_size = 50

class KnowledgeListCreateView(generics.ListCreateAPIView):
    queryset = Knowledge.objects.all().order_by("-created_at")
    serializer_class = KnowledgeSerializer
    pagination_class = None
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

        serializer = self.get_serializer(queryset, many=True)

        return Response({"data": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if "file" not in request.FILES:
            return Response({"error": "請上傳文件"}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES["file"]
        department = request.data.get("department", "")
        author = request.data.get("author", None)

        knowledge = Knowledge.objects.create(file=file, department=department, author_id=author)
        file_path = knowledge.file.path

        if file.name.endswith(".pdf"):
            extracted_pages = extract_text_from_pdf_with_pages(file_path)
        else:
            extracted_pages = [(1, extract_text_from_file(file_path))]
            
        for page_number, page_content in extracted_pages:
            add_to_enterprise_vectorstore(file.name, page_content, page_number, knowledge_id=knowledge.id)
   
        chunks = list_from_enterprise_vectorstore(knowledge.id)
        first_chunk = chunks[0]["content"] if chunks else ""
        # 將第一個 chunk 當作 content 紀錄
        knowledge.content = first_chunk
        knowledge.chunk = len(chunks)
        knowledge.save()
        return Response(KnowledgeSerializer(knowledge).data, status=status.HTTP_201_CREATED)

class KnowledgeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Knowledge.objects.all()
    serializer_class = KnowledgeSerializer
    parser_classes = (MultiPartParser, FormParser)

    def put(self, request, *args, **kwargs):
        knowledge = self.get_object()
        knowledge_id = knowledge.id
        old_title = os.path.basename(knowledge.file.name) if knowledge.file else f"manual_{knowledge_id}"

        if request.content_type.startswith("application/json"):
            content = request.data.get("content")
            department = request.data.get("department", knowledge.department)

            knowledge.content = content or ""
            knowledge.department = department
            knowledge.save()

            delete_from_enterprise_vectorstore(knowledge_id=knowledge_id)
            add_to_enterprise_vectorstore(old_title, knowledge.content, knowledge_id=knowledge_id)

            print(f"✅ [JSON 更新] 已更新 ID={knowledge_id} 並同步向量庫")
            return Response(KnowledgeSerializer(knowledge).data, status=status.HTTP_200_OK)

        if "file" not in request.FILES:
            return Response({"error": "請上傳新文件"}, status=status.HTTP_400_BAD_REQUEST)

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
            print(f"🗑 已刪除舊文件: {old_file_path}")

        new_file_path = knowledge.file.path
        if new_file.name.endswith(".pdf"):
            extracted_pages = extract_text_from_pdf_with_pages(new_file_path)
        else:
            extracted_pages = [(1, extract_text_from_file(new_file_path))]

        new_content = "\n\n".join([text for _, text in extracted_pages])
        knowledge.content = new_content
        knowledge.save()

        delete_from_enterprise_vectorstore(knowledge_id=knowledge_id)

        for page_number, page_content in extracted_pages:
            add_to_enterprise_vectorstore(knowledge.file.name, page_content, page_number, knowledge_id=knowledge_id)

        print(f"✅ [檔案更新] 已更新 ID={knowledge_id} 並同步向量庫")
        return response

    def delete(self, request, *args, **kwargs):
        knowledge = self.get_object()
        file_path = os.path.join(settings.MEDIA_ROOT, knowledge.file.name) if knowledge.file else None
        knowledge_id = knowledge.id

        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑 已刪除本地檔案: {file_path}")

        delete_from_enterprise_vectorstore(knowledge_id=knowledge_id)

        response = super().delete(request, *args, **kwargs)

        return response