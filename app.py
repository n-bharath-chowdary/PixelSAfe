import zipfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO
from PIL import Image
import numpy as np

app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "PixelSafe backend is live."

# ---------- LSB TEXT-IN-IMAGE ----------
def hide_text_in_image_bytes(img_bytes, text):
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    data = np.array(img)
    flat = data.flatten()
    flat = np.array(img).flatten().astype(np.uint8)
    message_bytes = text.encode("utf-8") + b'\xFF\xFE'  # EOF marker
    bit_array = np.unpackbits(np.frombuffer(message_bytes, dtype=np.uint8))

    if len(bit_array) > len(flat):
        raise ValueError("Message too long for image")

    flat[:len(bit_array)] = (flat[:len(bit_array)] & 0xFE) | bit_array  # 💥 FIXED HERE

    encoded = flat.reshape(data.shape)

    out = BytesIO()
    Image.fromarray(encoded, "RGBA").save(out, format="PNG")
    out.seek(0)
    return out

def extract_text_from_image_bytes(img_bytes):
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    flat = np.array(img).flatten()
    bits = flat & 1

    # Group bits into bytes
    total_bits = len(bits)
    num_bytes = total_bits // 8
    byte_array = np.packbits(bits[:num_bytes * 8])

    # Find EOF marker
    eof_index = byte_array.tobytes().find(b'\xFF\xFE')
    if eof_index != -1:
        byte_array = byte_array[:eof_index]

    return byte_array.tobytes().decode("utf-8", errors="ignore")


# ---------- IMAGE-IN-IMAGE ----------
def hide_image_in_image_bytes(cover_bytes, hidden_bytes):
    cover = np.array(Image.open(BytesIO(cover_bytes)).convert("RGBA").copy())
    hidden = np.array(Image.open(BytesIO(hidden_bytes)).convert("RGBA").copy())

    cover_flat = cover.reshape(-1)
    hidden_flat = hidden.reshape(-1)

    height, width = hidden.shape[:2]
    size_header = np.array([
        (height >> 8) & 0xFF, height & 0xFF,
        (width >> 8) & 0xFF, width & 0xFF
    ], dtype=np.uint8)

    payload = np.concatenate((size_header, hidden_flat))

    # Add padding to avoid browser/host side truncation issues
    padding = 8 - (len(payload) % 8) if (len(payload) % 8 != 0) else 0
    payload = np.pad(payload, (0, padding), constant_values=0)

    if len(payload) * 2 > len(cover_flat):
        raise ValueError("Cover image too small")

    payload_high = (payload >> 4) & 0x0F
    payload_low = payload & 0x0F

    indices = np.arange(len(payload) * 2)
    cover_encoded = np.copy(cover_flat)
    cover_encoded[indices[::2]] = (cover_flat[indices[::2]] & 0xF0) | payload_high
    cover_encoded[indices[1::2]] = (cover_flat[indices[1::2]] & 0xF0) | payload_low

    encoded = cover_encoded.reshape(cover.shape)
    out = BytesIO()
    Image.fromarray(encoded, "RGBA").save(out, format="PNG")
    out.seek(0)
    return out
    
