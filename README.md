Image Processing Queue with FastAPI, MinIO, RabbitMQ, and Workers

This project implements an image processing queue using FastAPI, MinIO, RabbitMQ, and a worker service to reduce the size of images. The process starts by sending an image via FastAPI to MinIO, a high-performance object storage, where the image is stored. RabbitMQ is used to manage the communication and queuing of tasks, and a worker then processes the image to reduce its size before storing the processed image back into MinIO.

Table of Contents

Introduction

Technologies

Architecture Overview

Setup and Installation

API Documentation

Worker Functionality

How It Works

Testing


Introduction

This project is designed to demonstrate a fully functional image processing pipeline using various modern tools and technologies. It is a complete solution for processing large images asynchronously while managing storage efficiently. It is ideal for applications that require image manipulation, such as resizing, compression, or format conversion, but without blocking the main application flow.

Technologies

FastAPI: A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.

MinIO: High-performance, distributed object storage system that is API compatible with Amazon S3.

RabbitMQ: A message broker that enables applications to communicate with each other by sending messages through queues.

Worker (Celery): A distributed task queue system used to handle background tasks like image processing.

Pillow: A Python Imaging Library (PIL) fork used for processing images.

Docker: For containerizing the application and making deployment easier.

Architecture Overview

The system architecture can be divided into the following main components:

FastAPI API Server:

Exposes an API endpoint for uploading images.

Once an image is uploaded, it is stored in MinIO.

The FastAPI application sends a message to RabbitMQ to trigger the image processing task.

MinIO:

A scalable, high-performance object storage that holds the original and processed images.

It is used as a private S3-compatible object storage to store images.

RabbitMQ:

Acts as a messaging broker between the FastAPI API and the worker.

Once an image is uploaded to MinIO, the API sends a message to RabbitMQ containing details of the image to be processed.

Worker:

The worker listens to the RabbitMQ queue, retrieves the image information, processes the image (e.g., compresses it), and stores the processed image back into MinIO.

Setup and Installation

Follow these steps to set up the project on your local machine.

Prerequisites

Docker and Docker Compose: Ensure Docker and Docker Compose are installed. You can install them from here

and here

.

Python 3.8+: Required for FastAPI and the worker components.

1. Clone the repository
git clone https://github.com/yourusername/image-processing-queue.git
cd image-processing-queue

2. Build Docker Containers

To build and start the application with Docker Compose:

docker-compose up --build


This command will:

Set up the FastAPI application.

Set up MinIO (for object storage).

Set up RabbitMQ (for message queuing).

Start the worker service (which processes the image).

3. Environment Variables

Ensure you have the following environment variables set in a .env file:

MINIO_URL=http://minio:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_QUEUE=image_queue

API Documentation

The FastAPI application exposes the following endpoint:

POST /upload-image/

This endpoint accepts an image file and stores it in MinIO. It triggers the processing of the image by the worker.

Request:

file (form-data): The image file to upload.

Response:

200 OK: If the image was successfully uploaded and queued for processing.

400 Bad Request: If there is an error with the image upload.

Example Request using curl:

curl -X 'POST' \
  'http://localhost:8000/upload-image/' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@path_to_your_image.jpg'

Worker Functionality

The worker is responsible for processing images. Once it receives a message from RabbitMQ containing the image information, it performs the following steps:

Fetches the image from MinIO: Downloads the original image from the MinIO server.

Processes the image: Using Pillow, the image is resized, compressed, or otherwise manipulated based on predefined rules.

Stores the processed image back in MinIO: The processed image is uploaded to a different bucket or folder within MinIO.

How It Works

Upload: The user uploads an image through the FastAPI endpoint.

Storage: The image is stored in MinIO.

Queueing: The FastAPI application sends a message to RabbitMQ with the image details (e.g., name, path).

Processing: The worker listens to the RabbitMQ queue, processes the image (e.g., compressing it), and stores the processed image back into MinIO.

Testing

You can test the entire pipeline by using the API's upload endpoint and verifying that the image is processed correctly.

Start the application using Docker Compose.

Use the /upload-image/ endpoint to upload an image.

Verify that the processed image is stored in MinIO.

You can also inspect the logs to see the worker's activity.

<img width="1809" height="1006" alt="image" src="https://github.com/user-attachments/assets/6250be59-d585-40d1-9ef9-375306753961" />
