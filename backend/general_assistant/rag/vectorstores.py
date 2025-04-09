from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ..models import Document
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import pdfplumber
import pytesseract
import docx
import PyPDF2
from pdf2image import convert_from_path
from unstructured.partition.pdf import partition_pdf
import ollama

# 設定詞嵌入模型
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# 設知識庫的儲存路徑
CHROMA_user_DB_PATH = "chroma_user_db"

# 初始化向量資料庫
user_vectorstore = Chroma(persist_directory=CHROMA_user_DB_PATH, embedding_function=embedder)

# 文字分割器
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

# 使用 Gemma3 模型摘要文字或表格
def summarize_text_or_table(element, element_type):
    print(element, ":", element_type)
    prompt = f"你是一位文本處理的助手，請根據以下內容進行摘要 {element_type}:\n{element}"
    response = ollama.chat(
        model='gemma3:4b',
        messages=[{
            'role': 'user',
            'content': prompt,
        }]
    )
    print(response.message.content)
    return response.message.content

# 使用 Gemma3 模型摘要圖片
def summarize_image(image_path):
    prompt = "你是一位針對影像和圖片進行摘要的助手，請詳細描述這張圖片的內容，若是圖表請說明其趨勢與關鍵數據"
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
        return f"\u274c Gemma3 \u5716\u50cf\u5206\u6790\u932f\u8aa4: {str(e)}"
    
# 將資料加入向量庫
def add_to_general_vectorstore(title, content, page_number=1, document_id=None):
    if not content.strip():
        print(f"⚠️ 跳過存入知識庫（內容為空）：{title}")
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
            "document_id": document_id
        } for i in range(len(chunks))
    ]
    user_vectorstore.add_texts(chunks, metadatas=metadata)
    print(f"✅ 已新增文件: {title}，共 {len(chunks)} 段落 (Page {page_number})")
    return True

def extract_element_from_pdf(file_path, knowledge_id=None):
    output_path = "./images"
    os.makedirs(output_path, exist_ok=True)

    raw_pdf_elements = partition_pdf(
        filename=file_path,
        extract_images_in_pdf=True,
        infer_table_structure=True,
        chunking_strategy="by_title",
        max_characters=4000,
        new_after_n_chars=3800,
        combine_text_under_n_chars=2000,
        extract_image_block_output_dir=output_path,
    )

    text_elements, table_elements, image_elements = [], [], []
    text_summaries, table_summaries, image_summaries = [], [], []

    for e in raw_pdf_elements:
        if 'CompositeElement' in repr(e):
            text_elements.append(e.text)
            summary = summarize_text_or_table(e.text, 'text')
            text_summaries.append(summary)
        elif 'Table' in repr(e):
            table_elements.append(e.text)
            summary = summarize_text_or_table(e.text, 'table')
            table_summaries.append(summary)

    for i in os.listdir(output_path):
        if i.endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(output_path, i)
            image_elements.append(image_path)
            summary = summarize_image(image_path)
            image_summaries.append(summary)

    for e, s in zip(text_elements, text_summaries):
        add_to_general_vectorstore(file_path, "Text Element", s, knowledge_id=knowledge_id)

    for e, s in zip(table_elements, table_summaries):
        add_to_general_vectorstore(file_path, "Table Element", s, knowledge_id=knowledge_id)

    for e, s in zip(image_elements, image_summaries):
        add_to_general_vectorstore(file_path, "Image Element", s, knowledge_id=knowledge_id)

    return {
        "text_summaries": text_summaries,
        "table_summaries": table_summaries,
        "image_summaries": image_summaries
    }
    
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
        chunks = list_from_general_vectorstore(document.id)
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
