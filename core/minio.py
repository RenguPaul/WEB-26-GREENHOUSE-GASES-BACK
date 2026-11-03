from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from minio import Minio

from core.config import settings


MINIO_PUBLIC_URL = (
    f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}"
)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
}


client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=settings.MINIO_SECURE,
)


def ensure_bucket_exists() -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def validate_image(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Изображение должно быть в формате "
                "JPEG, PNG или WEBP"
            ),
        )


def validate_video(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Видео должно быть в формате "
                "MP4, WEBM или MOV"
            ),
        )


async def upload_file(
    file: UploadFile,
    prefix: str,
) -> str:
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Загруженный файл пуст",
        )

    extension = ""

    if file.filename and "." in file.filename:
        extension = "." + file.filename.rsplit(
            ".",
            1,
        )[1].lower()

    filename = f"{prefix}_{uuid4().hex}{extension}"

    ensure_bucket_exists()

    client.put_object(
        settings.MINIO_BUCKET,
        filename,
        BytesIO(content),
        length=len(content),
        content_type=(
            file.content_type
            or "application/octet-stream"
        ),
    )

    return filename


def get_file_url(
    filename: str | None,
) -> str | None:
    if not filename:
        return None

    return f"{MINIO_PUBLIC_URL}/{filename}"