import json

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


class VectorStoreHandler:
    def __init__(self, db_path="chroma_user_db", embed_model="BAAI/bge-m3"):
        self.embedder = HuggingFaceEmbeddings(
            model_name=embed_model,
            model_kwargs={"device": "cpu"}  # 強制使用 CPU
        )
        self.vectorstore = Chroma(persist_directory=db_path, embedding_function=self.embedder)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

    def add(self, content, media_type, page, document_id, source):
        if not content.strip():
            return False
        chunks = self.splitter.split_text(content)
        metadatas = [
            {
                "media_type": media_type,
                "page_number": page,
                "document_id": document_id,
                "source": source,
                "chunk_index": i
            } for i in range(len(chunks))
        ]
        self.vectorstore.add_texts(chunks, metadatas=metadatas)
        print(f"✅ 向量已儲存：{media_type} 第 {page} 頁，共 {len(chunks)} 段")
        return True

    def list(self, document_id):
        try:
            result = self.vectorstore._collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"]
            )
            return [
                {
                    "id": result["ids"][i],
                    "content": result["documents"][i],
                    "chunk_index": result["metadatas"][i].get("chunk_index", i),
                    "page_number": json.loads(result["metadatas"][i].get("page_number", "1")),  # ✅ 轉回 list
                    "media_type": result["metadatas"][i].get("media_type", "text"),
                    "source": json.loads(result["metadatas"][i].get("source", "\"\""))  # ✅ 轉回 list
                }
                for i in range(len(result["documents"]))
            ]
        except Exception as e:
            print(f"❌ 查詢失敗: {e}")
            return []

    def delete(self, document_id):
        try:
            self.vectorstore._collection.delete(where={"document_id": document_id})
            print(f"🗑 已刪除 document_id={document_id} 的向量資料")
            return True
        except Exception as e:
            print(f"❌ 刪除失敗: {e}")
            return False
        
    def update(self, chunk_id, new_content):
        try:
            meta = self.vectorstore._collection.get(
                ids=[chunk_id], include=["metadatas"]
            )["metadatas"][0]
            self.vectorstore._collection.delete(ids=[chunk_id])
            new_ids = self.vectorstore.add_texts([new_content], metadatas=[meta])
            return new_ids[0] if new_ids else None  # ✅ 回傳新的 chunk_id
        except Exception as e:
            print(f"❌ 更新失敗: {e}")
            return None
        
    def delete_chunk_by_id(self, chunk_id):
        try:
            self.vectorstore._collection.delete(ids=[chunk_id])
            print(f"🗑 已刪除 chunk_id={chunk_id} 的向量資料")
            return True
        except Exception as e:
            print(f"❌ 刪除 chunk 失敗: {e}")
            return False
    
    def get_chunks_by_document_id(self, document_id):
        try:
            result = self.vectorstore._collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"]
            )
            return [
                {
                    "id": result["ids"][i],
                    "content": result["documents"][i],
                    **result["metadatas"][i]
                } for i in range(len(result["documents"]))
            ]
        except Exception as e:
            print(f"❌ 查詢 chunk 發生錯誤: {e}")
            return []

    def get_chunk_metadata_by_id(self, chunk_id):
        try:
            result = self.vectorstore._collection.get(
                ids=[chunk_id],
                include=["metadatas"]
            )
            return result.get("metadatas", [None])[0]
        except Exception as e:
            print(f"❌ 查詢 chunk metadata 失敗: {e}")
            return None
