# 🚀 RAG+Copilot

一個基於 LangChain 架構的智慧助理系統，支援 **多模態輸入**（文字、表格、圖片），整合 **GitHub 上的 LLM API**（如 LLaMA3.3 70B、OpenAI GPT-4o），可進行嵌入式檢索、問答與知識型輔助回答。前後端分離設計，提供清晰的使用者介面與高彈性 API 介接。

---

## 🔧 技術架構

| 元件 | 技術 |
|------|------|
| 前端 | React（支援多模態輸入與顯示） |
| 後端 | Django + Django REST Framework |
| RAG 架構 | LangChain |
| 向量資料庫 | ChromaDB |
| 詞嵌入模型 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`  via HuggingFace API |
| LLM | OpenAI GPT-4o、Meta LLaMA3.3 70B via Github API |
| 文件處理 | PyMuPDF、PIL、表格解析（如 pandas、pdfplumber） |

---

## 💡 功能特色

- ✅ 文件上傳（支援 PDF、圖片、表格）
- ✅ 多模態問答（文字、圖片、表格輸入）
- ✅ 自動嵌入與儲存向量到 ChromaDB
- ✅ RAG 文件檢索與語言模型整合回答
- ✅ 支援 OpenAI / HuggingFace API 切換
- ✅ RESTful API 串接前後端
- ✅ 前端 UI 支援查詢歷史與回答呈現

---

## 📦 安裝與執行

### ✅ 1. 專案初始化

```bash
git clone https://github.com/jhihyawang/Langchain_RAG_Django_React.git
cd Langchain_RAG_Django_React
```

### ✅ 2. 後端（Django）

```bash
python -m venv venv
source venv/bin/activate        # Windows 請使用 venv\Scripts\activate
pip install -r requirements.txt
```

### ✅ 3. 資料庫遷移與啟動

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

後端將啟動於：<http://127.0.0.1:8000>

---

### ✅ 4. 前端（React）

```bash
cd frontend
npm install
npm start
```

前端將運行於：<http://localhost:3000>

---

## 📁 專案結構

```
Langchain_RAG_Django_React/
├── backend/                      # Django 專案（rag_project）
│   ├── general_assistant/       # 通用型助手
│   ├── enterprise_assistant/    # 企業知識庫檢索模組
│   └── api/                     # RESTful API 定義
├── frontend/                    # React 前端
│   ├── package.json            # 專案依賴與指令定義
│   ├── public/                 # 公共靜態資源（如 index.html）
│   ├── src/                    # React 源始碼
│   │   ├── App.js              # 應用程式主組件
│   │   ├── App.test.js         # 測試檔案
│   │   ├── index.js            # React 入口點
│   │   └── components/         # 元件資料夾
│   │       ├── EnterpriseQuery.jsx     # 企業知識問答元件
│   │       ├── KnowledgeManager.jsx    # 文件管理與知識建立功能
│   │       ├── PdfViewer.jsx           # PDF 預覽與嵌入顯示
│   │       └── UserQuery.jsx           # 使用者端問答元件
├── .env.example                 # 環境變數範例
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🧑‍💻 作者

由 [@jhihyawang](https://github.com/jhihyawang) 製作，結合 Django、React 與 LangChain 建立文件智能問答助理系統。
