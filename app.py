import os
from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO
from pathlib import Path
import base64

app = Flask(__name__)

def to_px(value, default):
    try:
        s = str(value).strip().lower().replace("px", "")
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

def decode_b64_image(data):
    b64 = str(data)
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    img = Image.open(BytesIO(raw))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img

def encode_b64_image(img, fmt="PNG"):
    buf = BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def color_to_rgba(color, opacity=100):
    try:
        rgba = ImageColor.getcolor(str(color), "RGBA")
    except Exception:
        rgba = (0, 0, 0, 255)
    op = max(0, min(100, int(to_px(opacity, 100))))
    a = int(rgba[3] * (op / 100.0))
    return (rgba[0], rgba[1], rgba[2], a)

def load_font(size, font_name, fonts_dir=None):
    size = int(size)
    root = Path(fonts_dir or "font_archivo")
    if font_name:
        p = root / font_name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
        if not str(font_name).lower().endswith((".ttf", ".otf", ".ttc")):
            for ext in (".ttf", ".otf", ".ttc"):
                q = root / (str(font_name) + ext)
                if q.exists():
                    try:
                        return ImageFont.truetype(str(q), size)
                    except Exception:
                        pass
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()

def draw_text_simple(draw, text, x, y, font, fill, align="left", max_width=0, align_vertical="top"):
    if not text:
        return y

    all_lines = []
    lines = text.split("\n")
    for line in lines:
        if not line.strip():
            all_lines.append("")
            continue

        if max_width and max_width > 0:
            words = line.split()
            current_line = ""
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                line_width = bbox[2] - bbox[0]
                if line_width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        all_lines.append(current_line)
                    else:
                        all_lines.append(word)
                        current_line = ""
                        continue
                    current_line = word
            if current_line:
                all_lines.append(current_line)
        else:
            all_lines.append(line)

    try:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
    except Exception:
        try:
            line_height = int(font.size * 1.2)
        except Exception:
            line_height = 16

    total_height = len(all_lines) * line_height

    if align_vertical == "top":
        box_top = int(y)
    elif align_vertical == "center":
        box_top = int(round(y - total_height / 2))
    elif align_vertical == "bottom":
        box_top = int(round(y - total_height))
    else:
        box_top = int(y)

    current_y = box_top
    for line in all_lines:
        if line == "":
            current_y += line_height
            continue

        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        if align == "center":
            text_x = int(round(x - text_width / 2))
        elif align == "right":
            text_x = int(round(x - text_width))
        else:
            text_x = int(round(x))

        draw.text((text_x, current_y), line, font=font, fill=fill)
        current_y += line_height

    return current_y

@app.post("/process-text")
def process_text():
    j = request.get_json(silent=True) or {}

    img_b64 = j.get("image_b64") or j.get("image")
    if not img_b64:
        return jsonify(error="image_b64 ausente"), 400

    try:
        img = decode_b64_image(img_b64)
    except Exception as e:
        return jsonify(error=f"Falha ao decodificar imagem: {e}"), 400

    textos = j.get("textos", None)
    if textos is None:
        textos = [j]

    if not isinstance(textos, list):
        return jsonify(error="Campo 'textos' deve ser uma lista"), 400

    try:
        for t in textos:
            text = str(t.get("texto") or t.get("text") or "")
            x = to_px(t.get("x"), 0)
            y = to_px(t.get("y"), 0)
            fs = to_px(t.get("font_size"), 40)
            max_width = to_px(t.get("max_width"), 0)
            align = str(t.get("align", "left")).lower()
            if align not in ("left", "center", "right"):
                align = "left"
            align_vertical = str(t.get("align_vertical", "top")).lower()
            if align_vertical not in ("top", "center", "bottom"):
                align_vertical = "top"
            color = t.get("color", "#000000")
            opacity = to_px(t.get("opacity"), 100)
            font_name = t.get("font", "Archivo-Regular")

            layer = Image.new("RGBA", img.size, (0,0,0,0))
            draw = ImageDraw.Draw(layer)
            font = load_font(fs, font_name, "font_archivo")
            fill = color_to_rgba(color, opacity)

            draw_text_simple(draw, text, x, y, font, fill, align, max_width, align_vertical)
            img = Image.alpha_composite(img, layer)
    except Exception as e:
        return jsonify(error=f"Falha ao desenhar texto: {e}"), 500

    try:
        out_b64 = encode_b64_image(img, "PNG")
        resp = {"image_b64": out_b64, "width": img.width, "height": img.height}
        return jsonify(resp)
    except Exception as e:
        return jsonify(error=f"Falha ao codificar imagem: {e}"), 500

@app.get("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
