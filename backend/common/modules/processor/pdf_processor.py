import os
import re
import time
from datetime import datetime

import cv2
import fitz  # PyMuPDF
import numpy as np
import ollama
import pdfplumber
import torch
from easyocr import Reader
from pdf2image import convert_from_path
from PIL import Image, ImageDraw
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
        else:
            print(f"文字符合標準，使用pdfplumber")
            return False

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
        
    def get_title_from_above(self, img, coords):
        # 計算標題範圍
        x1, y1, x2, y2 = coords
        print(f"表格提取範圍:{[x1, y1, x2, y2]}")

        # X軸範圍：從表格最左邊到表格寬度的 3/4
        x_range = (x1*0.8, x1 + (x2 - x1) * 0.75)
        
        # Y軸範圍：從表格上方的空間的 1/2 開始到表格上邊緣
        print(y1*0.4)
        y_range = (y1*0.6, y1)

        print(f"標題提取範圍:{[x_range[0], y_range[0], x_range[1], y_range[1]]}")
                # 在原始圖像上畫出標題範圍
                
        draw = ImageDraw.Draw(img)
        draw.rectangle([x_range[0], y_range[0], x_range[1], y_range[1]], outline="red", width=3)

        # 顯示圖片
        img.show()
        # 裁切圖片
        crop = img.crop((x_range[0], y_range[0], x_range[1], y_range[1]))

        # 使用OCR讀取裁切區域的文字
        result = self.reader.readtext(np.array(crop))

        # 將所有文字合併為一個字串，用換行分隔
        return "\n".join([item[1] for item in result]) if result else "無標題"


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
    
    def calculate_table_area_each_page(self,box,total_table_area) -> float:
        x1, y1, x2, y2 = box
        table_area = abs((x2 - x1) * (y2 - y1))
        total_table_area += table_area
        return total_table_area
        
    def extract_table(self,img,i,j,box,table_blocks):
        coords = box.tolist()  # [x1, y1, x2, y2]
        expand_coords = [coords[0]*0.9,coords[1]*0.75,coords[2]*1.1,coords[3]*1.1]
        cropped = img.crop(expand_coords)
        path = os.path.join(self.output_dir, "tables", f"page{i}_table{j+1}.png")
        cropped.save(path)
        ocr = self.reader.readtext(np.array(cropped))
        merged = "\n".join([r[1] for r in ocr])
        box_width = coords[2] - coords[0]
        table_title = self.get_title_from_above(img, coords)
        print(f"檢測到的標題：{table_title}")
        table_blocks.append({
            "page": i,
            "image": path,
            "ocr_text": merged,
            "box_width": box_width,
            "title": table_title
        })
        return table_blocks

    def group_tables_summary(self,table_blocks,table_results):
        # 表格群組邏輯
        table_blocks.sort(key=lambda x: x["page"])
        grouped, temp = [], [table_blocks[0]] if table_blocks else []

        for i in range(1, len(table_blocks)):
            print("===== groping table =====")
            prev, curr = table_blocks[i-1], table_blocks[i]
            if (
                curr["page"] == prev["page"] + 1
                and abs(curr["box_width"] - prev["box_width"]) / max(prev["box_width"], 1) < 0.1
                and curr["title"] == "無標題" 
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
            title = [g["title"] for g in group][0] #跨頁表格以第一個表格標題(因為其他的應該都是"無標題")
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
                "content": f"表格標題: {title}\n[ocr]\n{chr(10).join(texts)}\n[llm摘要]\n{summary}"
            })
        return table_results

    def extract_texts(self,page,i,page_images,text_results):
        text = page.extract_text() or ""
        if self.should_ocr(text):
            img = page_images[i]
            path = os.path.join(self.output_dir, "ocr_fallback", f"page_{i}.png")
            img.save(path)
            ocr_result = self.reader.readtext(np.array(img))
            ocr_text = "\n".join([text for _, text, conf in ocr_result if conf > 0.5]) if ocr_result else ""
            prompt = f"以下圖片是一頁PDF文件的原始內容和擷取的文字如下:{ocr_text.strip()}，請直接敘述內容重點，條列其邏輯與段落，勿加入多餘引言或評論"
            summary = self.summarize_image(path, prompt)
            log(f"第 {i} 頁文字 OCR+LLM 摘要完成：[ocr]{ocr_text.strip()}\n[llm]{summary}")
            text_results.append({
                "page": i,
                "source": "ocr+llm",
                "content": f"[ocr]{ocr_text.strip()}\n[llm]{summary}"
            })
        else:
            log(f"第 {i} 頁純文字處理完成：{text}...")
            text_results.append({
                "page": i,
                "source": "ori",
                "content": text
            })
        return text_results
            
    def extract_imgs(self,doc,i,image_results):
        # 處理圖片
        fitz_page = doc.load_page(i - 1)
        image_list = fitz_page.get_images(full=True)
        print(f"📄 第 {i} 頁找到 {len(image_list)} 張圖片")

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            img_name = f"page_{i}_img_{img_index + 1}.{image_ext}"
            img_path = os.path.join(self.output_dir, "images", img_name)
            with open(img_path, "wb") as f:
                f.write(image_bytes)
            print(f"圖片 {img_index + 1} 已儲存：{img_path}")

            img = Image.open(img_path)
            img_array = np.array(img)
            ocr_result = self.reader.readtext(img_array)
            ocr_text = "\n".join([text for _, text, conf in ocr_result if conf > 0.5]) if ocr_result else ""
            print(f"OCR 結果: {ocr_result}")

            if ocr_text:
                print(f"OCR 結果: {ocr_text}")
                prompt = "請描述圖片內容，若為圖表請指出類型、X/Y軸意義、趨勢與關鍵變化，若非圖表請描述主要構成與重要資訊"
                summary = self.summarize_image(img_path, prompt)
                log(f"🖼️ 第 {i} 頁圖片摘要完成：[ocr]{ocr_text}\n[llm]{summary[:80]}...")
                image_results.append({
                    "page": i,
                    "source": img_path,
                    "content": summary
                })
            else:
                log(f"⚠️ 第 {i} 頁第 {img_index + 1} 張圖片 OCR 結果少於 8 字，已略過")
        return image_results
    
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

        # 首先檢查是否有表格頁，並將表格頁標記出來
        for i, page in enumerate(pdf.pages, start=1):
            log(f"🔍 處理第 {i} 頁...")

            text = page.extract_text() or ""
            if page.extract_tables():  # 如果該頁包含表格
                table_pages.append(i)
                need_page_image.add(i)

            if self.should_ocr(text):  # 判斷是否需要OCR
                need_page_image.add(i)

            if doc[i - 1].get_images(full=True):  # 檢查是否有圖片
                need_page_image.add(i)

        # 只轉換需要的頁面圖片
        if need_page_image:
            log(f"🖼️ convert_from_path 轉換頁面: {sorted(need_page_image)}")
            page_images_all = convert_from_path(self.pdf_path)
            page_images = {i: page_images_all[i - 1] for i in need_page_image}

        # 首先處理表格頁
        table_blocks = []
        rotated_pages = []
        for i in table_pages:
            log(f"📄 檢查第 {i} 頁表格位置...")
            img = page_images[i]
            page = pdf.pages[i - 1]
            #先判斷是否需要轉向
            ocr_result = self.reader.readtext(np.array(img))
            angle = self.detect_rotation_angle_easyocr(ocr_result)
            if angle == 90:
                img = img.rotate(-90, expand=True)
                page_images[i] = img
                ocr_result = self.reader.readtext(np.array(img))
                rotated_pages.append(i)
            #先檢測表格座標
            inputs = self.processor(images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.detector(**inputs)
            target_sizes = torch.tensor([img.size[::-1]]).to(self.device)
            results = self.processor.post_process_object_detection(outputs, threshold=0.6, target_sizes=target_sizes)[0]
            
            #頁面長寬
            # 獲取頁面邊界資訊
            page_rect = page.rects[0]
            page_width = page_rect['x1'] - page_rect['x0']  # 計算寬度
            page_height = page_rect['y1'] - page_rect['y0']  # 計算高度
            page_area = page_width * page_height
            total_table_area = 0
            for j, box in enumerate(results["boxes"]):
                # 計算表格佔頁面面積的比例
                total_table_area = self.calculate_table_area_each_page(box,total_table_area)
                table_blocks = self.extract_table(img,i,j,box,table_blocks)
                
            table_area_ratio =  total_table_area / page_area if page_area > 0 else 0.0
            log(f"第 {i} 頁的表格佔頁面面積比例為：{table_area_ratio:.2f}")
             # 如果表格佔比小於50%，進行文字和圖片提取
            if table_area_ratio < 0.5:
                log(f"表格佔比小於50%，開始進行文字和圖片提取...")
                text_results = self.extract_texts(page, i, page_images, text_results)
                image_results = self.extract_imgs(doc, i, image_results)
                
        table_results = self.group_tables_summary(table_blocks,table_results)
        # 表格處理完成後，再處理沒有表格的頁面
        for i, page in enumerate(pdf.pages, start=1):
            if i in table_pages:
                continue  # 跳過表格頁
            text_results = self.extract_texts(page,i,page_images,text_results)
            # 處理圖片
            image_results = self.extract_imgs(doc,i,image_results)
            
        if rotated_pages:
            self.rotate_original_pdf(self.pdf_path, rotated_pages)

        pdf.close()
        end_time = time.time()
        log(f"✅ PDF 全部處理完成，用時 {end_time - start_time:.2f} 秒")

        return {"text": text_results, "table": table_results, "image": image_results}


if __name__ == "__main__":
    processor = PdfProcessor("test.pdf")
    result = processor.optimized_process()
