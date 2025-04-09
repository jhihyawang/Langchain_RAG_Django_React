# ✅ 整合後：保留 A 的解析與儲存邏輯，改為 B 的架構格式

import os
import base64
import ollama
from unstructured.partition.pdf import partition_pdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# 設定詞嵌入模型與向量儲存路徑
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHROMA_USER_DB_PATH = "chroma_user_db"
user_vectorstore = Chroma(persist_directory=CHROMA_USER_DB_PATH, embedding_function=embedder)
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
def add_to_user_vectorstore(file_path, title, content, page_number=1, knowledge_id=None):
    if not content.strip():
        print(f"\u26a0\ufe0f 跳過存入（內容為空）：{title}")
        return False
    chunks = text_splitter.split_text(content)
    if not chunks:
        print(f"\u26a0\ufe0f 無法拆分文本，跳過存入 ChromaDB（{title}）")
        return False
    metadata = [
        {
            "filename": file_path,
            "title": title,
            "chunk_index": i,
            "page_number": page_number,
            "knowledge_id": knowledge_id
        } for i in range(len(chunks))
    ]
    user_vectorstore.add_texts(chunks, metadatas=metadata)
    print(f"\u2705 {file_path}已存入 ChromaDB: {title}，共 {len(chunks)} 段落 (Page {page_number})")
    return True

# PDF 文件解析：使用 A 的完整方式

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
        add_to_user_vectorstore(file_path, "Text Element", s, knowledge_id=knowledge_id)

    for e, s in zip(table_elements, table_summaries):
        add_to_user_vectorstore(file_path, "Table Element", s, knowledge_id=knowledge_id)

    for e, s in zip(image_elements, image_summaries):
        add_to_user_vectorstore(file_path, "Image Element", s, knowledge_id=knowledge_id)

    return {
        "text_summaries": text_summaries,
        "table_summaries": table_summaries,
        "image_summaries": image_summaries
    }

