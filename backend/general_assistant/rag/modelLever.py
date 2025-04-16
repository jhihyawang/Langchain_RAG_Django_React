# modelLever_django.py
# ✅ 重新整理為 Django-friendly 的版本，移除 streamlit 依賴

from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.chat_models import ChatOllama
from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain_community.vectorstores import Chroma
from langchain.storage import InMemoryStore

import base64
import uuid
import os
from PIL import Image

# === 模型建立 ===
def create_model(service: str, model: str, temp: float):
    if service == "Ollama":
        return ChatOllama(model=model, temperature=temp)
    else:
        raise ValueError("不支援的模型服務")

# === 圖像編碼 ===
def encode_image_base64(img_path):
    with open(img_path, "rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")

# === 圖片摘要處理 ===
def interpret_image(img_base64, service="Ollama", model="gemma3:4b"):
    if service != "Ollama":
        raise NotImplementedError("目前僅支援 Ollama 圖片摘要")

    image_path = f"/tmp/{uuid.uuid4().hex}.jpg"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(img_base64))

    prompt = "你是一位針對影像和圖片進行摘要的助手，請詳細描述這張圖片的內容，若是圖表請說明其趨勢與關鍵數據"
    try:
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt, 'images': [image_path]}]
        )
        return response['message']['content']
    except Exception as e:
        return f"❌ 圖像分析錯誤: {str(e)}"
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

# === 使用 ollama.chat 的文字/表格摘要 ===
def summarize_element_ollama(content, element_type, model="gemma3:4b"):
    prompt = f"你是一位文本處理的助手，請根據以下內容進行摘要 {element_type}：\n{content}"
    response = ollama.chat(
        model=model,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response['message']['content']

# === 多模態摘要處理 ===
def summarize_data_from_pdf(extract_data, service="Ollama", model="gemma3:4b", temp=0.8):
    text_summaries = [summarize_element_ollama(t, "text", model=model) for t in extract_data.get("textElements", [])]
    table_summaries = [summarize_element_ollama(t, "table", model=model) for t in extract_data.get("tableElements", [])]

    image_summaries = []
    for path in extract_data.get("imgPath", []):
        image_base64 = encode_image_base64(path)
        result = interpret_image(image_base64, service, model)
        image_summaries.append(result)

    return {
        "textSummaries": {"mediatype": "text", "payload": extract_data.get("textElements", []), "summary": text_summaries},
        "tableSummaries": {"mediatype": "text", "payload": extract_data.get("tableElements", []), "summary": table_summaries},
        "imageSummaries": {"mediatype": "image", "payload": extract_data.get("imgPath", []), "summary": image_summaries},
    }


# === 可選：建立本地記憶體用的 retriever（非寫入向量庫） ===
def retrieverGenerator(summarized_data):
    vectorstore = Chroma(collection_name="summaries", embedding_function=OpenAIEmbeddings())
    docstore = InMemoryStore()
    id_key = "rec_id"
    retriever = MultiVectorRetriever(vectorstore=vectorstore, docstore=docstore, id_key=id_key)

    for category in summarized_data:
        summary = summarized_data[category]["summary"]
        payload = summarized_data[category]["payload"]
        media_type = summarized_data[category]["mediatype"]
        doc_ids = [str(uuid.uuid4()) for _ in summary]

        documents = []
        for i, s in enumerate(summary):
            metadata = {id_key: doc_ids[i], "mediaType": media_type}
            if media_type == "image":
                metadata["source"] = payload[i]
            documents.append(Document(page_content=s, metadata=metadata))

        retriever.vectorstore.add_documents(documents)
        retriever.docstore.mset(list(zip(doc_ids, payload)))

    return retriever
