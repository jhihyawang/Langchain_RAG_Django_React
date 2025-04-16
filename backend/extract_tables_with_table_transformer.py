import os
import json
import torch
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
from transformers import DetrImageProcessor, TableTransformerForObjectDetection
from PyPDF2 import PdfReader, PdfWriter

# 初始化模型與處理器
ocr_engine = PaddleOCR(use_angle_cls=True, lang='chinese_cht')
table_model = TableTransformerForObjectDetection.from_pretrained("microsoft/table-transformer-detection")
processor = DetrImageProcessor.from_pretrained("microsoft/table-transformer-detection")

# 表格儲存設定
SAVE_DIR = "tables"
os.makedirs(SAVE_DIR, exist_ok=True)

# 判斷閾值設定
Y_TOP_THRESHOLD = 100
TITLE_CROP_SIZE = 200
WIDTH_SIMILARITY_THRESHOLD = 0.2
COL_COUNT_DIFF_MAX = 1

# 儲存結果
table_results = []
prev_box = None
prev_image = None
current_table = None
table_id_counter = 1
corrected_page_images = {}
corrected_pages = set()
rotated_pages = set()

# ➤ 判斷整頁主要文字方向
def detect_page_text_angle(image):
    result = ocr_engine.ocr(np.array(image), cls=True)
    angles = []
    for line in result:
        for box in line:
            if len(box) >= 3 and isinstance(box[2], dict):
                angles.append(box[2].get("angle", 0))
    if not angles:
        return 0
    dominant_angle = int(max(set(angles), key=angles.count))
    return dominant_angle if dominant_angle in [90, 270] else 0

# ➤ 是否有標題
def has_title_above(image: Image.Image, box):
    title_crop = image.crop((box[0], max(box[1] - TITLE_CROP_SIZE, 0), box[2], box[1]))
    result = ocr_engine.ocr(np.array(title_crop), cls=True)
    if not result or not isinstance(result[0], list):
        return False
    for line in result[0]:
        if isinstance(line, list) and len(line) >= 2:
            if len(line[1][0].strip()) >= 2:
                return True
    return False

# ➤ 擷取標題（已知頁面已旋轉為水平，不需判斷方向）
def extract_title(image: Image.Image, box):
    title_crop = image.crop((box[0], max(box[1] - TITLE_CROP_SIZE, 0), box[2], box[1]))
    result = ocr_engine.ocr(np.array(title_crop), cls=True)
    if not result or not isinstance(result[0], list):
        return ""
    texts = []
    for line in result[0]:
        if isinstance(line, list) and len(line) >= 2:
            texts.append(line[1][0])
    return "\n".join(texts).strip()

# ➤ 判斷是否為延續表格
def is_continued_table(curr_box, prev_box, curr_img, prev_img):
    if not prev_box:
        return False
    near_top = curr_box[1] < Y_TOP_THRESHOLD
    curr_width = curr_box[2] - curr_box[0]
    prev_width = prev_box[2] - prev_box[0]
    similar_width = abs(curr_width - prev_width) / max(prev_width, 1) < WIDTH_SIMILARITY_THRESHOLD
    no_title_above = not has_title_above(curr_img, curr_box)
    return near_top and similar_width and no_title_above

# ➤ 偵測表格
def detect_tables_in_page(image: Image.Image, page_number):
    global prev_box, prev_image, current_table, table_id_counter

    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = table_model(**inputs)
    target_sizes = torch.tensor([image.size[::-1]])
    results = processor.post_process_object_detection(outputs, threshold=0.7, target_sizes=target_sizes)[0]

    for idx, box in enumerate(results["boxes"]):
        box = [int(v) for v in box.tolist()]
        table_crop = image.crop((box[0], box[1], box[2], box[3]))
        filename = f"{SAVE_DIR}/page_{page_number}_table_{idx+1}.png"
        table_crop.save(filename)

        if is_continued_table(box, prev_box, image, prev_image):
            print(f"{filename} 是跨頁表格,  標題是{current_table["title"]}")
            current_table["pages"].append(page_number)
            current_table["images"].append(filename)
        else:
            title = extract_title(image, box)
            print(f"find table of {title}")
            current_table = {
                "table_id": f"table_{table_id_counter}",
                "pages": [page_number],
                "images": [filename],
                "title": title or "（無標題）"
            }
            table_results.append(current_table)
            table_id_counter += 1

        prev_box = box
        prev_image = image

# ➤ 重建旋轉後的 PDF
def rebuild_corrected_pdf(original_pdf, corrected_pages_dict, output_path):
    if not corrected_pages_dict:
        print("✅ 所有頁面角度已修正，無需重建 PDF")
        return

    reader = PdfReader(original_pdf)
    writer = PdfWriter()

    for i in range(len(reader.pages)):
        if i in corrected_pages_dict:
            img = corrected_pages_dict[i].convert("RGB")
            temp_path = f"temp_page_{i}.pdf"
            img.save(temp_path, "PDF")
            temp_reader = PdfReader(temp_path)
            writer.add_page(temp_reader.pages[0])
            os.remove(temp_path)
        else:
            writer.add_page(reader.pages[i])

    with open(output_path, "wb") as f:
        writer.write(f)

# ➤ 主流程
def process_pdf(pdf_path):
    images = convert_from_path(pdf_path, dpi=400)

    # 先處理旋轉頁面
    for i, img in enumerate(images):
        angle = detect_page_text_angle(img)
        if angle in [90, 270]:
            rotated = img.rotate(-angle, expand=True)
            corrected_page_images[i] = rotated
            images[i] = rotated  # 更新原圖像
            print(f"旋轉第{i}頁")
            rotated_pages.add(i + 1)

    # 再進行表格偵測與擷取
    for i, img in enumerate(images, start=1):
        print(f"📄 處理第 {i} 頁...")
        detect_tables_in_page(img, page_number=i)

    corrected_pdf_path = pdf_path.replace(".pdf", "_corrected.pdf")
    rebuild_corrected_pdf(pdf_path, corrected_page_images, corrected_pdf_path)

# ➤ 儲存 JSON 結果
def save_to_json(path="tables_with_titles.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已儲存表格資訊至：{path}")

# 🔧 執行
if __name__ == "__main__":
    pdf_path = "/Users/joy/LLM/群益1-30.pdf"
    process_pdf(pdf_path)
    save_to_json()
