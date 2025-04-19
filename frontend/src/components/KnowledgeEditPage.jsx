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
                setTitle((data.title || "").replace(/\.pdf$/i, "")); // 保留文件名
                const grouped = groupChunksByPage(data.chunks || []);
                setChunkGroups(grouped);
            })
            .catch(err => console.error("❌ 載入 chunks 失敗", err));
    }, [id]);

    const groupChunksByPage = (chunks) => {
        const groups = {};

        // 先根據頁碼分組
        chunks.forEach(chunk => {
            const key = JSON.stringify(chunk.page_number);
            if (!groups[key]) {
                groups[key] = {
                    page_number: chunk.page_number,
                    chunks: [],
                };
            }
            groups[key].chunks.push(chunk);
        });

        // 分類後重新排列每頁的 chunks
        return Object.values(groups);
    };

    const renderImageForChunk = (chunk) => {
        if (chunk.media_type === "image") {
            const sources = Array.isArray(chunk.source) ? chunk.source : [chunk.source];

            return (
                <div className="mb-2 text-center">
                    {sources.map((src, idx) => (
                        <img
                            key={`image-${idx}`}
                            src={`${API_BASE_URL}/${src}`}
                            alt={`chunk-${chunk.id}-image-${idx}`}
                            onError={(e) => console.error(`圖片載入失敗: ${src}`, e)}
                            style={{
                                maxWidth: "100%",
                                maxHeight: "300px",
                                objectFit: "contain",
                                border: "1px solid #ccc",
                                margin: "4px",
                            }}
                        />
                    ))}
                </div>
            );
        }
        return null;
    };

    const renderGroupImages = (group) => {
        let tableSources = new Set();  // 用來儲存表格圖片

        // 收集該群組內所有表格圖片
        group.chunks.forEach((chunk) => {
            if (chunk.media_type === "table") {
                let sources = [];
                try {
                    sources = Array.isArray(chunk.source) ? chunk.source : JSON.parse(chunk.source);
                } catch {
                    sources = [chunk.source];
                }

                sources.forEach(src => {
                    if (typeof src === "string" && src.includes("tables/")) {
                        tableSources.add(src);  // 表格圖片
                    }
                });
            }
        });

        // 如果沒有表格圖片，則不顯示
        if (tableSources.size === 0) return null;

        return (
            <div className="mb-2 text-center">
                {/* 顯示所有表格圖片 */}
                {Array.from(tableSources).map((src, idx) => (
                    <img
                        key={`table-${idx}`}
                        src={`${API_BASE_URL}/${src}`}
                        alt={`group-${group.page_number}-table-${idx}`}
                        style={{
                            maxWidth: "100%",
                            maxHeight: "300px",
                            objectFit: "contain",
                            border: "1px solid #ccc",
                            margin: "4px",
                        }}
                    />
                ))}
            </div>
        );
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
                // 先對所有 chunks 依 chunk_index 排序
                const sortedChunks = [...group.chunks].sort((a, b) => a.chunk_index - b.chunk_index);

                // 依照 media_type 分類
                const textChunks = sortedChunks.filter(chunk => chunk.media_type === "text");
                const imageChunks = sortedChunks.filter(chunk => chunk.media_type === "image");
                const tableChunks = sortedChunks.filter(chunk => chunk.media_type === "table");

                // 再依圖片 source 分組 image chunks
                const imageChunkGroups = {};
                imageChunks.forEach(chunk => {
                    let sources = [];
                    try {
                        sources = Array.isArray(chunk.source) ? chunk.source : JSON.parse(chunk.source);
                    } catch {
                        sources = [chunk.source];
                    }

                    const key = sources[0] || `unknown-${chunk.id}`;
                    if (!imageChunkGroups[key]) {
                        imageChunkGroups[key] = {
                            source: key,
                            chunks: [],
                        };
                    }
                    imageChunkGroups[key].chunks.push(chunk);
                });

                return (
                    <div key={idx} className="mb-4 border rounded p-3 bg-light">
                        <h5>
                            📄 頁碼：
                            {Array.isArray(group.page_number)
                                ? group.page_number.join(", ")
                                : group.page_number}
                        </h5>

                        {/* 📝 1. 顯示文字 chunk */}
                        {textChunks.map(chunk => (
                            <div className="card my-2" key={chunk.id}>
                                <div className="card-header d-flex justify-content-between align-items-center">
                                    <span>
                                        📝 Chunk #{chunk.chunk_index}
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
                                    {/* ✅ 顯示來源 source */}
                                    {chunk.source && (
                                        <p className="text-muted small">
                                            來源：{Array.isArray(chunk.source) ? chunk.source.join("、") : chunk.source}
                                        </p>
                                    )}
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

                        {/* 🖼️ 2. 顯示圖片群組（每張圖一次 + 該圖的 chunk） */}
                        {Object.values(imageChunkGroups).map((groupItem, gIdx) => (
                            <div key={`img-group-${gIdx}`} className="mb-4">
                                {groupItem.source && (
                                    <div className="mb-2 text-center">
                                        <img
                                            src={`${API_BASE_URL}/${groupItem.source}`}
                                            alt={`image-${gIdx}`}
                                            onError={(e) =>
                                                console.error(`圖片載入失敗: ${groupItem.source}`, e)
                                            }
                                            style={{
                                                maxWidth: "100%",
                                                maxHeight: "300px",
                                                objectFit: "contain",
                                                border: "1px solid #ccc",
                                                margin: "4px",
                                            }}
                                        />
                                    </div>
                                )}

                                {groupItem.chunks.map(chunk => (
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
                        ))}

                        {/* 📊 3. 顯示表格 chunks 與圖片 */}
                        {tableChunks.length > 0 && (
                            <div className="mt-4">
                                <h6 className="text-secondary">📊 表格區塊</h6>
                                {renderGroupImages({ chunks: tableChunks, page_number: group.page_number })}
                                {tableChunks.map((chunk) => (
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
                        )}
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
