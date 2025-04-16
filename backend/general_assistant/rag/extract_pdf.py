import re
import pdfplumber
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import os
import numpy as np
from PIL import Image
import io
import torch
from transformers import DetrImageProcessor, TableTransformerForObjectDetection
from unstructured.partition.pdf import partition_pdf
import ollama
from difflib import SequenceMatcher

ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch')

MEDIA_ROOT = "media"  # ⬅️ 設定 media 路徑為全域


def count_cid_like(text):
    cid_unicode_count = len(re.findall(r'[\ue000-\uf8ff]', text))
    cid_marker_count = len(re.findall(r'\(cid:\d+\)', text))
    return cid_unicode_count + cid_marker_count

def load_pdf_images_and_ocr(file_path, dpi=400):
    images = convert_from_path(file_path, dpi=dpi)
    ocr_cache = {}

    for i, image in enumerate(images):
        print(f"🖼️ OCR 預處理 第 {i+1} 頁")
        ocr_result = ocr_engine.ocr(np.array(image), cls=True)

        angles = [box[2].get("angle", 0) for line in ocr_result for box in line if len(box) >= 3 and isinstance(box[2], dict)]
        vertical_count = sum(1 for a in angles if a in [90, 270])
        ratio = vertical_count / len(angles) if angles else 0

        if len(angles) >= 5 and ratio > 0.6:
            dominant_angle = max(set(angles), key=angles.count)
            print(f"🔄 第 {i+1} 頁需要旋轉 {dominant_angle} 度")
            image = image.rotate(-dominant_angle, expand=True)
            ocr_result = ocr_engine.ocr(np.array(image), cls=True)
        elif len(angles) < 5 and ratio > 0.3:
            dominant_angle = max(set(angles), key=angles.count)
            print(f"🌀 少量文字但角度異常，旋轉第 {i+1} 頁 {dominant_angle} 度")
            image = image.rotate(-dominant_angle, expand=True)
            ocr_result = ocr_engine.ocr(np.array(image), cls=True)

        images[i] = image
        ocr_cache[i + 1] = {
            "image": image,
            "ocr_result": ocr_result
        }

    return images, ocr_cache

def extract_text_from_pdf_with_fallback(images, ocr_cache, file_path, cid_threshold=5):
    results = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            print(f"📄 正在解析第 {i} 頁...", end=" ")
            text = page.extract_text() or ""
            cid_count = count_cid_like(text)

            if cid_count >= cid_threshold:
                print(f"CID 達 {cid_count}，使用 OCR 快取")
                ocr_result = ocr_cache.get(i, {}).get("ocr_result")
                ocr_text = "\n".join([line[1][0] for line in ocr_result[0]]) if ocr_result else ""

                results.append({
                    "page": i,
                    "source": "ocr",
                    "cid_count": cid_count,
                    "content": ocr_text.strip()
                })
            else:
                print(f"使用 pdfplumber:{text.strip()}")
                results.append({
                    "page": i,
                    "source": "origin",
                    "cid_count": cid_count,
                    "content": text.strip()
                })
    return results

# 表格模型初始化
processor = DetrImageProcessor.from_pretrained("microsoft/table-transformer-detection")
table_model = TableTransformerForObjectDetection.from_pretrained("microsoft/table-transformer-detection")

def extract_title_above(image: Image.Image, box, ocr_engine, crop_height=200):
    top = max(box[1] - crop_height, 0)
    cropped = image.crop((box[0], top, box[2], box[1]))
    ocr_result = ocr_engine.ocr(np.array(cropped), cls=True)
    if ocr_result and isinstance(ocr_result[0], list):
        return "\n".join([line[1][0] for line in ocr_result[0]]).strip()
    return ""

def summarize_image(image_path, prompt):
    try:
        response = ollama.chat(
            model='gemma3:4b',
            messages=[{'role': 'user', 'content': prompt, 'images': [image_path]}]
        )
        return response['message']['content']
    except Exception as e:
        return f"❌ 圖像分析錯誤: {str(e)}"

def extract_table_and_summary(images, ocr_cache, save_dir="tables_valid"):
    output_dir = os.path.join(MEDIA_ROOT, save_dir)
    os.makedirs(output_dir, exist_ok=True)
    table_results = []

    for page_idx in range(1, len(images) + 1):
        print(f"📄 偵測第 {page_idx} 頁表格...")

        image = ocr_cache[page_idx]["image"]
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = table_model(**inputs)

        target_sizes = torch.tensor([image.size[::-1]])
        results = processor.post_process_object_detection(outputs, threshold=0.7, target_sizes=target_sizes)[0]

        for i, box in enumerate(results["boxes"]):
            box = [int(v) for v in box.tolist()]
            cropped = image.crop((box[0], box[1], box[2], box[3]))
            file_name = f"page_{page_idx}_table_{i+1}.png"
            table_img_path = os.path.join(output_dir, file_name)
            cropped.save(table_img_path)

            title = extract_title_above(image, box, ocr_engine)
            if not title:
                title = f"第 {page_idx} 頁表格 {i+1}"
            prompt = f"這是一份群益證券112年報，這張表格為：{title}，請詳細描述這張表格的內容，若是有每個欄位有關聯性，請一一列出每一列中的所有項目以及其內容"
            summary = "模擬LLM摘要"
            table_results.append({
                "page": page_idx,
                "source": f"{save_dir}/{file_name}",
                "content": summary
            })

    return table_results

def extract_img_and_summary(file_path, ocr_cache, save_dir="images"):
    output_dir = os.path.join(MEDIA_ROOT, save_dir)
    os.makedirs(output_dir, exist_ok=True)
    raw_pdf_elements = partition_pdf(
        filename=file_path,
        extract_images_in_pdf=True,
        infer_table_structure=False,
        extract_image_block_output_dir=output_dir,
        hi_res_images=True,
    )
    results = []
    for e in raw_pdf_elements:
        if e.category == "Image" and hasattr(e.metadata, "image_path"):
            page_num = e.metadata.page_number or 0
            img_path = e.metadata.image_path
            try:
                img = Image.open(img_path)
                if ocr_cache.get(page_num):
                    ocr_result = ocr_engine.ocr(np.array(img), cls=True)
                else:
                    ocr_result = ocr_engine.ocr(np.array(img), cls=True)

                if ocr_result and len(ocr_result[0]) >= 1:
                    print(f"✅ 有文字，保留圖片: {img_path}")
                    file_name = os.path.basename(img_path)
                    prompt = "請詳細描述這張圖片的內容，若是圖表請說明其趨勢與關鍵數據"
                    summary = "模擬LLM摘要"
                    results.append({
                        "page": page_num,
                        "source": f"{save_dir}/{file_name}",
                        "content": summary
                    })
                else:
                    print(f"⚠️ 無文字內容，刪除圖片: {img_path}")
                    os.remove(img_path)
            except Exception as err:
                print(f"❌ 圖片處理失敗: {img_path}，錯誤: {str(err)}")
    return results

def processData(file_path, document_id=None):
    print("📦 預先載入圖像與 OCR 結果...")
    images, ocr_cache = load_pdf_images_and_ocr(file_path)

    print("📄 Extract text from PDF...")
    text_content = extract_text_from_pdf_with_fallback(images, ocr_cache, file_path, cid_threshold=5)

    print("📊 Detecting tables...")
    table_content = extract_table_and_summary(images, ocr_cache)

    print("🖼️ Extracting images...")
    #img_content = extract_img_and_summary(file_path, ocr_cache)

    return {
        "text": text_content,
        "table": table_content,
        "image": []
    }
