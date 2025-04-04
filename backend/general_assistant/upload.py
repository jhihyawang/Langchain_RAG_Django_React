from rest_framework import generics, status, filters, pagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import Document
from .serializers import DocumentSerializer,UserQuerySerializer,UserQueryResponseSerializer
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from langchain_core.prompts import PromptTemplate
import os
import uuid
import base64
from unstructured.partition.pdf import partition_pdf
from openai import OpenAI
from enterprise_assistant.azure_llama_api import AzureLlamaAPI


# 🔹 設定 OpenAI API
token = "#"
endpoint = "https://models.inference.ai.azure.com"
model_name = "gpt-4o"

client = OpenAI(
    base_url=endpoint,
    api_key=token,
)

# 🔹 設定向量資料庫
CHROMA_USER_DB_PATH = "chroma_user_db"
# 設定詞嵌入模型
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
# 初始化向量資料庫
user_vectorstore = Chroma(persist_directory=CHROMA_USER_DB_PATH, embedding_function=embedder)
# 文字分割器
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

# AI生成 文字 & 表格摘要
def summarize_text_or_table(element, element_type):
    """使用 OpenAI API 來生成摘要"""
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "你是一位文本處理的助手"},
            {"role": "user", "content": f"請根據以下內容進行摘要 {element_type}:\n{element}"}
        ],
        model=model_name,
        max_tokens=1024
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content

# AI生成圖片摘要
def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')
    
def summarize_image(image_path):
    """使用 OpenAI API 來分析圖片"""
    encoded_image = encode_image(image_path)
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "你是一位針對影像和圖片進行摘要的助手"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "請詳細描述這張圖片的內容。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}", "detail": "low"}},
                ],
            },
        ],
        model=model_name,
        max_tokens=1024,
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content

# 存入 ChromaDB
def add_to_user_vectorstore(file_path, title, content, page_number=1):
    global user_vectorstore
    """將內容切割後存入 `chroma_user_db`"""
    if not content.strip():
        print(f"⚠️ 跳過存入（內容為空）：{title}")
        return False

    # 拆分文本
    chunks = text_splitter.split_text(content)
    if not chunks:
        print(f"⚠️ 無法拆分文本，跳過存入 ChromaDB（{title}）")
        return False

    # 設定 metadata
    metadata = [{"filename":file_path,"title": title, "chunk_index": i, "page_number": page_number} for i in range(len(chunks))]

    # 轉換向量並存入
    user_vectorstore.add_texts(chunks, metadatas=metadata)
    print(f"✅ {file_path}已存入 ChromaDB: {title}，共 {len(chunks)} 段落 (Page {page_number})")
    return True

# 解析 PDF，提取 文字 / 表格 / 圖片
import os
import fitz  # PyMuPDF
import pdfplumber

def extract_element_from_pdf(file_path):
    output_path = "./images"
    os.makedirs(output_path, exist_ok=True)

    # 儲存不同類型的元素
    text_elements, table_elements, image_elements = [], [], []
    text_summaries, table_summaries, image_summaries = [], [], []
    table_metadata, image_metadata = [], []

    # ✅ 使用 pdfplumber 提取文字與表格
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_elements.append(text)
                summary = summarize_text_or_table(text, 'text')
                text_summaries.append(summary)

            tables = page.extract_tables()
            for table_index, table in enumerate(tables):
                table_str = str(table)
                table_elements.append(table_str)
                summary = summarize_text_or_table(table_str, 'table')
                table_summaries.append(summary)
                table_metadata.append({"page": page_num + 1, "content": table_str})

    # ✅ 使用 PyMuPDF 提取圖片
    doc = fitz.open(file_path)
    for page_index in range(len(doc)):
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
            summary = summarize_image(image_path)
            image_summaries.append(summary)
            image_metadata.append({"page": page_index + 1, "path": image_path})

    # 存入向量資料庫
    for e, s in zip(text_elements, text_summaries):
        add_to_user_vectorstore(file_path, "Text Element", s)

    for item, summary in zip(table_metadata, table_summaries):
        add_to_user_vectorstore(file_path, "Table Element", summary, page_number=item["page"])

    for item, summary in zip(image_metadata, image_summaries):
        add_to_user_vectorstore(file_path, "Image Element", summary, page_number=item["page"])

    # 回傳所有摘要與對應頁面資訊
    return {
        "text_summaries": text_summaries,
        "table_summaries": table_summaries,
        "image_summaries": image_summaries,
        "tables": table_metadata,   # [{"page": 1, "content": "..."}]
        "images": image_metadata    # [{"page": 2, "path": "./images/page2_img1.jpg"}]
    }
    

