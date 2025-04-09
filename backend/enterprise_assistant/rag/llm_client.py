from rest_framework import generics, status, filters, pagination
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from ..serializers import KnowledgeSerializer,EnterpriseQuerySerializer,EnterpriseQueryResponseSerializer
import os
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from langchain_core.prompts import PromptTemplate
from ..azure_llama_api import AzureLlamaAPI
from .vectorstores import (
    enterprise_vectorstore,
)

class EnterpriseQueryView(generics.CreateAPIView):
    serializer_class = EnterpriseQuerySerializer

    def create(self, request, *args, **kwargs):
        query = request.data.get("query")
        model_type = request.data.get("model_type", "cloud")
        use_retrieval = request.data.get("use_retrieval", True)

        if not query:
            return Response({"error": "Query is required"}, status=status.HTTP_400_BAD_REQUEST)

        print(f"🔍 [查詢請求] 收到查詢: {query}, 使用模型: {model_type}, 啟用檢索: {use_retrieval}")

        context = ""
        retrieved_docs = []

        if use_retrieval:
            retriever = enterprise_vectorstore.as_retriever(search_kwargs={"k": 5})
            documents = retriever.get_relevant_documents(query)

            if not documents:
                return Response({
                    "query": query,
                    "answer": "⚠️ 未找到相關內容，請重新輸入問題或提供更多細節。",
                    "retrieved_docs": []
                }, status=status.HTTP_200_OK)

            print(f"✅ [檢索結果] 找到 {len(documents)} 份文件")

            for doc in documents:
                page_number = doc.metadata.get("page_number", "未知頁碼")
                title = doc.metadata.get("title", "未知文件")
                retrieved_docs.append({
                    "title": title,
                    "page_number": page_number,
                    "content": doc.page_content
                })

            context = "\n\n".join([doc["content"] for doc in retrieved_docs])

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