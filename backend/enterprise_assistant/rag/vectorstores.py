from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..models import Knowledge
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import pdfplumber
import pytesseract
import docx
import PyPDF2
from pdf2image import convert_from_path

# 設定詞嵌入模型
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# 設定企業內部知識庫的儲存路徑
CHROMA_ENTERPRISE_DB_PATH = "chroma_enterprise_db"

# 初始化向量資料庫
enterprise_vectorstore = Chroma(persist_directory=CHROMA_ENTERPRISE_DB_PATH, embedding_function=embedder)

# 文字分割器
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

def extract_text_from_file(file_path):
    text = ""
    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        if not text.strip():
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        if not text.strip():
            images = convert_from_path(file_path)
            for img in images:
                text += pytesseract.image_to_string(img, lang="chi_tra") + "\n"
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    print("解析內容前 500 字:", text[:500])
    return text.strip()

def extract_text_from_pdf_with_pages(file_path):
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

def add_to_enterprise_vectorstore(title, content, page_number=1, knowledge_id=None):
    if not content.strip():
        print(f"⚠️ 跳過存入企業知識庫（內容為空）：{title}")
        return False
    chunks = text_splitter.split_text(content)
    if not chunks:
        print(f"⚠️ 無法拆分文本，跳過存入 ChromaDB（{title}）")
        return False
    metadata = [
        {
            "title": title,
            "chunk_index": i,
            "page_number": page_number,
            "knowledge_id": knowledge_id
        } for i in range(len(chunks))
    ]
    enterprise_vectorstore.add_texts(chunks, metadatas=metadata)
    print(f"✅ 企業知識庫已新增: {title}，共 {len(chunks)} 段落 (Page {page_number})")
    return True

def delete_from_enterprise_vectorstore(knowledge_id):
    try:
        enterprise_vectorstore._collection.delete(where={"knowledge_id": knowledge_id})
        print(f"✅ 已刪除 knowledge_id={knowledge_id} 的向量資料")
        return True
    except Exception as e:
        print(f"❌ 刪除向量資料失敗: {e}")
        return False

def list_from_enterprise_vectorstore(knowledge_id):
    try:
        results = enterprise_vectorstore._collection.get(
            where={"knowledge_id": knowledge_id},
            include=["documents", "metadatas"]
        )
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])
        if not documents:
            print(f"⚠️ 未找到 knowledge_id={knowledge_id} 的向量資料")
            return []
        chunks = []
        for i in range(len(documents)):
            metadata = metadatas[i] if i < len(metadatas) else {}
            chunks.append({
                "id": ids[i],
                "chunk_index": metadata.get("chunk_index", i),
                "page_number": metadata.get("page_number", None),
                "content": documents[i]
            })
        print(f"✅ 找到 {len(chunks)} 筆 knowledge_id={knowledge_id} 的 chunks")
        return chunks
    except Exception as e:
        print(f"❌ 查詢 knowledge_id={knowledge_id} 的向量資料失敗: {e}")
        return []

class ChunkListCreateView(APIView):
    def get(self, request, pk):
        knowledge = get_object_or_404(Knowledge, pk=pk)
        chunks = list_from_enterprise_vectorstore(knowledge.id)
        return Response({
            "knowledge_id": knowledge.id,
            "title": os.path.basename(knowledge.file.name) if knowledge.file else "",
            "chunks": chunks
        }, status=status.HTTP_200_OK)

class ChunkDetailView(APIView):
    """
    - `PUT` 更新單一 chunk
    - `DELETE` 刪除單一 chunk
    """

    def put(self, request, chunk_id):
        content = request.data.get("content")
        if not content:
            return Response({"error": "請提供新的 content"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 查出原 metadata
            existing = enterprise_vectorstore._collection.get(
                ids=[chunk_id],
                include=["metadatas"]
            )

            if not existing["metadatas"]:
                return Response({"error": "找不到 chunk"}, status=status.HTTP_404_NOT_FOUND)

            metadata = existing["metadatas"][0]

            # 刪除舊的向量
            enterprise_vectorstore._collection.delete(ids=[chunk_id])

            # 加入新的向量（新內容 + 舊 metadata）
            enterprise_vectorstore.add_texts(
                [content],
                metadatas=[metadata]
            )

            # 嘗試更新 Knowledge 的 updated_at 時間
            knowledge_id = metadata.get("knowledge_id")
            if knowledge_id:
                from ..models import Knowledge  # 避免循環 import 問題
                from django.utils.timezone import now

                try:
                    knowledge = Knowledge.objects.get(id=knowledge_id)
                    # 更新 vectorstore 後，重新取得第一個 chunk 當作 content
                    chunks = list_from_enterprise_vectorstore(knowledge.id)
                    first_chunk = chunks[0]["content"] if chunks else ""
                    knowledge.content = first_chunk
                    knowledge.updated_at = now()
                    knowledge.chunk = len(chunks)
                    knowledge.save(update_fields=["content", "chunk", "updated_at"])
                    print(f"📌 已同步更新 Knowledge ID={knowledge_id} 的修改時間")
                except Knowledge.DoesNotExist:
                    print(f"⚠️ 無法找到 Knowledge ID={knowledge_id}，無法同步時間")

            return Response({"message": "✅ 已更新 chunk"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"更新失敗：{str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, chunk_id):
        try:
            # 先取得 metadata（可選，純粹為了 log）
            metadata = enterprise_vectorstore._collection.get(
                ids=[chunk_id],
                include=["metadatas"]
            ).get("metadatas", [{}])[0]

            knowledge_id = metadata.get("knowledge_id", "未知")
            enterprise_vectorstore._collection.delete(ids=[chunk_id])
            print(f"🗑 已刪除 chunk（ID: {chunk_id}, knowledge_id: {knowledge_id}）")

            return Response({"message": "✅ 已刪除 chunk"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": f"刪除失敗：{str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
