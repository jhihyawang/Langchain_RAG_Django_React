import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import KnowledgeManager from "./components/KnowledgeManager"; 
import EnterpriseQuery from "./components/EnterpriseQuery";
import UserQuery from "./components/UserQuery";
import PdfViewer from "./components/PdfViewer";
import KnowledgeEditPage from "./components/KnowledgeEditPage";

function App() {
    return (
        <Router>
            <div className="container mt-4">
                <h1 className="text-center">統一證券AI助手</h1>

                {/* 🔹 切換介面選單 */}
                <div className="d-flex justify-content-center my-3">
                    <Link to="/knowledge" className="btn btn-primary mx-2">
                        📂 知識庫管理
                    </Link>
                    <Link to="/enterprise_query" className="btn btn-outline-primary mx-2">
                        🤖 企業知識庫查詢
                    </Link>
                    <Link to="/general_query" className="btn btn-outline-primary mx-2">
                        🤖 通用型AI查詢
                    </Link>
                </div>

                {/* 🔹 設定不同的路由 */}
                <Routes>
                    <Route path="/knowledge" element={<KnowledgeManager />} />
                    <Route path="/knowledge/edit/:id" element={<KnowledgeEditPage />} />
                    <Route path="/enterprise_query" element={<EnterpriseQuery />} />
                    <Route path="/general_query" element={<UserQuery />} />
                    <Route path="/pdf-viewer/:title" element={<PdfViewer />} />  {/* ✅ 新增 PDF Viewer 路由 */}
                    <Route path="*" element={<KnowledgeManager />} />  {/* 預設路由導向 知識庫管理 */}
                </Routes>
            </div>
        </Router>
    );
}

export default App;