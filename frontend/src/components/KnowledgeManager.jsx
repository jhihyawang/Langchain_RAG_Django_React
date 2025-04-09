import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const KnowledgeManager = () => {
    const [knowledgeList, setKnowledgeList] = useState([]);
    const [file, setFile] = useState(null);
    const [department, setDepartment] = useState("");
    const [selectedFileName, setSelectedFileName] = useState("");
    const departments = ["IT 部門", "人資部門", "財務部門", "行銷部門"];
    const navigate = useNavigate(); 

    useEffect(() => {
        fetchKnowledge();
    }, []);

    // 查詢知識庫
    const fetchKnowledge = async () => {
        try {
            const res = await fetch("http://127.0.0.1:8000/api/knowledge/");
            const data = await res.json();
    
            console.log("📌 API 回傳資料:", data); // 確保 API 回傳的結構正確
    
            // 設定知識庫清單，確保是 API 回傳的 "data" 陣列
            setKnowledgeList(Array.isArray(data.data) ? data.data : []);
        } catch (error) {
            console.error("❌ 無法獲取知識庫資料", error);
            setKnowledgeList([]); // 確保前端不會崩潰
        }
    };
    // 上傳新檔案
    const handleUpload = async () => {
        if (!file || !department) {
            alert("請選擇文件與部門！");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("department", department);
        formData.append("author", 1);

        try {
            const res = await fetch("http://127.0.0.1:8000/api/knowledge/", {
                method: "POST",
                body: formData,
            });

            if (res.ok) {
                alert("檔案上傳成功！");
                setFile(null);
                setDepartment("");
                setSelectedFileName("");
                fetchKnowledge();
            } else {
                alert("上傳失敗！");
            }
        } catch (error) {
            console.error("❌ 檔案上傳失敗", error);
        }
    };

    // 刪除知識
    const handleDelete = async (id) => {
        if (!window.confirm("確定要刪除嗎？")) return;

        try {
            const res = await fetch(`http://127.0.0.1:8000/api/knowledge/${id}/`, {
                method: "DELETE",
            });

            if (res.ok) {
                alert("刪除成功！");
                fetchKnowledge();
            } else {
                alert("刪除失敗！");
            }
        } catch (error) {
            console.error("❌ 刪除失敗", error);
        }
    };

    return (
        <div className="container mt-4">
            <h2>📚 企業知識庫管理</h2>

            {/* 🔹 檔案上傳/更新表單 */}
            <div className="mb-3">
                <input type="file" className="form-control mb-2" onChange={(e) => {
                    setFile(e.target.files[0]);
                    setSelectedFileName(e.target.files[0]?.name || ""); // 顯示選擇的檔案名稱
                }} />
                <select className="form-control mb-2" value={department} onChange={(e) => setDepartment(e.target.value)}>
                    <option value="">選擇部門</option>
                    {departments.map((dep) => (
                        <option key={dep} value={dep}>
                            {dep}
                        </option>
                    ))}
                </select>
                {selectedFileName && <p>📄 選擇的檔案：{selectedFileName}</p>}
                <button className="btn btn-primary w-100" onClick={handleUpload}>
                    上傳文件
                </button>
            </div>

            {/* 知識清單 */}
            <table className="table table-bordered mt-4">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>檔案名稱</th>
                        <th>部門</th>
                        <th>內容預覽</th>
                        <th>段落數</th>
                        <th>建立時間</th>
                        <th>上次修改</th>
                        <th>作者</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {Array.isArray(knowledgeList) && knowledgeList.length > 0 ? (
                        knowledgeList.map((item) => (
                            <tr key={item.id}>
                                <td>{item.id}</td>
                                <td>
                                    {item.file ? (
                                        <a href={item.file} target="_blank" rel="noopener noreferrer">
                                            {decodeURIComponent(item.file.split("/").pop())}
                                        </a>
                                    ) : (
                                        <span className="text-muted">無檔案</span>
                                    )}
                                </td>
                                <td>{item.department || "—"}</td>
                                <td className="text-truncate" style={{ maxWidth: "200px" }}>
                                    {item.content ? item.content.slice(0, 80) + (item.content.length > 80 ? "..." : "") : "無內容"}
                                </td>
                                <td>{item.chunk ?? "?"}</td>
                                <td>{new Date(item.created_at).toLocaleString()}</td>
                                <td>{new Date(item.updated_at).toLocaleString()}</td>
                                <td>{item.author || "—"}</td>
                                <td>
                                    <button
                                        className="btn btn-warning btn-sm me-2"
                                        onClick={() => navigate(`/knowledge/edit/${item.id}`)}
                                    >
                                        編輯chunks
                                    </button>
                                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(item.id)}>
                                        刪除檔案
                                    </button>
                                </td>
                            </tr>
                        ))
                    ) : (
                        <tr>
                            <td colSpan="8" className="text-center text-muted">⚠️ 查無資料</td>
                        </tr>
                    )}
                </tbody>
            </table>

        </div>
    );
};

export default KnowledgeManager;