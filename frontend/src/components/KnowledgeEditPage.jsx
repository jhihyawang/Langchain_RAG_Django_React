import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

const KnowledgeEditPage = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [content, setContent] = useState("");
    const [department, setDepartment] = useState("");

    useEffect(() => {
        fetch(`http://127.0.0.1:8000/api/knowledge/${id}/`)
            .then(res => res.json())
            .then(data => {
                setContent(data.content || "");
                setDepartment(data.department || "");
            })
            .catch(err => console.error("❌ 載入內容失敗", err));
    }, [id]);

    const handleSave = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/knowledge/${id}/`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    content,
                    department,
                }),
            });

            if (res.ok) {
                alert("✅ 內容更新成功！");
                navigate("/knowledge");
            } else {
                alert("❌ 更新失敗");
            }
        } catch (err) {
            console.error("❌ 儲存錯誤", err);
        }
    };

    return (
        <div className="container mt-4">
            <h3>📝 編輯文件內容（ID: {id}）</h3>
            <div className="mb-3">
                <label htmlFor="department" className="form-label">部門</label>
                <input
                    id="department"
                    className="form-control"
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                />
            </div>
            <div className="mb-3">
                <label htmlFor="content" className="form-label">文件內容</label>
                <textarea
                    id="content"
                    className="form-control"
                    rows="12"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                ></textarea>
            </div>
            <button className="btn btn-success w-100" onClick={handleSave}>💾 儲存</button>
        </div>
    );
};

export default KnowledgeEditPage;
