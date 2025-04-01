import React from "react";
import { useParams, useLocation } from "react-router-dom";
import { Document, Page, pdfjs } from "react-pdf";

// 設定 PDF.js 的 worker URL，確保 PDF 能夠載入
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js`;

const PdfViewer = () => {
    const { title } = useParams();  // 從 URL 取得 `title`
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const pageNumber = parseInt(queryParams.get("page")) || 1;  // 取得 `page` 參數，預設第 1 頁

    // 設定檔案的 URL (Django 提供的 media 目錄)
    const pdfUrl = `http://127.0.0.1:8000/media/knowledge_files/${decodeURIComponent(title)}`;

    return (
        <div className="container mt-4">
            <h2>📄 PDF 預覽：{decodeURIComponent(title)}</h2>
            <Document file={pdfUrl} onLoadError={(error) => console.error("PDF 加載錯誤", error)}>
                <Page pageNumber={pageNumber} />
            </Document>
            <p className="mt-3">📜 目前顯示第 {pageNumber} 頁</p>
        </div>
    );
};

export default PdfViewer;