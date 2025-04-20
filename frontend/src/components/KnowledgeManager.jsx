import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API_BASE_URL from "../api";

const KnowledgeManager = () => {
    const [knowledgeList, setKnowledgeList] = useState([]);
    const [file, setFile] = useState(null);
    const [department, setDepartment] = useState("");
    const [selectedId, setSelectedId] = useState(null);
    const [selectedFileName, setSelectedFileName] = useState("");
    const departments = ["IT 部門", "人資部門", "財務部門", "行銷部門"];
    const navigate = useNavigate();
    const [content, setContent] = useState("");
    const [pageInfo, setPageInfo] = useState({ count: 0, next: null, previous: null });
    const [currentPage, setCurrentPage] = useState(1);
    const pageSize = 5;
    const totalPages = Math.ceil(pageInfo.count / pageSize);

    useEffect(() => {
        // 第一次掛載時立即取得資料
        fetchKnowledge();

        // 每 5 秒自動刷新一次列表（可即時反映處理中狀態）
        const interval = setInterval(() => {
            fetchKnowledge();
        }, 5000);

        // 離開元件時清除定時器
        return () => clearInterval(interval);
    }, []);

    const fetchKnowledge = async (url = `${API_BASE_URL}/api/knowledge/`) => {
        try {
            const res = await fetch(url);
            const data = await res.json();
            const urlObj = new URL(url);
            const page = parseInt(urlObj.searchParams.get("page")) || 1;
            setKnowledgeList(data.results || []);
            setPageInfo({ count: data.count, next: data.next, previous: data.previous });
            setCurrentPage(page);
        } catch (error) {
            console.error("❌ 無法獲取知識庫資料", error);
            setKnowledgeList([]);
        }
    };

    const checkProcessingStatus = (id) => {
        const interval = setInterval(() => {
            fetch(`${API_BASE_URL}/api/knowledge/${id}/`)
                .then(res => res.json())
                .then(data => {
                    if (data.processing_status === 'done') {
                        clearInterval(interval);
                        alert(`✅ 文件 ${id} 處理完成！`);
                        fetchKnowledge();
                    }
                })
                .catch(err => {
                    console.error("❌ 無法檢查處理狀態", err);
                    clearInterval(interval);
                });
        }, 5000);
    };

    const handleUpload = async () => {
        if (!file || !department) {
            alert("請選擇文件與部門！");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("department", department);
        formData.append("author", 1);
        formData.append("content", content);

        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/`, {
                method: "POST",
                body: formData,
            });

            if (res.ok) {
                const data = await res.json();
                alert("檔案上傳成功，後台處理中...");
                setFile(null);
                setDepartment("");
                setSelectedFileName("");
                checkProcessingStatus(data.data.id);
            } else {
                alert("上傳失敗！");
            }
        } catch (error) {
            console.error("❌ 檔案上傳失敗", error);
        }
    };

    const handleDelete = async (item) => {
        let confirmMsg = "確定要刪除這份文件嗎？";

        if (item.processing_status === "processing") {
            confirmMsg = "⚠️ 該文件正在處理中，是否強制刪除並中止後端處理？";
        }

        if (!window.confirm(confirmMsg)) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/${item.id}/`, {
                method: "DELETE",
            });

            if (res.ok) {
                alert("✅ 刪除成功！");
                fetchKnowledge();
            } else {
                alert("❌ 刪除失敗！");
            }
        } catch (error) {
            console.error("❌ 刪除失敗", error);
        }
    };


    return (
        <div className="container mt-4">
            <h2>📚 企業知識庫管理</h2>

            <div className="mb-3">
                <input type="file" className="form-control mb-2" onChange={(e) => {
                    setFile(e.target.files[0]);
                    setSelectedFileName(e.target.files[0]?.name || "");
                }} />
                <select className="form-control mb-2" value={department} onChange={(e) => setDepartment(e.target.value)}>
                    <option value="">選擇部門</option>
                    {departments.map((dep) => (
                        <option key={dep} value={dep}>{dep}</option>
                    ))}
                </select>
                {selectedFileName && <p>📄 選擇的檔案：{selectedFileName}</p>}
                <button className="btn btn-primary w-100" onClick={handleUpload}>上傳文件</button>
            </div>

            <table className="table table-bordered mt-4">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>檔案名稱</th>
                        <th>部門</th>
                        <th>內容預覽(第一個段落)</th>
                        <th>段落數</th>
                        <th>建立時間</th>
                        <th>上次修改</th>
                        <th>作者</th>
                        <th>操作</th>
                        <th>處理狀態</th>
                    </tr>
                </thead>
                <tbody>
                    {Array.isArray(knowledgeList) && knowledgeList.length > 0 ? (
                        knowledgeList.map((item) => (
                            <tr key={item.id}>
                                <td>{item.id}</td>
                                <td>{item.file ? (<a href={item.file} target="_blank" rel="noopener noreferrer">{decodeURIComponent(item.file.split("/").pop())}</a>) : (<span className="text-muted">無檔案</span>)}</td>
                                <td>{item.department}</td>
                                <td title={item.content} style={{ maxWidth: "300px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.content ? item.content.slice(0, 50) + (item.content.length > 50 ? "..." : "") : <span className="text-muted">無內容</span>}</td>
                                <td>{item.chunk ?? "?"}</td>
                                <td>{new Date(item.created_at).toLocaleString()}</td>
                                <td>{new Date(item.updated_at).toLocaleString()}</td>
                                <td>{item.author || "—"}</td>
                                <td>
                                    {item.processing_status === "processing" ? (
                                        <button
                                            className="btn btn-secondary btn-sm me-2"
                                            disabled
                                            title="處理中，尚無法編輯"
                                        >
                                            ⏳ 處理中
                                        </button>
                                    ) : (
                                        <button className="btn btn-warning btn-sm me-2"
                                            onClick={() => navigate(`/knowledge/edit/${item.id}`)}>
                                            編輯chunks
                                        </button>
                                    )}
                                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(item)}>
                                        刪除檔案
                                    </button>
                                </td>
                                <td>
                                    {item.processing_status === "done" && <span className="text-success">✅ 完成</span>}
                                    {item.processing_status === "processing" && <span className="text-warning">⏳ 處理中</span>}
                                    {item.processing_status === "pending" && <span className="text-secondary">🕒 等待中</span>}
                                    {item.processing_status === "error" && <span className="text-danger">❌ 失敗</span>}
                                </td>
                            </tr>
                        ))
                    ) : (
                        <tr>
                            <td colSpan="9" className="text-center text-muted">⚠️ 查無資料</td>
                        </tr>
                    )}
                </tbody>
            </table>

            <div className="mt-4 text-center">
                <button className="btn btn-outline-secondary me-2" onClick={() => fetchKnowledge(`${API_BASE_URL}/api/knowledge/?page=${currentPage - 1}`)} disabled={currentPage <= 1}>上一頁</button>
                <span className="mx-3 align-middle">第 <strong>{currentPage}</strong> 頁 / 共 <strong>{totalPages}</strong> 頁</span>
                <button className="btn btn-outline-secondary ms-2" onClick={() => fetchKnowledge(`${API_BASE_URL}/api/knowledge/?page=${currentPage + 1}`)} disabled={currentPage >= totalPages}>下一頁</button>
            </div>
        </div>
    );
};

export default KnowledgeManager;
