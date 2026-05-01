import os
import io
import hashlib
from PIL import Image, ImageDraw, ImageFont
import cloudinary.uploader
from werkzeug.utils import secure_filename


def compress_image(file, max_size=(1280, 1280), quality=75):
    img = Image.open(file)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail(max_size)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)

    return buffer


def upload_to_cloudinary(file):
    result = cloudinary.uploader.upload(
        file,
        quality="auto",
        fetch_format="auto"
    )
    return result["secure_url"]


def generate_avatar(name):
    if not name:
        name = "User"

    initials = "".join([n[0] for n in name.split()][:2]).upper()

    filename = hashlib.md5(name.encode()).hexdigest() + ".png"
    path = os.path.join("static/avatars", filename)

    if os.path.exists(path):
        return filename

    img = Image.new('RGB', (200, 200), color=(13, 138, 188))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 80)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    draw.text(((200 - w) / 2, (200 - h) / 2), initials, fill="white", font=font)

    os.makedirs("static/avatars", exist_ok=True)
    img.save(path)

    return filename
