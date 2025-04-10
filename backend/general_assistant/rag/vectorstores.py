import os
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForObjectDetection
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

# 向量庫初始化
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHROMA_user_DB_PATH = "chroma_user_db"
user_vectorstore = Chroma(persist_directory=CHROMA_user_DB_PATH, embedding_function=embedder)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

device = "cuda" if torch.cuda.is_available() else "cpu"
processor = AutoProcessor.from_pretrained("microsoft/table-transformer-detection", revision="no_timm")
model = AutoModelForObjectDetection.from_pretrained("microsoft/table-transformer-detection", revision="no_timm").to(device)

# 摘要

def summarize_text_or_table(element, element_type):
    prompt = f"你是一位文本處理的助手，請根據以下內容進行摘要 {element_type}：\n{element}"
    response = ollama.chat(
        model='gemma3:4b',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response.message.content

def summarize_image(image_path):
    prompt = "你是一位針對影像和圖片進行摘要的助手，請詳細描述這張圖片的內容，若是圖表請說明其趨勢與關鍵數據"
    try:
        response = ollama.chat(
            model='gemma3:4b',
            messages=[{'role': 'user', 'content': prompt, 'images': [image_path]}]
        )
        return response['message']['content']
    except Exception as e:
        return f"❌ 圖像分析錯誤: {str(e)}"

# 儲存向量庫

def add_to_general_vectorstore(title, content, page_number=1, document_id=None):
    if not content.strip():
        return False
    chunks = text_splitter.split_text(content)
    metadata = [{"title": title, "chunk_index": i, "page_number": page_number, "document_id": document_id} for i in range(len(chunks))]
    user_vectorstore.add_texts(chunks, metadatas=metadata)
    return True

# 表格偵測

def detect_and_crop_tables_from_image(image, page_index, output_dir="./table_images"):
    os.makedirs(output_dir, exist_ok=True)
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    target_sizes = torch.tensor([image.size[::-1]]).to(device)
    results = processor.post_process_object_detection(outputs, threshold=0.6, target_sizes=target_sizes)[0]

    saved_paths = []
    for i, box in enumerate(results["boxes"]):
        cropped = image.crop(box.tolist())
        save_path = os.path.join(output_dir, f"page{page_index+1}_table{i}.png")
        cropped.save(save_path)
        saved_paths.append((save_path, page_index+1))
    return saved_paths

# 圖片擷取

def extract_images_from_pdf(pdf_path, output_dir="./pdf_images"):
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    saved = []
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            path = os.path.join(output_dir, f"page{page_index+1}_img{img_index+1}.{image_ext}")
            with open(path, "wb") as f:
                f.write(image_bytes)
            saved.append((path, page_index+1))
    return saved

# 主流程：解析 PDF 中的所有元素

def extract_element_from_pdf(file_path, knowledge_id=None):
    text_summaries, table_summaries, image_summaries = [], [], []

    # 文字處理
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                summary = summarize_text_or_table(text, "text")
                full_text = f"[摘要]{summary}[原文]{text}"
                add_to_general_vectorstore("Text Element", full_text, page_number=i, document_id=knowledge_id)
                text_summaries.append(summary)

    # 表格處理（PDF 轉圖像後檢測）
    from pdf2image import convert_from_path
    images = convert_from_path(file_path)
    for page_index, img in enumerate(images):
        tables = detect_and_crop_tables_from_image(img, page_index)
        for table_path, pg in tables:
            summary = summarize_image(table_path)
            add_to_general_vectorstore("Table Image", summary, page_number=pg, document_id=knowledge_id)
            table_summaries.append(summary)

    # 圖片擷取 + 分析
    images_from_pdf = extract_images_from_pdf(file_path)
    for img_path, page_number in images_from_pdf:
        summary = summarize_image(img_path)
        add_to_general_vectorstore("Embedded Image", summary, page_number=page_number, document_id=knowledge_id)
        image_summaries.append(summary)

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
