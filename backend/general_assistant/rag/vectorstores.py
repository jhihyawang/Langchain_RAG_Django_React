import os
from PIL import Image
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from ..models import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import ollama
import fitz  # PyMuPDF
import pdfplumber
import io
from PIL import Image
from pdf2image import convert_from_path  # ← 改為處理本地路徑

# 向量庫初始化
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHROMA_user_DB_PATH = "chroma_user_db"
user_vectorstore = Chroma(persist_directory=CHROMA_user_DB_PATH, embedding_function=embedder)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

# 儲存向量庫
def add_to_general_vectorstore(content, page_number=1, document_id=None, media_type="text", source=None):
    if not content.strip():
        return False
    chunks = text_splitter.split_text(content)
    metadata = []
    for i in range(len(chunks)):
        meta = {
            "chunk_index": i,
            "page_number": page_number,
            "document_id": document_id,
            "mediaType": media_type,
        }
        if source:
            meta["source"] = source
        metadata.append(meta)
    user_vectorstore.add_texts(chunks, metadatas=metadata)
    return True

    
def delete_from_general_vectorstore(document_id):
    try:
        user_vectorstore._collection.delete(where={"document_id": document_id})
        print(f"✅ 已刪除 document_id={document_id} 的向量資料")
        return True
    except Exception as e:
        print(f"❌ 刪除向量資料失敗: {e}")
        return False

def list_from_general_vectorstore(document_id):
    try:
        results = user_vectorstore._collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"]
        )
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])
        if not documents:
            print(f"⚠️ 未找到 document_id={document_id} 的向量資料")
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
        print(f"✅ 找到 {len(chunks)} 筆 document_id={document_id} 的 chunks")
        return chunks
    except Exception as e:
        print(f"❌ 查詢 document_id={document_id} 的向量資料失敗: {e}")
        return []

class ChunkListCreateView(APIView):
    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        results = user_vectorstore._collection.get(
            where={"document_id": document.id},
            include=["documents", "metadatas"]
        )
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])

        chunks = []
        for i in range(len(documents)):
            metadata = metadatas[i] if i < len(metadatas) else {}
            chunks.append({
                "id": ids[i],
                "chunk_index": metadata.get("chunk_index", i),
                "page_number": metadata.get("page_number", None),
                "content": documents[i],
                "mediaType": metadata.get("mediaType", "text"),
                "source": metadata.get("source", None)
            })
            
        return Response({
            "document_id": document.id,
            "title": os.path.basename(document.file.name) if document.file else "",
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
            existing = user_vectorstore._collection.get(
                ids=[chunk_id],
                include=["metadatas"]
            )

            if not existing["metadatas"]:
                return Response({"error": "找不到 chunk"}, status=status.HTTP_404_NOT_FOUND)

            metadata = existing["metadatas"][0]

            # 刪除舊的向量
            user_vectorstore._collection.delete(ids=[chunk_id])

            # 加入新的向量（新內容 + 舊 metadata）
            user_vectorstore.add_texts(
                [content],
                metadatas=[metadata]
            )

            # 嘗試更新 document 的 updated_at 時間
            document_id = metadata.get("document_id")
            if document_id:
                from ..models import Document  # 避免循環 import 問題
                from django.utils.timezone import now

                try:
                    document = Document.objects.get(id=document_id)
                    # 更新 vectorstore 後，重新取得第一個 chunk 當作 content
                    chunks = list_from_general_vectorstore(document.id)
                    first_chunk = chunks[0]["content"] if chunks else ""
                    document.content = first_chunk
                    document.updated_at = now()
                    document.chunk = len(chunks)
                    document.save(update_fields=["content", "chunk", "updated_at"])
                    print(f"📌 已同步更新 document ID={document_id} 的修改時間")
                except Document.DoesNotExist:
                    print(f"⚠️ 無法找到 document ID={document_id}，無法同步時間")

            return Response({"message": "✅ 已更新 chunk"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"更新失敗：{str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, chunk_id):
        try:
            # 先取得 metadata（可選，純粹為了 log）
            metadata = user_vectorstore._collection.get(
                ids=[chunk_id],
                include=["metadatas"]
            ).get("metadatas", [{}])[0]

            document_id = metadata.get("document_id", "未知")
            user_vectorstore._collection.delete(ids=[chunk_id])
            print(f"🗑 已刪除 chunk（ID: {chunk_id}, document_id: {document_id}）")

            return Response({"message": "✅ 已刪除 chunk"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": f"刪除失敗：{str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)