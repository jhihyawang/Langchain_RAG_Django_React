from rest_framework import generics, status, filters, pagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import Document
from .serializers import DocumentSerializer, UserQuerySerializer
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from langchain_core.prompts import PromptTemplate
import uuid
import ollama
import fitz  # PyMuPDF
import pdfplumber
import io
import base64
import requests
from PIL import Image
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import os
from django.conf import settings
from django.core.files.storage import default_storage
from .rag.vectorstores import (
    user_vectorstore,
    add_to_general_vectorstore,
    delete_from_general_vectorstore,
    list_from_general_vectorstore,
    extract_element_from_pdf
)

class AskImageView(APIView):
    @swagger_auto_schema(
        operation_description="圖像問答（Gemma3 Vision）",
        manual_parameters=[],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['image', 'question'],
            properties={
                'image': openapi.Schema(type=openapi.TYPE_FILE, description='上傳圖檔'),
                'question': openapi.Schema(type=openapi.TYPE_STRING, description='問題文字')
            },
        ),
        responses={200: openapi.Response(description="回答結果")}
    )
    def post(self, request, *args, **kwargs):
        image_file = request.FILES.get('image')
        question = request.data.get('question')

        if not image_file or not question:
            return Response({"error": "請提供圖片與問題"}, status=status.HTTP_400_BAD_REQUEST)

        temp_folder = "temp_images"
        os.makedirs(temp_folder, exist_ok=True)
        file_ext = image_file.name.split('.')[-1]
        temp_filename = f"{uuid.uuid4()}.{file_ext}"
        temp_path = os.path.join(temp_folder, temp_filename)

        with open(temp_path, 'wb+') as f:
            for chunk in image_file.chunks():
                f.write(chunk)

        try:
            response = ollama.chat(
                model='gemma3:4b',
                messages=[{
                    'role': 'user',
                    'content': question,
                    'images': [temp_path]
                }]
            )
            answer = response['message']['content']
        except Exception as e:
            return Response({"error": f"Ollama Gemma3 Vision 模型呼叫失敗: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return Response({
            "question": question,
            "answer": answer
        }, status=status.HTTP_200_OK)

class DocumentPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'size'
    max_page_size = 50

class DocumentListCreateView(generics.ListCreateAPIView):
    queryset = Document.objects.all().order_by("-created_at")
    serializer_class = DocumentSerializer
    pagination_class = None
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [filters.SearchFilter]
    search_fields = ["file", "department"]

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        title = request.GET.get("title")
        if title:
            queryset = queryset.filter(file__icontains=title)
        serializer = self.get_serializer(queryset, many=True)

        return Response({"data": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if "file" not in request.FILES:
            return Response({"error": "請上傳文件"}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES["file"]
        author = request.data.get("author", None)

        document = Document.objects.create(file=file, author_id=author)

        # ✅ 這裡修正錯誤用法
        file_path = document.file.path

        # 解析 PDF 多模態內容並摘要 + 存入向量庫
        summary = extract_element_from_pdf(file_path, knowledge_id=document.id)

        # 從向量庫取得摘要內容
        chunks = list_from_general_vectorstore(document.id)
        first_chunk = chunks[0]["content"] if chunks else ""

        document.content = first_chunk
        document.chunk = len(chunks)
        document.save()

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = (MultiPartParser, FormParser)

    def put(self, request, *args, **kwargs):
        document = self.get_object()
        document_id = document.id
        old_title = os.path.basename(document.file.name) if document.file else f"manual_{document_id}"

        if request.content_type.startswith("application/json"):
            content = request.data.get("content")
            department = request.data.get("department", document.department)

            document.content = content or ""
            document.department = department
            document.save()

            delete_from_general_vectorstore(document_id=document_id)
            add_to_general_vectorstore(old_title, document.content, document_id=document_id)

            print(f"✅ [JSON 更新] 已更新 ID={document_id} 並同步向量庫")
            return Response(DocumentSerializer(document).data, status=status.HTTP_200_OK)

        if "file" not in request.FILES:
            return Response({"error": "請上傳新文件"}, status=status.HTTP_400_BAD_REQUEST)

        old_file_path = os.path.join(settings.MEDIA_ROOT, document.file.name) if document.file else None

        new_file = request.FILES["file"]
        temp_file_path = os.path.join(settings.MEDIA_ROOT, "temp_" + new_file.name)
        with default_storage.open(temp_file_path, 'wb+') as destination:
            for chunk in new_file.chunks():
                destination.write(chunk)

        response = self.update(request, *args, **kwargs)
        document.refresh_from_db()

        if old_file_path and os.path.exists(old_file_path):
            os.remove(old_file_path)
            print(f"🗑 已刪除舊文件: {old_file_path}")

        new_file_path = document.file.path
        if new_file.name.endswith(".pdf"):
            extracted_pages = extract_text_from_pdf_with_pages(new_file_path)
        else:
            extracted_pages = [(1, extract_text_from_file(new_file_path))]

        new_content = "\n\n".join([text for _, text in extracted_pages])
        document.content = new_content
        document.save()

        delete_from_general_vectorstore(document_id=document_id)

        for page_number, page_content in extracted_pages:
            add_to_general_vectorstore(document.file.name, page_content, page_number, document_id=document_id)

        print(f"✅ [檔案更新] 已更新 ID={document_id} 並同步向量庫")
        return response

    def delete(self, request, *args, **kwargs):
        document = self.get_object()
        file_path = os.path.join(settings.MEDIA_ROOT, document.file.name) if document.file else None
        document_id = document.id

        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑 已刪除本地檔案: {file_path}")

        delete_from_general_vectorstore(document_id=document_id)

        response = super().delete(request, *args, **kwargs)

        return response

class UserQueryView(APIView):
    def post(self, request):
        query = request.data.get("query")
        if not query:
            return Response({"error": "請提供查詢內容"}, status=status.HTTP_400_BAD_REQUEST)

        context = retrieve_from_chroma(query)
        prompt = PromptTemplate(template="根據以下內容回答問題：\n\n{context}\n\n問題：{query}\n回答：", input_variables=["context", "query"])
        formatted_prompt = prompt.format(context=context, query=query)

        try:
            response = ollama.chat(
                model='gemma3:4b',
                messages=[{'role': 'user', 'content': formatted_prompt}]
            )
            answer = response['message']['content']
        except Exception as e:
            return Response({"error": f"Gemma3 查詢錯誤: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"query": query, "answer": answer, "context": context})
