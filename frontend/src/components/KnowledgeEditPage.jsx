import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import API_BASE_URL from "../api";

const KnowledgeEditPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [title, setTitle] = useState("");
    const [chunkGroups, setChunkGroups] = useState([]);
    const [modifiedChunks, setModifiedChunks] = useState(new Set());
    const [searchText, setSearchText] = useState("");

    useEffect(() => {
        fetch(`${API_BASE_URL}/api/knowledge/${id}/chunks/`)
            .then(res => res.json())
            .then(data => {
                setTitle(data.title || "");
                const grouped = groupChunksByPage(data.chunks || []);
                setChunkGroups(grouped);
            })
            .catch(err => console.error("❌ 載入 chunks 失敗", err));
    }, [id]);

    const groupChunksByPage = (chunks) => {
        const groups = {};

        chunks.forEach(chunk => {
            const key = JSON.stringify(chunk.page_number);  // ex: "[2,3,4]"
            if (!groups[key]) {
                groups[key] = {
                    page_number: chunk.page_number,
                    chunks: [],
                    source: chunk.source
                };
            }
            groups[key].chunks.push(chunk);
        });

        return Object.values(groups);
    };

    const handleChunkEdit = (chunkId, newContent) => {
        setChunkGroups(prev =>
            prev.map(group => ({
                ...group,
                chunks: group.chunks.map(chunk =>
                    chunk.id === chunkId ? { ...chunk, content: newContent } : chunk
                )
            }))
        );
    };

    const handleDeleteChunk = async (chunkId) => {
        if (!window.confirm("確定要刪除此區塊嗎？")) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/knowledge/chunk/${chunkId}/`, {
                method: "DELETE",
            });
            if (res.status === 204) {
                setChunkGroups(prev =>
                    prev.map(group => ({
                        ...group,
                        chunks: group.chunks.filter(chunk => chunk.id !== chunkId)
                    })).filter(group => group.chunks.length > 0)
                );
            } else {
                alert("❌ 刪除失敗");
            }
        } catch (err) {
            console.error("❌ 刪除 chunk 失敗", err);
        }
    };

    const handleSaveAll = async () => {
        try {
            for (const group of chunkGroups) {
                for (const chunk of group.chunks) {
                    await fetch(`${API_BASE_URL}/api/knowledge/chunk/${chunk.id}/`, {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ content: chunk.content }),
                    });
                }
            }
            alert("✅ 所有區塊已成功更新！");
            navigate("/document");
        } catch (err) {
            console.error("❌ 儲存失敗", err);
            alert("❌ 儲存失敗");
        }
    };

    const renderGroupImages = (source) => {
        let sources = [];

        try {
            sources = Array.isArray(source) ? source : JSON.parse(source);
        } catch {
            sources = [source];
        }

        const imageSources = sources.filter(
            src => typeof src === "string" && (src.includes("images/") || src.includes("tables/"))
        );

        if (imageSources.length === 0) return null;

        return (
            <div className="mb-2 text-center">
                {imageSources.map((src, idx) => (
                    <img
                        key={idx}
                        src={`${API_BASE_URL}/${src}`}
                        alt={`chunk-image-${idx}`}
                        style={{
                            maxWidth: "100%",
                            maxHeight: "300px",
                            height: "auto",
                            objectFit: "contain",  // 不變形
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
            <input
                type="text"
                className="form-control mb-3"
                placeholder="🔍 搜尋 chunk 內容關鍵字..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
            />
            {chunkGroups.map((group, idx) => {
                const matchedChunks = group.chunks.filter(chunk =>
                    chunk.content.toLowerCase().includes(searchText.toLowerCase())
                );
                if (matchedChunks.length === 0) return null;

                const mediaTypes = [...new Set(group.chunks.map(c => c.media_type))];
                const isPureTable = mediaTypes.length === 1 && mediaTypes[0] === "table";
                const isImage = mediaTypes.length === 1 && mediaTypes[0] === "image";
                const isText = mediaTypes.length === 1 && mediaTypes[0] === "text";

                return (
                    <div key={idx} className="mb-4 border rounded p-3 bg-light">
                        <h5>
                            📄 頁碼：{Array.isArray(group.page_number)
                                ? group.page_number.join(", ")
                                : group.page_number}
                            {isPureTable && (
                                <> ｜ 共 {Array.isArray(group.page_number) ? group.page_number.length : 1} 張跨頁表格</>
                            )}
                        </h5>

                        {/* ✅ 僅表格與圖片顯示圖片 */}
                        {(isPureTable || isImage) && renderGroupImages(group.source)}

                        {/* ✅ 僅文字與圖片顯示來源 */}
                        {(isText || isImage) && group.source && (
                            <p className="text-muted small">
                                來源：{Array.isArray(group.source)
                                    ? group.source.join("、")
                                    : group.source}
                            </p>
                        )}

                        {matchedChunks.map((chunk) => (
                            <div className="card my-2" key={chunk.id}>
                                <div className="card-header d-flex justify-content-between align-items-center">
                                    <span>
                                        🧩 Chunk #{chunk.chunk_index}
                                        {modifiedChunks.has(chunk.id) && (
                                            <span className="text-warning ms-2">🟡 已修改</span>
                                        )}
                                    </span>
                                    <button
                                        className="btn btn-sm btn-danger"
                                        onClick={() => handleDeleteChunk(chunk.id)}
                                    >
                                        🗑️ 刪除
                                    </button>
                                </div>
                                <div className="card-body">
                                    <textarea
                                        className="form-control"
                                        rows="5"
                                        value={chunk.content}
                                        onChange={(e) => {
                                            handleChunkEdit(chunk.id, e.target.value);
                                            setModifiedChunks((prev) => {
                                                const next = new Set(prev);
                                                next.add(chunk.id);
                                                return next;
                                            });
                                        }}
                                    ></textarea>
                                </div>
                            </div>
                        ))}
                    </div>
                );
            })}
            <button className="btn btn-success w-100 mt-4" onClick={handleSaveAll}>
                💾 儲存所有變更
            </button>
        </div>
    );

};

export default KnowledgeEditPage;
