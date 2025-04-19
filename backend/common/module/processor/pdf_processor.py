import os
import re
import time
from datetime import datetime

import fitz  # PyMuPDF
import numpy as np
import ollama
import pdfplumber
import torch
from easyocr import Reader
from pdf2image import convert_from_path
from PIL import Image
from transformers import AutoModelForObjectDetection, AutoProcessor


def log(msg):
    now = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{now} {msg}")

class PdfProcessor:
    def __init__(self, pdf_path, output_dir="media/extract_data", model_name="gemma3:27b", knowledge_id=None, vectorstore=None,cid_threshold=20):
        self.pdf_path = pdf_path
        self.file_stem = os.path.splitext(os.path.basename(pdf_path))[0]
        self.output_dir = os.path.join(output_dir, self.file_stem)
        self.model_name = model_name
        self.knowledge_id = knowledge_id
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.reader = Reader(['ch_tra', 'en'], gpu=torch.cuda.is_available())
        self.detector = AutoModelForObjectDetection.from_pretrained("microsoft/table-transformer-detection", revision="no_timm").to(self.device)
        self.processor = AutoProcessor.from_pretrained("microsoft/table-transformer-detection", revision="no_timm")
        self.cid_threshold = cid_threshold
        #self.vectorstore = vectorstore or VectorStoreHandler(db_path="chroma_user_db")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "tables"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "ocr_fallback"), exist_ok=True)

    # def should_ocr(self, text):
    #     cid_count = text.count("(cid:")
    #     return cid_count > 15 or (len(text) > 0 and cid_count / len(text) > 0.3) or not bool(re.search(r"[\u4e00-\u9fa5a-zA-Z]", text))

    def should_ocr(self, text):
        cid_unicode_count = len(re.findall(r'[\ue000-\uf8ff]', text))
        cid_marker_count = len(re.findall(r'\(cid:\d+\)', text))
        cid_count = cid_unicode_count + cid_marker_count
        if cid_count >= self.cid_threshold:
                print(f"CID 達 {cid_count}，使用 OCR 快取")
        return True

    def summarize_image(self, image_paths, prompt):
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        log("[解析圖片或整頁影像]")
        system_prompt = "你是一位針對圖片影像和表格影像進行提取內容的助手，請以敘述者的角度說明每張圖片中的資料或文本內容，例如數據、文字等，若是圖表也請說明其趨勢與關鍵數據"
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt, "images": image_paths}
                ]
            )
            return response['message']['content']
        except Exception as e:
            return f"❌ 圖像分析錯誤: {str(e)}"

    def detect_rotation_angle_easyocr(self, ocr_result, min_text_count=5, vertical_angle_range=(75, 105)):
        vertical_texts, short_texts, tall_boxes = 0, 0, 0
        total_texts = len(ocr_result)
        for (box, text, _) in ocr_result:
            x0, y0 = box[0]; x1, y1 = box[1]
            dx, dy = x1 - x0, y1 - y0
            angle = abs(np.arctan2(dy, dx) * 180 / np.pi)
            if vertical_angle_range[0] <= angle <= vertical_angle_range[1]: vertical_texts += 1
            if len(text.strip()) <= 1: short_texts += 1
            w = np.linalg.norm(np.array(box[0]) - np.array(box[1]))
            h = np.linalg.norm(np.array(box[0]) - np.array(box[3]))
            if h > w * 2: tall_boxes += 1
        if total_texts < min_text_count: return 0
        if vertical_texts / total_texts > 0.5 or short_texts / total_texts > 0.4 or tall_boxes / total_texts > 0.4:
            return 90
        return 0

    def get_title_from_above(self, image_path):
        with Image.open(image_path) as img:
            w, h = img.size
            crop = img.crop((0, 0, w, min(80, h)))
            result = self.reader.readtext(np.array(crop))
            return result[0][1] if result else "無標題"

    def rotate_original_pdf(self, file_path, rotated_pages):
        log("rotate this file")
        doc = fitz.open(file_path)
        for page_index in rotated_pages:
            page = doc[page_index - 1]
            page.set_rotation((page.rotation + 90) % 360)
            log(f"========== Page {page_index} has been rotated 90 degrees ==========")

        temp_path = file_path + ".rotated.pdf"
        doc.save(temp_path)
        doc.close()
        os.replace(temp_path, file_path)
        return file_path

    def process(self):
        start_time = time.time()
        text_results, table_results, image_results = [], [], []
        table_pages = []
        page_images = convert_from_path(self.pdf_path)
        doc = fitz.open(self.pdf_path)

        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                log(f"🔍 處理第 {i} 頁...")
                if page.extract_tables():
                    table_pages.append(i)
                    continue

                text = page.extract_text() or ""
                if self.should_ocr(text):
                    path = os.path.join(self.output_dir, "ocr_fallback", f"page_{i}.png")
                    img = page_images[i - 1]
                    img.save(path)
                    ocr_result = self.reader.readtext(np.array(img))
                    ocr_text = "\n".join([text for _, text, conf in ocr_result if conf > 0.5]) if ocr_result else ""
                    print(f"==========extract text from page {page}==========\n {ocr_text.strip()}")
                    prompt = f"以下圖片是一頁PDF文件的原始內容和擷取的文字如下:{ocr_text.strip()}，請直接敘述內容重點，條列其邏輯與段落，勿加入多餘引言或評論"
                    summary = self.summarize_image(path, prompt)
                    log(f"📝 第 {i} 頁文字摘要完成：{summary[:80]}...")
                    #self.vectorstore.add(summary, media_type="text", page=i, document_id=self.knowledge_id, source=path)
                    text_results.append({
                        "page": i,
                        "source": "llm",
                        "content": summary
                    })
                else:
                    #self.vectorstore.add("[文字]" + text, media_type="text", page=i, document_id=self.knowledge_id, source="text")
                    log(f"📝 第 {i} 頁純文字處理完成：{text[:80]}...")
                    text_results.append({
                        "page": i,
                        "source": "llm",
                        "content": text
                    })

                fitz_page = doc.load_page(i - 1)
                for img_index, img in enumerate(fitz_page.get_images(full=True)):
                    xref = img[0]
                    base = doc.extract_image(xref)
                    img_path = os.path.join(self.output_dir, "images", f"page{i}_img{img_index+1}.{base['ext']}")
                    with open(img_path, "wb") as f: f.write(base["image"])
                    prompt = "請描述圖片內容，若為圖表請指出類型、X/Y軸意義、趨勢與關鍵變化，若非圖表請描述主要構成與重要資訊"
                    summary = self.summarize_image(img_path, prompt)
                    log(f"🖼️ 第 {i} 頁圖片摘要完成：{summary[:80]}...")
                    #self.vectorstore.add("[圖片]" + summary, media_type="image", page=i, document_id=self.knowledge_id, source=img_path)
                    image_results.append({
                        "page": i,
                        "source": f"images/page{i}_img{img_index+1}.{base['ext']}",
                        "content": summary
                    })

        table_blocks = []
        rotated_pages = []
        for i in table_pages:
            log(f"📄 檢查表格頁第 {i} 頁旋轉與偵測...")
            img = page_images[i - 1]
            ocr_result = self.reader.readtext(np.array(img))
            angle = self.detect_rotation_angle_easyocr(ocr_result)
            if angle == 90:
                img = img.rotate(-90, expand=True)
                page_images[i - 1] = img
                rotated_pages.append(i)

            inputs = self.processor(images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.detector(**inputs)
            target_sizes = torch.tensor([img.size[::-1]]).to(self.device)
            results = self.processor.post_process_object_detection(outputs, threshold=0.6, target_sizes=target_sizes)[0]

            for j, box in enumerate(results["boxes"]):
                coords = box.tolist()  # [x1, y1, x2, y2]
                cropped = img.crop(coords)
                path = os.path.join(self.output_dir, "tables", f"page{i}_table{j+1}.png")
                cropped.save(path)
                ocr = self.reader.readtext(np.array(cropped))
                merged = "\n".join([r[1] for r in ocr])
                box_width = coords[2] - coords[0]
                table_blocks.append({
                    "page": i,
                    "image": path,
                    "ocr_text": merged,
                    "box_width": box_width
                })
        table_blocks.sort(key=lambda x: x["page"])
        grouped, temp = [], [table_blocks[0]] if table_blocks else []

        for i in range(1, len(table_blocks)):
            prev, curr = table_blocks[i-1], table_blocks[i]
            if (
                curr["page"] == prev["page"] + 1
                and abs(curr["box_width"] - prev["box_width"]) / max(prev["box_width"], 1) < 0.1
            ):
                temp.append(curr)
            else:
                grouped.append(temp)
                temp = [curr]

        for group_index, group in enumerate(grouped):
            texts = [g["ocr_text"] for g in group]
            imgs = [g["image"] for g in group]
            pages = [g["page"] for g in group]
            title = self.get_title_from_above(imgs[0])
            prompt = (
                f"以下是表格標題：{title}\n以下是 OCR 內容：\n{chr(10).join(texts)}\n"
                f"請統整摘要如下：\n1. 表格主題\n2. 每個欄位的意義\n3. 數據趨勢與重點"
            )
            summary = self.summarize_image(imgs, prompt)
            log(f"📋 表格組 {group_index + 1} 摘要完成：{summary[:80]}...")
            #table_results.append(summary)
            table_results.append({
                "page": pages,
                "source": imgs ,
                "title": title,
                "content": f"[ocr]\n{chr(10).join(texts)}\n[llm摘要]\n{summary}"
            })

        if rotated_pages:
            self.rotate_original_pdf(self.pdf_path, rotated_pages)

        end_time = time.time()
        log(f"✅ PDF 全部處理完成，用時 {end_time - start_time:.2f} 秒")

        return {"text": text_results, "table": table_results, "image": image_results}
    
    # 原先使用 table-transformer 的表格偵測流程，改為使用 pdfplumber 的 page.find_tables()
    # 並且僅在需要處理圖片摘要的情境下才使用 convert_from_path
    def optimized_process(self):
        import time
        start_time = time.time()
        text_results, table_results, image_results = [], [], []
        table_pages = []

        doc = fitz.open(self.pdf_path)
        pdf = pdfplumber.open(self.pdf_path)

        page_images = []  # 延後轉換圖片
        need_page_image = set()

        for i, page in enumerate(pdf.pages, start=1):
            log(f"🔍 處理第 {i} 頁...")

            text = page.extract_text() or ""
            if page.extract_tables():
                table_pages.append(i)
                need_page_image.add(i)

            if self.should_ocr(text):
                need_page_image.add(i)

            if doc[i - 1].get_images(full=True):
                need_page_image.add(i)

        # 只轉換需要的頁面圖片
        if need_page_image:
            log(f"🖼️ convert_from_path 轉換頁面: {sorted(need_page_image)}")
            page_images_all = convert_from_path(self.pdf_path)
            page_images = {
                i: page_images_all[i - 1] for i in need_page_image
            }

        # 處理純文字 + 圖片
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            if i in table_pages:
                continue

            if self.should_ocr(text):
                img = page_images[i]
                path = os.path.join(self.output_dir, "ocr_fallback", f"page_{i}.png")
                img.save(path)
                ocr_result = self.reader.readtext(np.array(img))
                ocr_text = "\n".join([text for _, text, conf in ocr_result if conf > 0.5]) if ocr_result else ""
                prompt = f"以下圖片是一頁PDF文件的原始內容和擷取的文字如下:{ocr_text.strip()}，請直接敘述內容重點，條列其邏輯與段落，勿加入多餘引言或評論"
                summary = self.summarize_image(path, prompt)
                log(f"📝 第 {i} 頁文字摘要完成：{summary[:80]}...")
                text_results.append({
                    "page": i,
                    "source": "ocr+llm",
                    "content": f"[ocr]{ocr_text.strip()}\n[llm]{summary}"
                })
            else:
                log(f"📝 第 {i} 頁純文字處理完成：{text[:80]}...")
                text_results.append({
                    "page": i,
                    "source": "ori",
                    "content": text
                })

            fitz_page = doc.load_page(i - 1)
            for img_index, img in enumerate(fitz_page.get_images(full=True)):
                xref = img[0]
                base = doc.extract_image(xref)
                img_path = os.path.join(self.output_dir, "images", f"page{i}_img{img_index+1}.{base['ext']}")
                with open(img_path, "wb") as f:
                    f.write(base["image"])
                prompt = "請描述圖片內容，若為圖表請指出類型、X/Y軸意義、趨勢與關鍵變化，若非圖表請描述主要構成與重要資訊"
                summary = self.summarize_image(img_path, prompt)
                log(f"🖼️ 第 {i} 頁圖片摘要完成：{summary[:80]}...")
                image_results.append({
                    "page": i,
                    "source": f"images/page{i}_img{img_index+1}.{base['ext']}",
                    "content": summary
                })

        # 處理表格頁
        table_blocks = []
        rotated_pages = []
        for i in table_pages:
            log(f"📄 檢查第 {i} 頁表格位置...")
            img = page_images[i]
            page = pdf.pages[i - 1]

            ocr_result = self.reader.readtext(np.array(img))
            angle = self.detect_rotation_angle_easyocr(ocr_result)
            if angle == 90:
                img = img.rotate(-90, expand=True)
                page_images[i] = img
                rotated_pages.append(i)

            tables = page.find_tables()
            for j, table in enumerate(tables):
                bbox = table.bbox  # (x0, top, x1, bottom)
                cropped = img.crop(bbox)
                path = os.path.join(self.output_dir, "tables", f"page{i}_table{j+1}.png")
                cropped.save(path)
                ocr = self.reader.readtext(np.array(cropped))
                merged = "\n".join([r[1] for r in ocr])
                box_width = bbox[2] - bbox[0]
                table_blocks.append({
                    "page": i,
                    "image": path,
                    "ocr_text": merged,
                    "box_width": box_width
                })

        # 表格群組邏輯
        table_blocks.sort(key=lambda x: x["page"])
        grouped, temp = [], [table_blocks[0]] if table_blocks else []

        for i in range(1, len(table_blocks)):
            print("===== groping table =====")
            prev, curr = table_blocks[i-1], table_blocks[i]
            if (
                curr["page"] == prev["page"] + 1
                and abs(curr["box_width"] - prev["box_width"]) / max(prev["box_width"], 1) < 0.1
            ):
                temp.append(curr)
            else:
                grouped.append(temp)
                temp = [curr]
        if temp: grouped.append(temp)

        for group_index, group in enumerate(grouped):
            texts = [g["ocr_text"] for g in group]
            imgs = [g["image"] for g in group]
            pages = [g["page"] for g in group]
            title = self.get_title_from_above(imgs[0])
            print(f"Title: {title}")
            print(f"OCR: {texts}")
            prompt = (
                f"以下是表格標題：{title}\n以下是 OCR 內容：\n{chr(10).join(texts)}\n"
                f"請統整摘要如下：\n1. 表格主題\n2. 每個欄位的意義\n3. 數據趨勢與重點"
            )
            summary = self.summarize_image(imgs, prompt)
            log(f"📋 表格組 {group_index + 1} 摘要完成：{summary[:80]}...")
            table_results.append({
                "page": pages,
                "source": imgs,
                "title": title,
                "content": f"[ocr]\n{chr(10).join(texts)}\n[llm摘要]\n{summary}"
            })

        if rotated_pages:
            self.rotate_original_pdf(self.pdf_path, rotated_pages)

        pdf.close()
        end_time = time.time()
        log(f"✅ PDF 全部處理完成，用時 {end_time - start_time:.2f} 秒")

        return {"text": text_results, "table": table_results, "image": image_results}



if __name__ == "__main__":
    processor = PdfProcessor("test.pdf")
    result = processor.optimized_process()
