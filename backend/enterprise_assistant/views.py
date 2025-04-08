from rest_framework import generics, status, filters, pagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import Knowledge
from .serializers import KnowledgeSerializer,EnterpriseQuerySerializer,EnterpriseQueryResponseSerializer
import pdfplumber
import pytesseract
import docx
import PyPDF2
from pdf2image import convert_from_path
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from langchain_core.prompts import PromptTemplate
from .azure_llama_api import AzureLlamaAPI

def extract_text_from_file(file_path):
    """ 根據文件類型解析內容 """
    text = ""

    if file_path.endswith(".pdf"):
        # **方法 1：使用 pdfplumber 解析**
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

        # **方法 2：使用 PyPDF2 解析**
        if not text.strip():
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

        # **方法 3：使用 OCR 解析圖片 PDF**
        if not text.strip():
            images = convert_from_path(file_path)
            for img in images:
                text += pytesseract.image_to_string(img, lang="chi_tra") + "\n"

    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"

    print("解析內容前 500 字:", text[:500])  # 測試是否有讀取內容
    return text.strip()

def extract_text_from_pdf_with_pages(file_path):
    """解析 PDF，並返回 (頁碼, 文字內容) 列表"""
    extracted_pages = []
    
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                extracted_pages.append((i, text))

    if not extracted_pages:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append((i, page_text))

    print(f"✅ 解析 {len(extracted_pages)} 頁 PDF 內容")
    return extracted_pages

# 設定詞嵌入模型
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# 設定企業內部知識庫的儲存路徑
CHROMA_ENTERPRISE_DB_PATH = "chroma_enterprise_db"

# 初始化向量資料庫
enterprise_vectorstore = Chroma(persist_directory=CHROMA_ENTERPRISE_DB_PATH, embedding_function=embedder)

# 文字分割器
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

def add_to_enterprise_vectorstore(title, content, page_number=1):
    """將文件內容切割後存入向量資料庫，並記錄頁碼"""
    global enterprise_vectorstore

    if not content.strip():
        print(f"⚠️ 跳過存入企業知識庫（內容為空）：{title}")
        return False

    # 拆分文本
    chunks = text_splitter.split_text(content)
    if not chunks:
        print(f"⚠️ 無法拆分文本，跳過存入 ChromaDB（{title}）")
        return False

    # 設定 metadata，包含文件名稱與頁碼
    metadata = [{"title": title, "chunk_index": i, "page_number": page_number} for i in range(len(chunks))]

    # 存入向量資料庫
    enterprise_vectorstore.add_texts(chunks, metadatas=metadata)
    print(f"✅ 企業知識庫已新增: {title}，共 {len(chunks)} 段落 (Page {page_number})")
    return True

def delete_from_enterprise_vectorstore(title):
    """
    從 ChromaDB 刪除對應 `title` 的向量資料
    """
    try:
        all_vectors = enterprise_vectorstore._collection.get(include=["metadatas"])

        if all_vectors and "metadatas" in all_vectors:
            matching_vectors = [meta for meta in all_vectors["metadatas"] if meta.get("title") == title]

            if matching_vectors:
                print(f"🔍 找到 `{title}` 的 {len(matching_vectors)} 筆向量資料，準備刪除...")
                enterprise_vectorstore._collection.delete(where={"title": title})
                print(f"✅ 已成功刪除 `{title}` 的向量資料")
                return True
            else:
                print(f"⚠️ 未找到 `{title}` 的向量資料，無需刪除")
                return False
    except Exception as e:
        print(f"❌ 刪除 `{title}` 的向量資料失敗: {e}")
        return False

'''
def rebuild_vectorstore():
    """清空並重新建置企業知識庫的 ChromaDB"""
    global enterprise_vectorstore
    # 取得所有向量的 metadata
    all_vectors = enterprise_vectorstore._collection.get(include=["metadatas"])

    if all_vectors and "metadatas" in all_vectors:
        all_titles = {meta["title"] for meta in all_vectors["metadatas"] if "title" in meta}
        # 批量刪除
        for title in all_titles:
            enterprise_vectorstore._collection.delete(where={"title": title})
            print(f"✅ 已刪除向量資料: {title}")
        print("⚠️ 已成功清空使用者向量資料庫！")

    # **重新載入所有 Knowledge 資料**
    all_documents = Knowledge.objects.all()
    if not all_documents.exists():
        print("⚠️ 沒有企業文件，無需重建向量資料庫。")
        return

    for doc in all_documents:
        title = os.path.basename(doc.file.name)  # 確保與刪除時的名稱一致
        add_to_enterprise_vectorstore(title, doc.content)

    print(f"✅ 已成功重新載入 {len(all_documents)} 份企業知識庫文件！")
'''

