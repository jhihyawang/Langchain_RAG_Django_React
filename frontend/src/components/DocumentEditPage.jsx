import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const DocumentEditPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [title, setTitle] = useState("");
    const [chunkList, setChunkList] = useState([]);
    const cleanTitle = title.replace(/\.pdf$/i, "");

    useEffect(() => {
        fetch(`http://127.0.0.1:8000/api/document/${id}/chunks/`)
            .then(res => res.json())
            .then(data => {
                setTitle(data.title || "");
                setChunkList(data.chunks || []);
            })
            .catch(err => console.error("❌ 載入 chunks 失敗", err));
    }, [id]);

    const handleChunkEdit = (chunkId, newContent) => {
        setChunkList(prev =>
            prev.map(chunk =>
                chunk.id === chunkId ? { ...chunk, content: newContent } : chunk
            )
        );
    };

    const handleDeleteChunk = async (chunkId) => {
        if (!window.confirm("確定要刪除此區塊嗎？")) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/document/chunk/${chunkId}/`, {
                method: "DELETE",
            });
            if (res.status === 204) {
                setChunkList(prev => prev.filter(chunk => chunk.id !== chunkId));
            } else {
                alert("❌ 刪除失敗");
            }
        } catch (err) {
            console.error("❌ 刪除 chunk 失敗", err);
        }
    };

    const handleSaveAll = async () => {
        try {
            for (const chunk of chunkList) {
                await fetch(`http://127.0.0.1:8000/api/document/chunk/${chunk.id}/`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ content: chunk.content }),
                });
            }
            alert("✅ 所有區塊已成功更新！");
            navigate("/document");
        } catch (err) {
            console.error("❌ 儲存失敗", err);
            alert("❌ 儲存失敗");
        }
    };

    const renderChunkImage = (chunk) => {
        let sources = [];

        try {
            const parsed = JSON.parse(chunk.source);
            sources = Array.isArray(parsed) ? parsed : [parsed];
        } catch {
            sources = [chunk.source];
        }

        // ➤ 過濾非圖片類型（只保留以 images/ 或 tables/ 開頭的路徑）
        const imageSources = sources.filter(
            src => typeof src === 'string' && (src.startsWith("images/") || src.startsWith("tables/"))
        );

        if (imageSources.length === 0) return null;

        return (
            <div className="mb-2 text-center">
                {imageSources.map((src, idx) => (
                    <img
                        key={idx}
                        src={`http://127.0.0.1:8000/media/extract_data/${encodeURIComponent(cleanTitle)}/${src}`}
                        alt={`chunk-${chunk.id}-${idx}`}
                        style={{
                            maxWidth: "100%",
                            maxHeight: "300px",
                            border: "1px solid #ccc",
                            margin: "4px",
                        }}
                    />
                ))}
            </div>
        );
    };


    return (
        <div className="container mt-4">
            <h3>📝 編輯文件內容（ID: {id}）</h3>
            <p>檔案名稱：{title}</p>

            {chunkList.map((chunk) => (
                <div className="card mb-3" key={chunk.id}>
                    <div className="card-header d-flex justify-content-between align-items-center">
                        <span>🧩 Chunk #{chunk.chunk_index}（第 {chunk.page_number} 頁） 來源：{chunk.source}</span>
                        <button
                            className="btn btn-sm btn-danger"
                            onClick={() => handleDeleteChunk(chunk.id)}
                        >
                            🗑️ 刪除
                        </button>
                    </div>
                    <div className="card-body">
                        {renderChunkImage(chunk)}
                        <textarea
                            className="form-control"
                            rows="5"
                            value={chunk.content}
                            onChange={(e) => handleChunkEdit(chunk.id, e.target.value)}
                        ></textarea>
                    </div>
                </div>
            ))}

            <button className="btn btn-success w-100 mt-4" onClick={handleSaveAll}>
                💾 儲存所有變更
            </button>
        </div>
    );
};

export default DocumentEditPage;
