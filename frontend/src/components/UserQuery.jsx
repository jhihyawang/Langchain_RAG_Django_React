import React, { useState, useEffect } from "react";

const UserQuery = () => {
    // 📌 **文本管理狀態**
    const [textList, setTextList] = useState([]);
    const [file, setFile] = useState(null);
    const [selectedFileName, setSelectedFileName] = useState(""); 
    const [selectedId, setSelectedId] = useState(null);

    // 📌 **查詢狀態**
    const [query, setQuery] = useState("");
    const [response, setResponse] = useState("");
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(false);
    const [modelType, setModelType] = useState("cloud");

    useEffect(() => {
        fetchTexts();
    }, []);

    // 📌 **查詢文本庫**
    const fetchTexts = async () => {
        try {
            const res = await fetch("http://127.0.0.1:8000/api/document/");
            const data = await res.json();
            setTextList(Array.isArray(data.data) ? data.data : []);
        } catch (error) {
            console.error("❌ 獲取文本庫失敗", error);
            setTextList([]);
        }
    };

    // 📌 **上傳新文本**
    const handleUpload = async () => {
        if (!file) {
            alert("請選擇檔案！");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("author", 1);

        try {
            const res = await fetch("http://127.0.0.1:8000/api/document/", {
                method: "POST",
                body: formData,
            });

            if (res.ok) {
                alert("📂 文本上傳成功！");
                setFile(null);
                setSelectedFileName("");
                fetchTexts();
            } else {
                alert("❌ 文本上傳失敗！");
            }
        } catch (error) {
            console.error("❌ 文本上傳失敗", error);
        }
    };

    // 📌 **刪除文本**
    const handleDelete = async (id) => {
        if (!window.confirm("⚠️ 確定要刪除嗎？")) return;

        try {
            const res = await fetch(`http://127.0.0.1:8000/api/document/${id}/`, {
                method: "DELETE",
            });

            if (res.ok) {
                alert("🗑️ 刪除成功！");
                fetchTexts();
            } else {
                alert("❌ 刪除失敗！");
            }
        } catch (error) {
            console.error("❌ 刪除失敗", error);
        }
    };

    // 📌 **查詢 LLM API**
    const handleQuery = async () => {
        if (!query.trim()) {
            alert("請輸入查詢問題！");
            return;
        }

        setLoading(true);
        setResponse("");  
        setDocuments([]); 

        try {
            const res = await fetch("http://127.0.0.1:8000/api/query_user/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, model_type: modelType }),
            });

            const data = await res.json();

            if (res.ok) {
                setResponse(data.answer || "⚠️ 無回應");
                setDocuments(data.retrieved_docs || []);
            } else {
                setResponse(`❌ API 錯誤: ${data.error || "未知錯誤"}`);
            }
        } catch (error) {
            console.error("❌ 查詢失敗", error);
            setResponse("❌ 查詢失敗，請稍後再試");
        }

        setLoading(false);
    };

    return (
        <div className="container mt-4">
            <h2>📚 文本管理與查詢</h2>

            {/* 📌 **文本上傳表單** */}
            <div className="mb-3">
                <input type="file" className="form-control mb-2" onChange={(e) => {
                    setFile(e.target.files[0]);
                    setSelectedFileName(e.target.files[0]?.name || ""); 
                }} />
                {selectedFileName && <p>📄 選擇的檔案：{selectedFileName}</p>}
                <button className="btn btn-primary w-100" onClick={handleUpload}>
                    📤 上傳文件
                </button>
            </div>

            {/* 📌 **文本庫文件清單** */}
            <table className="table table-bordered mt-4">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>檔案名稱</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {Array.isArray(textList) && textList.length > 0 ? (
                        textList.map((item) => (
                            <tr key={item.id}>
                                <td>{item.id}</td>
                                <td>
                                    <a href={item.file} target="_blank" rel="noopener noreferrer">
                                        {decodeURIComponent(item.file.split("/").pop())}
                                    </a>
                                </td>
                                <td>
                                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(item.id)}>
                                        🗑 刪除
                                    </button>
                                </td>
                            </tr>
                        ))
                    ) : (
                        <tr>
                            <td colSpan="3" className="text-center text-muted">⚠️ 無文本庫文件</td>
                        </tr>
                    )}
                </tbody>
            </table>

            {/* 📌 **查詢區塊** */}
            <div className="mt-4">
                <h3>🔍 文本查詢</h3>

                <div className="mb-3">
                    <label className="form-label">選擇 LLM 模型：</label>
                    <select className="form-control" value={modelType} onChange={(e) => setModelType(e.target.value)}>
                        <option value="cloud">☁️ 雲端 LLM</option>
                        <option value="local">💻 本地 LLM</option>
                    </select>
                </div>

                <div className="input-group mb-3">
                    <input
                        type="text"
                        className="form-control"
                        placeholder="輸入您的問題..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    <button className="btn btn-primary" onClick={handleQuery} disabled={loading}>
                        {loading ? "查詢中..." : "🔍 查詢"}
                    </button>
                </div>

                {/* 📌 **查詢回應** */}
                <div className="mt-4 p-3 bg-light border rounded">
                    <h5>📜 LLM 回應：</h5>
                    <p className="text-muted">{loading ? "⏳ 正在產生回應..." : response}</p>
                </div>
            </div>
        </div>
    );
};

export default UserQuery;