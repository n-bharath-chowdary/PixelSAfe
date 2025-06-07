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
    # Convert hidden image to PNG (force RGBA, uncompressed)
    hidden_img = Image.open(BytesIO(hidden_bytes)).convert("RGBA")
    hidden_io = BytesIO()
    hidden_img.save(hidden_io, format="PNG", optimize=False, compress_level=0)
    hidden_io.seek(0)
    hidden = np.array(Image.open(hidden_io))  # Reload cleanly after save

    # Process cover image as usual
    cover = np.array(Image.open(BytesIO(cover_bytes)).convert("RGBA"))

    # (Continue your existing logic below...)
    cover_flat = cover.reshape(-1)
    hidden_flat = hidden.reshape(-1)

    height, width = hidden.shape[:2]
    size_header = np.array([
        (height >> 8) & 0xFF, height & 0xFF,
        (width >> 8) & 0xFF, width & 0xFF
    ], dtype=np.uint8)

    payload = np.concatenate((size_header, hidden_flat))

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
    Image.fromarray(encoded, "RGBA").save(out, format="PNG", optimize=False, compress_level=0)
    out.seek(0)
    return out
    
def extract_image_from_image_bytes(stego_bytes):
    stego = np.array(Image.open(BytesIO(stego_bytes)).convert("RGBA").copy())
    stego_flat = stego.reshape(-1)
    # Extract header bytes from first 8 stego bytes (4 payload bytes)
    # Recall two cover bytes = one payload byte (high nibble from first byte, low nibble from second byte)
    header_high = stego_flat[:8:2] & 0x0F  # nibbles from even indices
    header_low = stego_flat[1:9:2] & 0x0F  # nibbles from odd indices
    header = (header_high << 4) | header_low
    height = int((header[0] << 8) + header[1])
    width = int((header[2] << 8) + header[3])
    if height <= 0 or width <= 0 or height > 4000 or width > 4000:
        raise ValueError(f"Invalid decoded dimensions: {height}x{width}")
    expected_data_len = height * width * 4  # 4 bytes per pixel (RGBA)
    total_payload_bytes = expected_data_len + 4  # header 4 bytes + pixel data
    total_cover_bytes = total_payload_bytes * 2  # 2 cover bytes per payload byte
    # If cover image truncated, fallback on available data
    if total_cover_bytes > len(stego_flat):
        total_cover_bytes = len(stego_flat)
        total_payload_bytes = total_cover_bytes // 2
    cover_payload = stego_flat[:total_cover_bytes].reshape(-1, 2)
    highs = cover_payload[:, 0] & 0x0F
    lows = cover_payload[:, 1] & 0x0F
    hidden_bytes = (highs << 4) | lows
    hidden_data = hidden_bytes[4:]  # skip 4-byte header
    # If we don't have enough data for expected pixels, reduce to fit multiples of 4 bytes (per pixel)
    actual_len = len(hidden_data)
    if actual_len < expected_data_len:
        expected_data_len = (actual_len // 4) * 4
    # Reshape hidden image (height x width x 4)
    try:
        img_array = hidden_data[:expected_data_len].reshape((height, width, 4)).astype(np.uint8)
    except Exception as e:
        # In case reshape error (e.g. dimensions mismatch), fallback to safe reshape by counting pixels
        pixel_count = expected_data_len // 4
        img_array = hidden_data[:pixel_count*4].reshape((pixel_count, 4)).astype(np.uint8)
        # Further reshape to height and width might fail, so returning whatever possible
        # Optional: pad or crop accordingly or raise a meaningful error
        pass
    # Save extracted image bytes as PNG
    out = BytesIO()
    Image.fromarray(img_array, "RGBA").save(out, format="PNG", optimize=False, compress_level=0)
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
            cover_file = request.files['cover_image']
            secret_file = request.files['image']

            # Warn or block if hidden image is not PNG
            if not secret_file.filename.lower().endswith('.png'):
                return jsonify({"error": "Hidden image must be a PNG file to ensure accurate decoding."}), 400

            cover = cover_file.read()
            secret = secret_file.read()
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

