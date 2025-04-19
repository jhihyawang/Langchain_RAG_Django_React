import requests

class AzureLlamaAPI:
    """ 使用 `requests` 呼叫 Azure Inference API """

    API_URL = "https://models.inference.ai.azure.com/chat/completions"
    API_KEY = "#"  # ⚠️ 請確保 API Key 正確

    @staticmethod
    def ask(question: str, context: str = ""):
        """ 直接發送 `POST` API，包含檢索到的上下文 """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AzureLlamaAPI.API_KEY}"
        }

        messages = [
            {"role": "system", "content": "你是一個 AI 助手，根據提供的上下文回答問題。"},
            {"role": "user", "content": f"上下文：{context}\n\n問題：{question}"}
        ]

        payload = {
            "messages": messages,
            "model": "Llama-3.3-70B-Instruct",
            "temperature": 0.8,
            "max_tokens": 2048,
            "top_p": 0.1
        }

        response = requests.post(AzureLlamaAPI.API_URL, headers=headers, json=payload)

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"API 請求失敗: {response.status_code}, {response.text}"