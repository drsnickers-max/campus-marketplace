"""Safe image uploads. Uses Cloudinary when configured, else a local folder."""
import logging
import os
import uuid

from flask import current_app, url_for
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}


class ImageError(Exception):
    """Raised with a user-friendly message when an upload is rejected."""


def _sniff(head):
    """Identify the real format from the file's first bytes, not from its name."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def cloudinary_enabled():
    cfg = current_app.config
    return all(cfg.get(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"))


def configure_cloudinary(app):
    if all(app.config.get(k) for k in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")):
        import cloudinary
        cloudinary.config(cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
                          api_key=app.config["CLOUDINARY_API_KEY"],
                          api_secret=app.config["CLOUDINARY_API_SECRET"], secure=True)


def save_image(file_storage):
    name = secure_filename(file_storage.filename or "") or "image"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageError(f"'{name}': only JPG, PNG, WEBP or GIF images are allowed.")

    limit = current_app.config["MAX_IMAGE_BYTES"]
    data = file_storage.read(limit + 1)
    if not data:
        raise ImageError(f"'{name}' is empty.")
    if len(data) > limit:
        raise ImageError(f"'{name}' is too large (max {limit // (1024 * 1024)} MB).")
    fmt = _sniff(data[:12])
    if fmt is None or fmt != ("jpg" if ext == "jpeg" else ext):
        raise ImageError(f"'{name}' is not a valid {ext.upper()} image.")

    if cloudinary_enabled():
        try:
            import cloudinary.uploader
            res = cloudinary.uploader.upload(data, folder="campus_marketplace", resource_type="image")
        except Exception:
            logger.exception("Cloudinary upload failed")
            raise ImageError("Image upload failed. Please try again.")
        return {"url": res["secure_url"], "public_id": res["public_id"], "format": res.get("format", fmt),
                "bytes": res.get("bytes", len(data)), "provider": "cloudinary"}

    filename = f"{uuid.uuid4().hex}.{fmt}"
    folder = current_app.config["UPLOAD_FOLDER"]
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, filename), "wb") as fh:
            fh.write(data)
    except OSError:
        logger.exception("Could not save uploaded image")
        raise ImageError("Could not save the image. Please try again.")
    return {"url": url_for("static", filename=f"uploads/{filename}"), "public_id": filename,
            "format": fmt, "bytes": len(data), "provider": "local"}


def delete_images(images):
    """Best-effort cleanup; failures are logged, never shown to the user."""
    for img in images or []:
        try:
            if img.get("provider") == "cloudinary":
                import cloudinary.uploader
                cloudinary.uploader.destroy(img["public_id"])
            elif img.get("provider") == "local":
                os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], secure_filename(img["public_id"])))
        except Exception:
            logger.warning("Could not delete image %s", img.get("public_id"))


def save_images(files):
    saved = []
    try:
        for f in files:
            saved.append(save_image(f))
    except ImageError:
        delete_images(saved)  # don't leave half-uploaded sets behind
        raise
    return saved
