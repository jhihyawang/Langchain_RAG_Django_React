# tasks.py
import json

from background_task import background
from common.modules.processor.pdf_processor import PdfProcessor
from common.modules.processor.vector_store import VectorStoreHandler
from enterprise_assistant.models import Knowledge


@background(schedule=5)
def process_pdf_background(knowledge_id):
    knowledge = Knowledge.objects.get(id=knowledge_id)
    knowledge.processing_status = "processing"
    knowledge.save()

    try:
        processor = PdfProcessor(pdf_path=knowledge.file.path, knowledge_id=knowledge_id)
        result = processor.optimized_process()

        vectorstore = VectorStoreHandler("chroma_user_db")

        for media_type in ["text", "table", "image"]:
            for item in result.get(media_type, []):
                vectorstore.add(
                    content=item["content"],
                    page=json.dumps(item["page"] if isinstance(item["page"], list) else [item["page"]]),
                    document_id=knowledge_id,
                    media_type=media_type,
                    source=json.dumps(item["source"] if isinstance(item["source"], list) else [item["source"]])
                )

        chunks = vectorstore.list(knowledge_id)
        first_chunk = chunks[0]["content"] if chunks else ""
        knowledge.content = first_chunk
        knowledge.chunk = len(chunks)
        knowledge.processing_status = "done"
        knowledge.save()

    except Exception as e:
        knowledge.processing_status = "error"
        knowledge.save()
        print(f"❌ 處理失敗：{e}")
