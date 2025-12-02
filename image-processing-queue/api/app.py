import os
import io
import time
import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from minio import Minio
from minio.error import S3Error
from PIL import Image
import pika

app = FastAPI(title="Image Processing Queue API")

# ---------- تنظیمات از env ----------
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"

BUCKET_ORIGINAL = os.getenv("MINIO_BUCKET_ORIGINAL", "original-images")
BUCKET_PROCESSED = os.getenv("MINIO_BUCKET_PROCESSED", "processed-images")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "pass")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "image_tasks")

# ---------- MinIO Client ----------
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_USE_SSL,
)


def ensure_bucket(bucket_name: str):
    """اگر باکت وجود ندارد، بسازش"""
    found = minio_client.bucket_exists(bucket_name)
    if not found:
        minio_client.make_bucket(bucket_name)


@app.on_event("startup")
def startup_event():
    # مطمئن شو باکت‌ها موجودند
    ensure_bucket(BUCKET_ORIGINAL)
    ensure_bucket(BUCKET_PROCESSED)


def publish_message(message: dict):
    """ارسال پیام به RabbitMQ"""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # تضمین وجود صف
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    body = json.dumps(message).encode("utf-8")

    channel.basic_publish(
        exchange="",
        routing_key=RABBITMQ_QUEUE,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2  # پیام پایدار
        ),
    )
    connection.close()


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    # چک کردن نوع فایل
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="فقط فایل‌های تصویری مجاز هستند")

    try:
        # خواندن محتوا
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="فایل خالی است")

        # اسم یکتا برای فایل
        timestamp = int(time.time())
        object_name = f"{timestamp}_{file.filename}"

        # آپلود به MinIO در باکت original
        data_stream = io.BytesIO(content)
        data_stream.seek(0, io.SEEK_END)
        size = data_stream.tell()
        data_stream.seek(0)

        minio_client.put_object(
            BUCKET_ORIGINAL,
            object_name,
            data_stream,
            length=size,
            content_type=file.content_type,
        )

        # ساخت پیام برای صف
        message = {
            "bucket_original": BUCKET_ORIGINAL,
            "bucket_processed": BUCKET_PROCESSED,
            "object_name": object_name,
        }

        publish_message(message)

        return JSONResponse(
            content={
                "message": "فایل دریافت شد و برای پردازش در صف قرار گرفت",
                "object_name": object_name,
            }
        )

    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"اشکال در MinIO: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطای غیرمنتظره: {str(e)}")


@app.get("/")
def root():
    return {"status": "ok", "message": "Image Processing Queue API"}
