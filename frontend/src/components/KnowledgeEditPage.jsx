import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

const KnowledgeEditPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [title, setTitle] = useState("");
    const [chunkList, setChunkList] = useState([]);

    useEffect(() => {
        fetch(`http://127.0.0.1:8000/api/knowledge/${id}/chunks/`)
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

    const handleSaveAll = async () => {
        try {
            for (const chunk of chunkList) {
                await fetch(`http://127.0.0.1:8000/api/knowledge/chunk/${chunk.id}/`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ content: chunk.content }),
                });
            }
            alert("✅ 所有區塊已成功更新！");
            navigate("/knowledge");
        } catch (err) {
            console.error("❌ 儲存失敗", err);
            alert("❌ 儲存失敗");
        }
    };

    return (
        <div className="container mt-4">
            <h3>📝 編輯文件內容（ID: {id}）</h3>
            <p>檔案名稱：{title}</p>

            {chunkList.map((chunk) => (
                <div className="card mb-3" key={chunk.id}>
                    <div className="card-header">
                        🧩 Chunk #{chunk.chunk_index}（第 {chunk.page_number} 頁）
                    </div>
                    <div className="card-body">
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

export default KnowledgeEditPage;