def extract_image_from_image_bytes(stego_bytes):
    stego = np.array(Image.open(BytesIO(stego_bytes)).convert("RGBA").copy())
    stego_flat = stego.reshape(-1)

    header_high = stego_flat[:8:2] & 0x0F
    header_low = stego_flat[1:9:2] & 0x0F
    header = (header_high << 4) | header_low

    height = (header[0] << 8) + header[1]
    width = (header[2] << 8) + header[3]

    if height <= 0 or width <= 0 or height > 4000 or width > 4000:
        raise ValueError(f"Invalid decoded dimensions: {height}x{width}")

    expected_data_len = height * width * 4
    total_payload_bytes = expected_data_len + 4
    total_cover_bytes = total_payload_bytes * 2

    # fallback: if truncated, decode what you can
    if total_cover_bytes > len(stego_flat):
        total_cover_bytes = len(stego_flat)
        total_payload_bytes = total_cover_bytes // 2

    cover_payload = stego_flat[:total_cover_bytes].reshape(-1, 2)
    highs = cover_payload[:, 0] & 0x0F
    lows = cover_payload[:, 1] & 0x0F
    hidden_bytes = (highs << 4) | lows
    hidden_data = hidden_bytes[4:]  # skip size header

    actual_len = len(hidden_data)
    expected_len = expected_data_len

    if actual_len < expected_len:
        expected_len = (actual_len // 4) * 4  # fit to 4-channel pixels

    img_array = hidden_data[:expected_len].reshape(-1, 4).astype(np.uint8)
    img_array = img_array.reshape((img_array.shape[0] // width, width, 4))

    out = BytesIO()
    Image.fromarray(img_array, "RGBA").save(out, format="PNG")
    out.seek(0)
    return out

# ---------- ZIP-IN-VIDEO ----------
def hide_text_in_video_bytes(video_bytes, text):
    payload = text.encode('utf-8')
    return hide_file_in_video_bytes(video_bytes, payload, b'TXT')

def hide_image_in_video_bytes(video_bytes, image_bytes):
    return hide_file_in_video_bytes(video_bytes, image_bytes, b'IMG')

def hide_video_in_video_bytes(video_bytes, hidden_video_bytes):
    return hide_file_in_video_bytes(video_bytes, hidden_video_bytes, b'VID')

def hide_file_in_video_bytes(video_bytes, payload_bytes, tag=b'DAT'):
    """
    Combines video and payload with a tag header.
    Format: video + b<<<SPLIT>>> + TAG (3 bytes) + payload
    """
    combined = video_bytes + b'<<<SPLIT>>>' + tag + payload_bytes
    return BytesIO(combined)

def extract_file_from_video_bytes(video_bytes):
    parts = video_bytes.split(b'<<<SPLIT>>>')
    if len(parts) != 2:
        raise ValueError("No hidden content found in video")

    tag = parts[1][:3]
    payload = parts[1][3:]

    return tag, BytesIO(payload)

# ---------- ROUTES ----------
@app.route("/encode", methods=["POST"])
def encode():
    try:
        if 'image' in request.files and 'text' in request.form:
            image = request.files['image'].read()
            text = request.form['text']
            out = hide_text_in_image_bytes(image, text)
            return send_file(out, mimetype="image/png", download_name="encoded_image.png", as_attachment=True)

        elif 'cover_image' in request.files and 'image' in request.files:
            cover = request.files['cover_image'].read()
            secret = request.files['image'].read()
            out = hide_image_in_image_bytes(cover, secret)
            return send_file(out, mimetype="image/png", download_name="image_in_image.png", as_attachment=True)

        elif 'video' in request.files:
            video_bytes = request.files['video'].read()

            if 'text' in request.form:
                text = request.form['text']
                out = hide_text_in_video_bytes(video_bytes, text)
                return send_file(out, mimetype="video/mp4", download_name="video_with_text.mp4", as_attachment=True)

            elif 'hidden_image' in request.files:
                image_bytes = request.files['hidden_image'].read()
                out = hide_image_in_video_bytes(video_bytes, image_bytes)
                return send_file(out, mimetype="video/mp4", download_name="video_with_image.mp4", as_attachment=True)

            elif 'hidden_video' in request.files:
                hidden_vid = request.files['hidden_video'].read()
                out = hide_video_in_video_bytes(video_bytes, hidden_vid)
                return send_file(out, mimetype="video/mp4", download_name="video_with_video.mp4", as_attachment=True)

            return jsonify({"error": "No valid content to encode in video"}), 400


        return jsonify({"error": "Unsupported encode request"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/decode", methods=["POST"])
def decode():
    try:
        file = request.files['file']
        decode_type = request.form.get('decode_type', 'text')
        file_bytes = file.read()
        filename = file.filename.lower()

        if filename.endswith(('.png', '.jpg', '.jpeg')):
            if decode_type == 'text':
                text = extract_text_from_image_bytes(file_bytes)
                return jsonify({"decoded_text": text})
            elif decode_type == 'image':
                out = extract_image_from_image_bytes(file_bytes)
                return send_file(out, mimetype="image/png", download_name="decoded_image.png", as_attachment=True)

        elif filename.endswith(('.mp4', '.avi')):
            tag, content = extract_file_from_video_bytes(file_bytes)

            if tag == b'TXT':
                return jsonify({"decoded_text": content.read().decode('utf-8', errors='ignore')})
            elif tag == b'IMG':
                return send_file(content, mimetype="image/png", download_name="image_from_video.png", as_attachment=True)
            elif tag == b'VID':
                return send_file(content, mimetype="video/mp4", download_name="video_from_video.mp4", as_attachment=True)
            else:
                return send_file(content, mimetype="application/octet-stream", download_name="unknown_data", as_attachment=True)

        return jsonify({"error": "Unsupported file type"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

