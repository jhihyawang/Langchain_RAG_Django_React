import re
import pdfplumber
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import os
import numpy as np
import json

# 初始化 PaddleOCR（繁中英文混合）
#ocr_engine = PaddleOCR(use_angle_cls=True, lang='chinese_cht')
# 初始化 PaddleOCR（簡中英文混合） #目前較佳
ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch')
# 檢查是否需要使用 OCR
def count_cid_like(text):
    cid_unicode_count = len(re.findall(r'[\ue000-\uf8ff]', text))
    cid_marker_count = len(re.findall(r'\(cid:\d+\)', text))
    return cid_unicode_count + cid_marker_count

# 解析 PDF 檔案，必要時 fallback OCR（改用 PaddleOCR）
def extract_text_from_pdf_with_fallback(file_path, cid_threshold=5):
    results = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            print(f"📄 正在解析第 {i} 頁...", end=" ")
            text = page.extract_text() or ""
            cid_count = count_cid_like(text)

            if cid_count >= cid_threshold:
                print(f"⚠️ CID 達 {cid_count}，使用 PaddleOCR")
                image = convert_from_path(file_path, first_page=i, last_page=i, dpi=400)[0]
                ocr_result = ocr_engine.ocr(np.array(image), cls=True)  # 加上 np.array()
                ocr_text = "\n".join([line[1][0] for line in ocr_result[0]])
                print(ocr_text.strip())
                results.append({
                    "page": i,
                    "method": "paddleocr",
                    "cid_count": cid_count,
                    "content": ocr_text.strip()
                })
            else:
                print("✅ 使用 pdfplumber")
                results.append({
                    "page": i,
                    "method": "pdfplumber",
                    "cid_count": cid_count,
                    "content": text.strip()
                })

    return results

# 📝 儲存為 JSON
def save_results_to_json(results, output_path="parsed_with_paddleocr.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已儲存解析結果至 {output_path}")

# 🧪 測試入口
if __name__ == "__main__":
    pdf_path = "/Users/joy/LLM/群益1-30.pdf"  # ← 修改為你的 PDF 路徑
    results = extract_text_from_pdf_with_fallback(pdf_path)
    save_results_to_json(results)
