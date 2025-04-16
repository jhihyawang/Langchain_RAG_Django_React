from general_assistant.rag.extract_pdf import load_pdf_images_and_ocr

file_path = "/Users/joy/LLM/群益14.pdf"
images, ocr_cache = load_pdf_images_and_ocr(file_path)
print(ocr_cache[1])  # 查看第3頁的OCR結果是否已旋轉後變為可辨識中文