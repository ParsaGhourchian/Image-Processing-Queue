import os
import json
import io
import time
import logging

import pika
from pika.exceptions import AMQPConnectionError
from minio import Minio
from minio.error import S3Error
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- تنظیمات محیط ----------
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


# ---------- اتصال به MinIO ----------
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_USE_SSL,
)


def ensure_bucket(bucket_name: str):
    """اگر باکت موجود نبود، آن را بساز"""
    found = minio_client.bucket_exists(bucket_name)
    if not found:
        logger.info(f"در حال ساخت باکت {bucket_name}")
        minio_client.make_bucket(bucket_name)


# ---------- اتصال با Retry به RabbitMQ ----------
def connect_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=60,
    )

    for attempt in range(1, 11):
        try:
            logger.info(f"تلاش برای اتصال به RabbitMQ... ({attempt}/10)")
            connection = pika.BlockingConnection(parameters)
            logger.info("اتصال به RabbitMQ موفق بود")
            return connection
        except AMQPConnectionError as e:
            logger.error(f"اتصال ناموفق بود: {e}")
            time.sleep(5)

    logger.critical("اتصال به RabbitMQ پس از ۱۰ تلاش ممکن نشد. Worker متوقف می‌شود.")
    raise SystemExit


# ---------- فشرده‌سازی تصویر ----------
def compress_image(data: bytes) -> bytes:
    """دریافت بایت تصویر و برگرداندن نسخه فشرده شده"""
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=50, optimize=True)
        return output.getvalue()


# ---------- پردازش پیام دریافت‌شده ----------
def process_message(ch, method, properties, body):
    try:
        message = json.loads(body.decode("utf-8"))
        logger.info(f"پیام دریافت شد: {message}")

        bucket_original = message["bucket_original"]
        bucket_processed = message["bucket_processed"]
        object_name = message["object_name"]

        ensure_bucket(bucket_original)
        ensure_bucket(bucket_processed)

        # دانلود فایل از MinIO
        response = minio_client.get_object(bucket_original, object_name)
        original_data = response.read()
        response.close()
        response.release_conn()

        # فشرده‌سازی
        compressed_data = compress_image(original_data)

        compressed_name = f"compressed_{object_name}"

        data_stream = io.BytesIO(compressed_data)
        size = len(compressed_data)

        # آپلود نسخه فشرده شده
        minio_client.put_object(
            bucket_processed,
            compressed_name,
            data_stream,
            length=size,
            content_type="image/jpeg",
        )

        logger.info(f"فایل پردازش شد و ذخیره شد: {bucket_processed}/{compressed_name}")

        # پیام انجام شد
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"خطا در پردازش پیام: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# ---------- اجرای Worker ----------
def main():
    ensure_bucket(BUCKET_ORIGINAL)
    ensure_bucket(BUCKET_PROCESSED)

    connection = connect_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=RABBITMQ_QUEUE,
        on_message_callback=process_message,
    )

    logger.info("Worker آماده و در حال گوش دادن به صف است...")
    channel.start_consuming()


if __name__ == "__main__":
    main()