def delete_from_user_vectorstore(file_path):
    """
    從 ChromaDB 刪除對應 `file_name` 的向量資料
    """
    try:
        all_vectors = user_vectorstore._collection.get(include=["metadatas"])

        if all_vectors and "metadatas" in all_vectors:
            matching_vectors = [meta for meta in all_vectors["metadatas"] if meta.get("filename") == file_path]

            if matching_vectors:
                print(f"🔍 找到 `{file_path}` 的 {len(matching_vectors)} 筆向量資料，準備刪除...")
                user_vectorstore._collection.delete(where={"filename": file_path})
                print(f"✅ 已成功刪除 `{file_path}` 的向量資料")
                return True
            else:
                print(f"⚠️ 未找到 `{file_path}` 的向量資料，無需刪除")
                return False
    except Exception as e:
        print(f"❌ 刪除 `{file_path}` 的向量資料失敗: {e}")
        return False
    
class DocumentPagination(pagination.PageNumberPagination):
    """RESTful API 標準分頁"""
    page_size = 10  # 預設每頁 10 筆
    page_size_query_param = 'size'  # 允許使用者調整每頁大小
    max_page_size = 50  # 最大 50 筆
    
class DocumentListCreateView(generics.ListCreateAPIView):
    """
    知識庫管理：
    - `GET` 查詢所有知識
    - `POST` 上傳新知識
    """
    queryset = Document.objects.all().order_by("-created_at")
    serializer_class = DocumentSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]

    def get(self, request, *args, **kwargs):
        """查詢所有文件"""
        queryset = self.filter_queryset(self.get_queryset())
        filename = request.GET.get("filename")
        if filename:
            queryset = queryset.filter(file__icontains=filename)

        # **將查詢結果轉換為 JSON**
        serializer = self.get_serializer(queryset, many=True)
        return Response({"data": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """上傳新知識文件（支援 PDF 多模態摘要）"""
        if "file" not in request.FILES:
            return Response({"error": "請上傳文件"}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES["file"]
        author = request.data.get("author", None)

        # 儲存檔案
        document = Document.objects.create(file=file, author_id=author)
        file_path = document.file.path  # Django 自動儲存路徑

        # 解析文件內容（PDF 頁碼 & 多模態摘要）
        if file.name.endswith(".pdf"):
            extracted_summaries = extract_element_from_pdf(file_path)
        else:
            return Response({"error": "僅支援 PDF 檔案"}, status=status.HTTP_400_BAD_REQUEST)

        # 合併所有摘要內容
        full_summary = "\n\n".join(
            extracted_summaries["text_summaries"] +
            extracted_summaries["table_summaries"] +
            extracted_summaries["image_summaries"]
        )

        # 存入資料庫
        document.content = full_summary
        document.save()

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)
    
class DocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    - `PUT` 更新檔案
    - `DELETE` 刪除檔案
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def put(self, request, *args, **kwargs):
        """更新知識文件，刪除舊文件並更新向量資料庫"""

        document = self.get_object()

        if "file" not in request.FILES:
            return Response({"error": "請上傳新文件"}, status=status.HTTP_400_BAD_REQUEST)

        old_file_path = os.path.join(settings.MEDIA_ROOT, document.file.name) if document.file else None
        old_title = os.path.basename(document.file.name) if document.file else None  
        # 從向量資料庫刪除舊文件向量
        delete_from_user_vectorstore(old_title)
        
        new_file = request.FILES["file"]
        # **先存入臨時檔案 (避免檔案遺失)**
        temp_file_path = os.path.join(settings.MEDIA_ROOT, "temp_" + new_file.name)
        with default_storage.open(temp_file_path, 'wb+') as destination:
            for chunk in new_file.chunks():
                destination.write(chunk)

        # **更新資料庫內容**
        response = self.update(request, *args, **kwargs)
        
        # **確保 Django 已更新 file 字段**
        document.refresh_from_db()

        if old_file_path and os.path.exists(old_file_path):
            os.remove(old_file_path)
            print(f"🗑 已刪除舊文件: {old_file_path}")

        # 解析文件內容（PDF 頁碼 & 多模態摘要）
        if file.name.endswith(".pdf"):
            extracted_summaries = extract_element_from_pdf(new_file_path)
        else:
            return Response({"error": "僅支援 PDF 檔案"}, status=status.HTTP_400_BAD_REQUEST)

        # 合併所有摘要內容
        full_summary = "\n\n".join(
            extracted_summaries["text_summaries"] +
            extracted_summaries["table_summaries"] +
            extracted_summaries["image_summaries"]
        )
        # 存入資料庫
        document.content = full_summary
        document.save()
        return response
    
    def delete(self, request, *args, **kwargs):
        """刪除特定知識庫文件，並同步刪除本地檔案 & 向量資料"""
        document = self.get_object()
        file_path = os.path.join(settings.MEDIA_ROOT, document.file.name) if document.file else None
        title = os.path.basename(document.file.name) if document.file else None

        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑 已刪除本地檔案: {file_path}")

        # **從向量資料庫刪除**
        delete_from_user_vectorstore(title)

        response = super().delete(request, *args, **kwargs)

        return response
    

# 🔹 **從 ChromaDB 進行檢索**
def retrieve_from_chroma(query):
    """從 `chroma_user_db` 進行檢索"""
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
        # ✅ 組合 `context` 作為 LLM 參考資料
    retrieved_context = "\n\n".join([doc["content"] for doc in retrieved_docs])
    return retrieved_context

# 🔹 **問答系統**
def ask(question,context):
    """檢索資料庫後，使用 OpenAI API 回答問題"""
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "你是一位針對文本內容進行答覆的助手"},
            {"role": "user", "content": f"請基於以下內容回答問題:\n{context}\n問題: {question}"}
        ],
        model=model_name,
        max_tokens=1024
    )
    
    return response.choices[0].message.content

