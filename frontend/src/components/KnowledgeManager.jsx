import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API_BASE_URL from "../api";

const KnowledgeManager = () => {
    const [knowledgeList, setKnowledgeList] = useState([]);
    const [file, setFile] = useState(null);
    const [department, setDepartment] = useState("");
    const [selectedId, setSelectedId] = useState(null);
    const [selectedFileName, setSelectedFileName] = useState(""); // 顯示選中的檔案名稱
    const departments = ["IT 部門", "人資部門", "財務部門", "行銷部門"];
    const navigate = useNavigate();
    const [content, setContent] = useState("");
    const [pageInfo, setPageInfo] = useState({
        count: 0, //總資料數
        next: null, //next page url
        previous: null, //last page url
    });
    const [currentPage, setCurrentPage] = useState(1);//目前頁數
    const pageSize = 5; //後端預設每頁10筆資料
    const totalPages = Math.ceil(pageInfo.count / pageSize)
    useEffect(() => {
        fetchKnowledge();
    }, []);

    // 查詢知識庫
    const fetchKnowledge = async (url = `${API_BASE_URL}/api/knowledge/`) => {
        try {
            const res = await fetch(url);
            const data = await res.json();
            const urlObj = new URL(url);
            const page = parseInt(urlObj.searchParams.get("page")) || 1;

            //知識庫清單和分頁資訊
            //設定知識庫清單
            setKnowledgeList(data.results || []);
            setPageInfo({
                count: data.count,
                next: data.next,
                previous: data.previous,
            });
            setCurrentPage(page)
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
        formData.append("content", content);

        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/`, {
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

    //更新已上傳的檔案
    const handleUpdate = async () => {
        if (!file || !selectedId) {
            alert("請選擇要更新的文件！");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("department", department);

        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/${selectedId}/`, {
                method: "PUT",
                body: formData,
            });

            if (res.ok) {
                alert("檔案更新成功！");
                setFile(null);
                setDepartment("");
                setSelectedId(null);
                setSelectedFileName("");
                fetchKnowledge();
            } else {
                alert("更新失敗！");
            }
        } catch (error) {
            console.error("❌ 更新失敗", error);
        }
    };

    // 刪除知識
    const handleDelete = async (id) => {
        if (!window.confirm("確定要刪除嗎？")) return;

        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/${id}/`, {
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

            {/* 檔案上傳 */}
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
                        <th>內容預覽(第一個段落)</th>
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
                                <td>{item.department}</td>
                                <td
                                    title={item.content}
                                    style={{ maxWidth: "300px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                    {item.content ? item.content.slice(0, 50) + (item.content.length > 50 ? "..." : "") : <span className="text-muted">無內容</span>}
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
                            <td colSpan="4" className="text-center text-muted">⚠️ 查無資料</td>
                        </tr>
                    )}
                </tbody>
            </table>
            <div className="mt-4 text-center">
                <button
                    className="btn btn-outline-secondary me-2"
                    onClick={() => fetchKnowledge(`${API_BASE_URL}/api/knowledge/?page=${currentPage - 1}`)}
                    disabled={currentPage <= 1}
                >
                    上一頁
                </button>

                <span className="mx-3 align-middle">
                    第 <strong>{currentPage}</strong> 頁 / 共 <strong>{totalPages}</strong> 頁
                </span>

                <button
                    className="btn btn-outline-secondary ms-2"
                    onClick={() => fetchKnowledge(`${API_BASE_URL}/api/knowledge/?page=${currentPage + 1}`)}
                    disabled={currentPage >= totalPages}
                >
                    下一頁
                </button>
            </div>
        </div>
    );
};

export default KnowledgeManager;

