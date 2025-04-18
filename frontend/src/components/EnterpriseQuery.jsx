import React, { useEffect, useState } from "react";
import Switch from "react-switch";

const EnterpriseQuery = () => {
    const [query, setQuery] = useState("");  // 存儲使用者輸入的問題
    const [response, setResponse] = useState("");  // 存儲 LLM 回應
    const [documents, setDocuments] = useState([]);  // 存儲檢索到的文件
    const [loading, setLoading] = useState(false);  // 控制讀取狀態
    const [modelType, setModelType] = useState("cloud");  // 新增模型選擇，預設為雲端 LLM
    const [modelName, setModelName] = useState("");  // 新增模型選擇，預設為雲端 LLM
    const [isListening, setIsListening] = useState(false); // 控制語音輸入狀態
    const [Retrieval, setIsRetrival] = useState(true);  // 預設啟用檢索

    let recognition = null;

    // 📌 初始化語音識別
    useEffect(() => {
        if ("webkitSpeechRecognition" in window) {
            recognition = new window.webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = "zh-TW"; // 設置為繁體中文

            recognition.onstart = () => {
                console.log("🎤 語音輸入開始...");
                setIsListening(true);
            };

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                console.log("🎙️ 識別到的語音：", transcript);
                setQuery(transcript); // 將語音結果填入查詢框
            };

            recognition.onerror = (event) => {
                console.error("❌ 語音輸入錯誤:", event.error);
            };

            recognition.onend = () => {
                console.log("🛑 語音輸入結束");
                setIsListening(false);
            };
        } else {
            console.warn("⚠️ 你的瀏覽器不支援 Web Speech API");
        }
    }, []);

    // 📌 開始語音輸入
    const startListening = () => {
        if (recognition) {
            recognition.start();
        } else {
            alert("你的瀏覽器不支援語音輸入！");
        }
    };

    // 📌 查詢 LLM API
    const handleQuery = async () => {
        if (!query.trim()) {
            alert("請輸入查詢問題！");
            return;
        }

        setLoading(true);
        setResponse("");  // 清空先前回應
        setDocuments([]); // 清空先前的文件

        console.log("📡 發送查詢請求：", { query, modelType }); // 確保 `modelType` 正確

        try {
            const res = await fetch("http://127.0.0.1:8000/api/query_enterprise/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query,
                    model_type: modelType,
                    use_retrieval: Retrieval
                }),
            });

            const data = await res.json();
            console.log("✅ API 回應數據：", data);  // 確保 API 回應格式正確

            if (res.ok) {
                setResponse(data.answer || "⚠️ 無回應");
                setDocuments(data.retrieved_docs || []);
            } else {
                setResponse(`❌ API 回應錯誤: ${data.error || "未知錯誤"}`);
            }
        } catch (error) {
            console.error("❌ 查詢失敗", error);
            setResponse("❌ 查詢失敗，請稍後再試");
        }

        setLoading(false);
    };

    return (
        <div className="container mt-4">
            <h2>🤖 企業知識庫查詢</h2>

            {/* 🔹 模型選擇下拉選單 */}
            <div className="mb-3">
                <label className="form-label">選擇 LLM 模型：</label>
                <select className="form-control" value={modelType} onChange={(e) => {
                    console.log("🔄 切換模型:", e.target.value); // 確保有更新 `modelType`
                    setModelType(e.target.value);
                }}>
                    <option value="cloud">☁️ 雲端 LLM</option>
                    <option value="local">💻 本地 LLM</option>
                </select>
            </div>

            <div className="mb-3 d-flex align-items-center">
                <label className="me-3">🔁 啟用向量檢索</label>
                <Switch
                    onChange={(checked) => {
                        console.log("🔁 檢索開關狀態：", checked);
                        setIsRetrival(checked);
                    }}
                    checked={Retrieval}
                    onColor="#3b82f6"        // 開啟時的藍色
                    offColor="#d1d5db"       // 關閉時的灰色
                    onHandleColor="#ffffff"  // 開啟時的開關顏色
                    handleDiameter={24}
                    uncheckedIcon={false}
                    checkedIcon={false}
                    height={28}
                    width={56}
                />
                <span className="ms-2">{Retrieval ? "ON" : "OFF"}</span>
            </div>

            {/* 🔹 查詢輸入框 + 語音按鈕 */}
            <div className="input-group mb-3">
                <input
                    type="text"
                    className="form-control"
                    placeholder="輸入您的問題..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />
                <button className="btn btn-secondary" onClick={startListening} disabled={isListening}>
                    {isListening ? "🎙️ 語音中..." : "🎤 語音輸入"}
                </button>
                <button className="btn btn-primary" onClick={handleQuery} disabled={loading}>
                    {loading ? "查詢中..." : "🔍 查詢"}
                </button>
            </div>

            {/* 🔹 LLM 回應區 */}
            <div className="mt-4 p-3 bg-light border rounded">
                <h5>🔍 LLM 回應：</h5>
                <p className="text-muted">{loading ? "⏳ 正在產生回應..." : response}</p>
            </div>

            {/* 🔹 顯示檢索說明與文件內容 */}
            <div className="mt-4">
                <h3>📄 檢索資料</h3>

                {/* 情況一：未啟用檢索 */}
                {!Retrieval && (
                    <div className="alert alert-info">
                        📌 <strong>未啟用向量檢索</strong>，以下回答內容為 LLM 根據自身知識生成。
                    </div>
                )}

                {/* 情況二：啟用檢索但找不到資料 */}
                {Retrieval && documents.length === 0 && (
                    <div className="alert alert-warning">
                        ⚠️ <strong>已啟用向量檢索</strong>，但未找到任何相關文件。
                    </div>
                )}

                {/* 情況三：成功檢索到文件 */}
                {Retrieval && documents.length > 0 && (
                    <ul className="list-group">
                        {documents.map((doc, index) => (
                            <li key={index} className="list-group-item">
                                <strong>📌 {doc.title} (第 {doc.page_number} 頁)</strong>
                                <p className="text-muted">{doc.content?.substring(0, 150)}...</p>
                                <a
                                    href={`/pdf-viewer/${doc.title}#page=${doc.page_number}`}
                                    className="btn btn-sm btn-link"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    🔗 跳轉到該頁
                                </a>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

        </div>
    );
};

export default EnterpriseQuery;