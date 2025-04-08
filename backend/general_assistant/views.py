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

# 向量資料庫與嵌入模型
CHROMA_USER_DB_PATH = "chroma_user_db"
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
user_vectorstore = Chroma(persist_directory=CHROMA_USER_DB_PATH, embedding_function=embedder)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

def summarize_text_or_table(element, element_type):
    if element_type == 'text':
        return f"[{element_type.upper()} 摘要] {element}..."
    elif element_type == 'table':
        try:
            prompt=f"你是一位文本處理的助手，請根據以下內容進行摘要 {element_type}:\n{element}"
            response = ollama.chat(
                model='gemma3:4b',
                messages=[{
                    'role': 'user',
                    'content': prompt,
                }]
            )
            return f"[{element_type.upper()} 摘要] {response['message']['content']}..."
        except Exception as e:
            return f"❌ Gemma3 表格分析錯誤: {str(e)}"

def summarize_image_with_gemma3(image_path, prompt="請詳細描述這張圖片的內容，若是圖表請說明其趨勢與關鍵數據"):
    try:
        response = ollama.chat(
            model='gemma3:4b',
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [image_path]
            }]
        )
        return response['message']['content']
    except Exception as e:
        return f"❌ Gemma3 圖像分析錯誤: {str(e)}"

def add_to_user_vectorstore(file_path, title, content, page_number=1):
    if not content.strip():
        return False
    chunks = text_splitter.split_text(content)
    if not chunks:
        return False
    metadata = [{"filename": file_path, "title": title, "chunk_index": i, "page_number": page_number} for i in range(len(chunks))]
    user_vectorstore.add_texts(chunks, metadatas=metadata)
    return True

def retrieve_from_chroma(query):
    retriever = user_vectorstore.as_retriever(search_kwargs={"k": 5})
    documents = retriever.get_relevant_documents(query)
    retrieved_docs = []
    for doc in documents:
        page_number = doc.metadata.get("page_number", "未知頁碼")
        filename = doc.metadata.get("filename", "未知文件")
        retrieved_docs.append({
            "filename": filename,
            "page_number": page_number,
            "content": doc.page_content
        })
    return "\n\n".join([doc["content"] for doc in retrieved_docs])

def extract_element_from_pdf(file_path):
    output_path = "./images"
    os.makedirs(output_path, exist_ok=True)
    text_elements, table_elements, image_elements = [], [], []
    text_summaries, table_summaries, image_summaries = [], [], []
    table_metadata, image_metadata = [], []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_elements.append(text)
                summary = summarize_text_or_table(text, 'text')
                print(f"processing: {page_num},text summary: {summary}")
                text_summaries.append(summary)

            tables = page.extract_tables()
            for table_index, table in enumerate(tables):
                table_str = str(table)
                table_elements.append(table_str)
                summary = summarize_text_or_table(table_str, 'table')
                table_summaries.append(summary)
                print(f"processing: page{page_num},table{table_index}\ntable summary: {table_summaries}")
                table_metadata.append({"page": page_num + 1, "content": table_str})

    doc = fitz.open(file_path)
    for page_index in range(len(doc)):
        print(f"processing:{page_index}")
        for img_index, img in enumerate(doc[page_index].get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_ext = base_image["ext"]
            img_filename = f"page{page_index+1}_img{img_index+1}.{img_ext}"
            image_path = os.path.join(output_path, img_filename)

            with open(image_path, "wb") as f:
                f.write(img_bytes)

            image_elements.append(image_path)
            summary = summarize_image_with_gemma3(image_path)
            print(f"{img_filename}:{summary}")
            image_summaries.append(summary)
            image_metadata.append({
                "page": page_index + 1,
                "path": image_path,
                "summary": summary,
                "image_name": f"圖 {page_index+1}-{img_index+1}"
            })

    for e, s in zip(text_elements, text_summaries):
        add_to_user_vectorstore(file_path, "Text Element", s)
    for item, summary in zip(table_metadata, table_summaries):
        add_to_user_vectorstore(file_path, "Table Element", summary, page_number=item["page"])
    for item in image_metadata:
        add_to_user_vectorstore(file_path, "Image Element", item["summary"], page_number=item["page"])

    return {
        "text_summaries": text_summaries,
        "table_summaries": table_summaries,
        "image_summaries": image_summaries,
        "tables": table_metadata,
        "images": image_metadata
    }

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
    filter_backends = [filters.SearchFilter]

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        filename = request.GET.get("filename")
        if filename:
            queryset = queryset.filter(file__icontains=filename)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"data": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        if "file" not in request.FILES:
            return Response({"error": "請上傳文件"}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES["file"]
        author = request.data.get("author", None)
        document = Document.objects.create(file=file, author_id=author)
        file_path = document.file.path

        if file.name.endswith(".pdf"):
            extracted_summaries = extract_element_from_pdf(file_path)
        else:
            return Response({"error": "僅支援 PDF 檔案"}, status=status.HTTP_400_BAD_REQUEST)

        full_summary = "\n\n".join(
            extracted_summaries["text_summaries"] +
            extracted_summaries["table_summaries"] +
            [f"{img['image_name']}: {img['summary']}" for img in extracted_summaries["images"]]
        )

        document.content = full_summary
        document.save()

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

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