class KnowledgePagination(pagination.PageNumberPagination):
    """RESTful API 標準分頁"""
    page_size = 10  # 預設每頁 10 筆
    page_size_query_param = 'size'  # 允許使用者調整每頁大小
    max_page_size = 50  # 最大 50 筆

class KnowledgeListCreateView(generics.ListCreateAPIView):
    """
    知識庫管理：
    - `GET` 查詢所有知識
    - `POST` 上傳新知識
    """
    queryset = Knowledge.objects.all().order_by("-created_at")
    serializer_class = KnowledgeSerializer
    pagination_class = None
    parser_classes = (MultiPartParser, FormParser)
    filter_backends = [filters.SearchFilter]
    search_fields = ["file", "department"]

    def get(self, request, *args, **kwargs):
        """查詢所有知識（支援 title & department 過濾）"""
        queryset = self.filter_queryset(self.get_queryset())

        title = request.GET.get("title")
        department = request.GET.get("department")

        if title:
            queryset = queryset.filter(file__icontains=title)
        if department:
            queryset = queryset.filter(department__icontains=department)

        # **將查詢結果轉換為 JSON**
        serializer = self.get_serializer(queryset, many=True)

        return Response({"data": serializer.data, "count": len(serializer.data)}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """上傳新知識文件（支援 PDF 頁碼標記）"""
        if "file" not in request.FILES:
            return Response({"error": "請上傳文件"}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES["file"]
        department = request.data.get("department", "")
        author = request.data.get("author", None)

        # **儲存檔案**
        knowledge = Knowledge.objects.create(file=file, department=department, author_id=author)
        file_path = knowledge.file.path  # Django 自動儲存路徑

        # **解析文件內容（解析 PDF 頁碼）**
        if file.name.endswith(".pdf"):
            extracted_pages = extract_text_from_pdf_with_pages(file_path)
        else:
            extracted_pages = [(1, extract_text_from_file(file_path))]  # 預設為第 1 頁

        # **存入資料庫**
        knowledge.content = "\n\n".join([text for _, text in extracted_pages])
        knowledge.save()

        # **存入向量資料庫**
        for page_number, page_content in extracted_pages:
            add_to_enterprise_vectorstore(file.name, page_content, page_number)

        return Response(KnowledgeSerializer(knowledge).data, status=status.HTTP_201_CREATED)

class KnowledgeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    - `PUT` 更新檔案
    - `DELETE` 刪除檔案
    """
    queryset = Knowledge.objects.all()
    serializer_class = KnowledgeSerializer
    parser_classes = (MultiPartParser, FormParser)

    def put(self, request, *args, **kwargs):
        """更新知識文件，刪除舊文件並更新向量資料庫"""

        knowledge = self.get_object()

        if "file" not in request.FILES:
            return Response({"error": "請上傳新文件"}, status=status.HTTP_400_BAD_REQUEST)

        old_file_path = os.path.join(settings.MEDIA_ROOT, knowledge.file.name) if knowledge.file else None
        old_title = os.path.basename(knowledge.file.name) if knowledge.file else None  

        new_file = request.FILES["file"]

        # **先存入臨時檔案 (避免檔案遺失)**
        temp_file_path = os.path.join(settings.MEDIA_ROOT, "temp_" + new_file.name)
        with default_storage.open(temp_file_path, 'wb+') as destination:
            for chunk in new_file.chunks():
                destination.write(chunk)

        # **更新資料庫內容**
        response = self.update(request, *args, **kwargs)

        # **確保 Django 已更新 file 字段**
        knowledge.refresh_from_db()

        if old_file_path and os.path.exists(old_file_path):
            os.remove(old_file_path)
            print(f"🗑 已刪除舊文件: {old_file_path}")

        new_file_path = knowledge.file.path  # Django 自動儲存的新路徑
        if new_file.name.endswith(".pdf"):
            extracted_pages = extract_text_from_pdf_with_pages(new_file_path)
        else:
            extracted_pages = [(1, extract_text_from_file(new_file_path))]

        knowledge.content = "\n\n".join([text for _, text in extracted_pages])
        knowledge.save()

        # **從向量資料庫刪除舊文件向量**
        delete_from_enterprise_vectorstore(old_title)

        # **存入新的向量資料庫**
        for page_number, page_content in extracted_pages:
            add_to_enterprise_vectorstore(knowledge.file.name, page_content, page_number)

        return response
    
    def delete(self, request, *args, **kwargs):
        """刪除特定知識庫文件，並同步刪除本地檔案 & 向量資料"""
        knowledge = self.get_object()
        file_path = os.path.join(settings.MEDIA_ROOT, knowledge.file.name) if knowledge.file else None
        title = os.path.basename(knowledge.file.name) if knowledge.file else None

        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑 已刪除本地檔案: {file_path}")

        # **從向量資料庫刪除**
        delete_from_enterprise_vectorstore(title)

        response = super().delete(request, *args, **kwargs)

        return response
    
    
class EnterpriseQueryView(generics.CreateAPIView):
    """企業知識庫查詢，支援雲端/本地 LLM，並可選擇是否使用向量檢索"""

    serializer_class = EnterpriseQuerySerializer  # 讓 Swagger 正確顯示 API 參數
    def create(self, request, *args, **kwargs):
        query = request.data.get("query")
        model_type = request.data.get("model_type", "cloud")  # 預設使用雲端 LLM
        use_retrieval = request.data.get("use_retrieval", True)  # 預設開啟檢索

        if not query:
            return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

        print(f"🔍 [查詢請求] 收到查詢: {query}, 使用模型: {model_type}, 啟用檢索: {use_retrieval}")

        context = ""
        retrieved_docs = []

        if use_retrieval:
            # ✅ 取得企業知識庫的相關文件
            retriever = enterprise_vectorstore.as_retriever(search_kwargs={"k": 5})
            documents = retriever.get_relevant_documents(query)

            if not documents:
                return Response({
                    "query": query,
                    "answer": "⚠️ 未找到相關內容，請重新輸入問題或提供更多細節。",
                    "retrieved_docs": []
                }, status=status.HTTP_200_OK)

            print(f"✅ [檢索結果] 找到 {len(documents)} 份文件")

            # ✅ 提取 `page_number` 和 `title`
            for doc in documents:
                page_number = doc.metadata.get("page_number", "未知頁碼")
                title = doc.metadata.get("title", "未知文件")
                retrieved_docs.append({
                    "title": title,
                    "page_number": page_number,
                    "content": doc.page_content
                })

            # ✅ 組合 `context` 作為 LLM 參考資料
            context = "\n\n".join([doc["content"] for doc in retrieved_docs])

        # ✅ 建立 LLM 查詢 Prompt
        if use_retrieval:
            prompt = PromptTemplate(
                template="根據以下背景資訊回答問題：\n\n{context}\n\n問題：{query}\n回答：",
                input_variables=["context", "query"]
            )
            formatted_prompt = prompt.format(context=context, query=query)
        else:
            prompt = PromptTemplate(
                template="請回答以下問題：\n\n問題：{query}\n回答：",
                input_variables=["query"]
            )
            formatted_prompt = prompt.format(query=query)

        print(f"📜 [Prompt] 送入 LLM:\n{formatted_prompt[:500]}...")

        # ✅ 根據 `model_type` 呼叫不同 LLM
        if model_type == "cloud":
            try:
                answer = AzureLlamaAPI.ask(formatted_prompt)
                print(f"🤖 [雲端 LLM 回應] {answer[:300]}...")
            except Exception as e:
                print(f"❌ [雲端 LLM 錯誤] {str(e)}")
                answer = "⚠️ 雲端 LLM 伺服器錯誤，請稍後再試。"

        elif model_type == "local":
            try:
                llm = Ollama(model="openchat:latest")
                answer = llm.invoke(formatted_prompt)
                print(f"🤖 [本地 LLM 回應] {answer[:300]}...")
            except Exception as e:
                print(f"❌ [本地 LLM 錯誤] {str(e)}")
                answer = "⚠️ 本地 LLM 無法運行，請檢查設置。"

        else:
            return Response({"error": "Invalid model_type"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "query": query,
            "answer": answer,
            "retrieved_docs": retrieved_docs if use_retrieval else []
        }, status=status.HTTP_200_OK)
