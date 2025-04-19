# views/query.py

from common.modules.ai.llm_factory import LlmFactory
from common.modules.processor.vector_store import VectorStoreHandler
from drf_spectacular.utils import extend_schema
from enterprise_assistant.serializers import (
    EnterpriseQueryResponseSerializer, EnterpriseQuerySerializer)
from langchain_core.prompts import PromptTemplate
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(
    request=EnterpriseQuerySerializer,
    responses=EnterpriseQueryResponseSerializer,
    summary="查詢企業知識庫 (支援 RAG)",
    description="使用者可輸入問題，選擇是否啟用檢索與使用本地或雲端模型，系統將回覆根據知識庫文件的回答。"
)

class EnterpriseQueryView(CreateAPIView):
    serializer_class = EnterpriseQuerySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]
        model_type = serializer.validated_data["model_type"]
        model_name = serializer.validated_data["model_name"]
        use_retrieval = serializer.validated_data["use_retrieval"]

        retrieved_docs = []
        context = ""
        vectorstore = VectorStoreHandler("chroma_user_db")

        if use_retrieval:
            retriever = vectorstore.vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5, "fetch_k": 20})
            documents = retriever.invoke(query)

            if documents:
                print(f"✅ [檢索結果] 找到 {len(documents)} 份文件")
                for doc in documents:
                    page_number = doc.metadata.get("page_number", "未知頁碼")
                    title = doc.metadata.get("title", "未知文件")
                    retrieved_docs.append({
                        "title": title,
                        "page_number": page_number,
                        "content": doc.page_content
                    })
                    print(f"page_number {page_number} / title {title}: {doc.page_content[:100]}...")
                context = "\n\n".join([doc["content"] for doc in retrieved_docs])
            else:
                answer = "我不知道，我沒有被提供相關的知識文件，你可以試試關閉檢索功能再問我問題!!感恩!!"
                response_data = {
                    "query": query,
                    "answer": answer,
                    "retrieved_docs": []
                }
                response_serializer = EnterpriseQueryResponseSerializer(response_data)
                return Response(response_serializer.data, status=status.HTTP_200_OK)

        prompt_template = PromptTemplate(
            template="根據以下背景資訊回答問題：\n\n{context}\n\n問題：{query}\n回答：",
            input_variables=["context", "query"]
        ) if use_retrieval else PromptTemplate(
            template="請根據你的知識範圍回答問題：\n\n問題：{query}\n回答：",
            input_variables=["query"]
        )

        formatted_prompt = prompt_template.format(context=context, query=query) if use_retrieval else prompt_template.format(query=query)
        print(f"📜 [Prompt] 送入 LLM:\n{formatted_prompt[:500]}...")

        try:
            model = LlmFactory().create(model_type, model_name)
            answer = model.generate(formatted_prompt)
            print(f"[LLM 回應] {answer[:300]}...")
        except Exception as e:
            print(f"[LLM 錯誤] {str(e)}")
            answer = "⚠️ LLM 伺服器錯誤，請稍後再試。"

        response_data = {
            "query": query,
            "answer": answer,
            "retrieved_docs": retrieved_docs
        }
        response_serializer = EnterpriseQueryResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
