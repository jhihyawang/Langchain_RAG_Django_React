import React, { useState, useEffect } from "react";

const UserQuery = () => {
  const [textList, setTextList] = useState([]);
  const [file, setFile] = useState(null);
  const [selectedFileName, setSelectedFileName] = useState("");
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [modelType, setModelType] = useState("cloud");

  useEffect(() => {
    fetchTexts();
  }, []);

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

  const handleUpload = async () => {
    if (!file) return alert("請選擇檔案！");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("author", 1);

    const res = await fetch("http://127.0.0.1:8000/api/document/", {
      method: "POST",
      body: formData,
    });

    if (res.ok) {
      alert("📂 上傳成功");
      setFile(null);
      setSelectedFileName("");
      fetchTexts();
    } else {
      alert("❌ 上傳失敗");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("⚠️ 確定刪除？")) return;
    const res = await fetch(`http://127.0.0.1:8000/api/document/${id}/`, {
      method: "DELETE",
    });
    if (res.ok) {
      alert("🗑️ 刪除成功！");
      fetchTexts();
    } else {
      alert("❌ 刪除失敗！");
    }
  };

  const handleQuery = async () => {
    if (!query.trim()) {
      alert("請輸入查詢問題！");
      return;
    }

    setLoading(true);
    setResponse("");

    try {
      const res = await fetch("http://127.0.0.1:8000/api/query_user/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, model_type: modelType }),
      });

      const data = await res.json();

      if (res.ok) {
        setResponse(data.answer || "⚠️ 無回應");
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
    <div className="max-w-4xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-4">📚 文本管理與查詢</h2>

      <div className="mb-6">
        <input
          type="file"
          onChange={(e) => {
            setFile(e.target.files[0]);
            setSelectedFileName(e.target.files[0]?.name || "");
          }}
          className="w-full border p-2 rounded"
        />
        {selectedFileName && (
          <p className="text-sm mt-1">📄 {selectedFileName}</p>
        )}
        <button
          onClick={handleUpload}
          className="bg-blue-600 text-white px-4 py-2 rounded mt-2 w-full"
        >
          📤 上傳文件
        </button>
      </div>

      <div className="mb-8">
        <h3 className="text-lg font-semibold mb-2">📄 文件清單</h3>
        <table className="w-full text-left border">
          <thead className="bg-gray-100">
            <tr>
              <th className="p-2 border">ID</th>
              <th className="p-2 border">檔案名稱</th>
              <th className="p-2 border">操作</th>
            </tr>
          </thead>
          <tbody>
            {textList.length > 0 ? (
              textList.map((item) => (
                <tr key={item.id}>
                  <td className="p-2 border">{item.id}</td>
                  <td className="p-2 border">
                    <a href={item.file} target="_blank" rel="noopener noreferrer">
                      {decodeURIComponent(item.file.split("/").pop())}
                    </a>
                  </td>
                  <td className="p-2 border">
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="text-red-600 hover:underline"
                    >
                      🗑 刪除
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="3" className="p-2 text-center text-gray-400">
                  ⚠️ 無文件
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-2">🔍 查詢</h3>

        <div className="mb-2">
          <label className="block mb-1">選擇 LLM 模型：</label>
          <select
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
            className="w-full border p-2 rounded"
          >
            <option value="cloud">☁️ 雲端 LLM</option>
            <option value="local">💻 本地 LLM</option>
          </select>
        </div>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-grow border p-2 rounded"
            placeholder="請輸入問題..."
          />
          <button
            onClick={handleQuery}
            disabled={loading}
            className="bg-green-600 text-white px-4 py-2 rounded"
          >
            {loading ? "查詢中..." : "🔍 查詢"}
          </button>
        </div>

        <div className="bg-gray-100 p-4 rounded">
          <h4 className="font-semibold mb-2">📜 回答結果</h4>
          <p className="text-gray-700 whitespace-pre-wrap">
            {loading ? "⏳ 正在查詢..." : response}
          </p>
        </div>
      </div>
    </div>
  );
};

export default UserQuery;