class UserQueryView(generics.CreateAPIView):
    """LLM查詢，支援雲端/本地 LLM"""
    serializer_class = UserQuerySerializer  # 讓 Swagger 正確顯示 API 參數
    def create(self, request, *args, **kwargs):
        query = request.data.get("query")
        model_type = request.data.get("model_type", "cloud")  # 預設使用雲端 LLM
        
        if not query:
            return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

        print(f"🔍 [查詢請求] 收到查詢: {query}, 使用模型: {model_type}")
        context = retrieve_from_chroma(query)
        # 根據 `model_type` 呼叫不同 LLM
        '''
        if model_type == "cloud":
            try:
                answer = ask(query,context)
                print(f"🤖 [雲端 LLM 回應] {answer[:300]}...")
            except Exception as e:
                print(f"❌ [雲端 LLM 錯誤] {str(e)}")
                answer = "⚠️ 雲端 LLM 伺服器錯誤，請稍後再試。"
        '''
        # ✅ 根據 `model_type` 呼叫不同 LLM
        if model_type == "cloud":
            # ✅ 建立 LLM 查詢 Prompt
            prompt = PromptTemplate(
                template="根據以下背景資訊回答問題：\n\n{context}\n\n問題：{query}\n回答：",
                input_variables=["context", "query"]
            )
            formatted_prompt = prompt.format(context=context, query=query)
            print(f"📜 [Prompt] 送入 LLM:\n{formatted_prompt[:500]}...")
            try:
                answer = AzureLlamaAPI.ask(formatted_prompt)  
                print(f"🤖 [雲端 LLM 回應] {answer[:300]}...")
            except Exception as e:
                print(f"❌ [雲端 LLM 錯誤] {str(e)}")
                answer = "⚠️ 雲端 LLM 伺服器錯誤，請稍後再試。"
                
        elif model_type == "local":
            try:
                llm = Ollama(model="openchat:latest")  # 修正語法錯誤
                answer = llm.invoke(context)
                print(f"🤖 [本地 LLM 回應] {answer[:300]}...")
            except Exception as e:
                print(f"❌ [本地 LLM 錯誤] {str(e)}")
                answer = "⚠️ 本地 LLM 無法運行，請檢查設置。"

        else:
            return Response({"error": "Invalid model_type"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "query": query,
            "answer": answer,
            "retrieved_docs": context
        }, status=status.HTTP_200_OK)