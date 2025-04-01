import os
import uuid
import base64
import chromadb
from unstructured.partition.pdf import partition_pdf
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI

# 🔹 設定 OpenAI API
token = "#"
endpoint = "https://models.inference.ai.azure.com"
model_name = "gpt-4o"

client = OpenAI(
    base_url=endpoint,
    api_key=token,
)

# 🔹 設定向量資料庫 (改用 `chroma_user_db`)
CHROMA_USER_DB_PATH = "chroma_user_db"
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
chroma_client = chromadb.PersistentClient(path=CHROMA_USER_DB_PATH)
user_collection = chroma_client.get_or_create_collection(name="user_knowledge")

# 🔹 設定文字切割器
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)

# 🔹 解析 PDF，提取 文字 / 表格 / 圖片
output_path = "./images"
raw_pdf_elements = partition_pdf(
    filename="/Users/joy/LLM/proj.pdf",
    extract_images_in_pdf=True,
    infer_table_structure=True,
    chunking_strategy="by_title",
    max_characters=4000,
    new_after_n_chars=3800,
    combine_text_under_n_chars=2000,
    extract_image_block_output_dir=output_path,
)

# 🔹 文字 & 表格摘要
text_elements, table_elements = [], []
text_summaries, table_summaries = [], []

def summarize_text_or_table(element, element_type):
    """使用 OpenAI API 來生成摘要"""
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize the following {element_type}:\n{element}"}
        ],
        model=model_name,
        max_tokens=1024
    )
    return response.choices[0].message.content

for e in raw_pdf_elements:
    if 'CompositeElement' in repr(e):
        text_elements.append(e.text)
        summary = summarize_text_or_table(e.text, 'text')
        text_summaries.append(summary)

    elif 'Table' in repr(e):
        table_elements.append(e.text)
        summary = summarize_text_or_table(e.text, 'table')
        table_summaries.append(summary)

# 🔹 圖片摘要
def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def summarize_image(image_path):
    """使用 OpenAI API 來分析圖片"""
    encoded_image = encode_image(image_path)
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant that describes images."},
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
    return response.choices[0].message.content

image_elements, image_summaries = [], []

for i in os.listdir(output_path):
    if i.endswith(('.png', '.jpg', '.jpeg')):
        image_path = os.path.join(output_path, i)
        image_elements.append(image_path)
        summary = summarize_image(image_path)
        image_summaries.append(summary)

# 🔹 **存入 ChromaDB**
def add_to_chroma_vectorstore(title, content, page_number=1):
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
    metadata = [{"title": title, "chunk_index": i, "page_number": page_number} for i in range(len(chunks))]

    # 轉換向量並存入
    vectors = [embedder.embed_query(chunk) for chunk in chunks]
    user_collection.add(
        ids=[str(uuid.uuid4()) for _ in range(len(chunks))],
        embeddings=vectors,
        metadatas=metadata,
        documents=chunks
    )

    print(f"✅ 已存入 ChromaDB: {title}，共 {len(chunks)} 段落 (Page {page_number})")
    return True

# **存入 文字 / 表格 / 圖片**
for e, s in zip(text_elements, text_summaries):
    add_to_chroma_vectorstore("Text Element", s)

for e, s in zip(table_elements, table_summaries):
    add_to_chroma_vectorstore("Table Element", s)

for e, s in zip(image_elements, image_summaries):
    add_to_chroma_vectorstore("Image Element", s)

# 🔹 **從 ChromaDB 進行檢索**
def retrieve_from_chroma(question):
    """從 `chroma_user_db` 進行檢索"""
    query_vector = embedder.embed_query(question)
    results = user_collection.query(
        query_embeddings=[query_vector],
        n_results=5
    )
    
    retrieved_context = ""
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        retrieved_context += f"[{meta['title']}]\n{doc}\n"

    return retrieved_context

# 🔹 **問答系統**
def answer(question):
    """檢索資料庫後，使用 OpenAI API 回答問題"""
    context = retrieve_from_chroma(question)

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant that answers questions based on given context."},
            {"role": "user", "content": f"Answer the question based on the following context:\n{context}\nQuestion: {question}"}
        ],
        model=model_name,
        max_tokens=1024
    )
    
    return response.choices[0].message.content

# 🔹 **測試問答**
if __name__ == "__main__":
    question = "112年哪一種災害類型死亡人數最多？"
    answer_text = answer(question)
    print(f"🤖 回答: {answer_text}")