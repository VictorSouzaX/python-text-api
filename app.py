from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO
from pathlib import Path
import base64, os

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

def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]

def draw_text_simple(draw, text, x, y, font, fill, align="left", max_width=0, align_vertical="top"):
    """Desenha texto com quebra de linha, alinhamento horizontal e vertical"""
    if not text:
        return y

    # Quebra o texto em linhas (manual ou por largura)
    all_lines = []
    lines = text.split("\n")

    for line in lines:
        if not line.strip():
            all_lines.append("")
            continue

        if max_width > 0:
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
                    current_line = word
            if current_line:
                all_lines.append(current_line)
        else:
            all_lines.append(line)

    # Usa métricas da fonte para altura real da linha
    ascent, descent = font.getmetrics()
    line_height = ascent + descent

    # Altura total do bloco
    total_height = len(all_lines) * line_height

    # Ajuste vertical
    if align_vertical == "center":
        y = y - total_height // 2
    elif align_vertical == "bottom":
        y = y - total_height

    # Renderiza linha a linha
    current_y = y
    for line in all_lines:
        if line.strip():
            draw_text_line(draw, line, x, current_y, font, fill, align, max_width)
        current_y += line_height

    return current_y

def draw_text_line(draw, text, x, y, font, fill, align="left", max_width=0):
    """Desenha uma linha de texto com alinhamento horizontal"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]

    if align == "left":
        draw.text((x, y), text, font=font, fill=fill)
    elif align == "center":
        if max_width > 0:
            x_center = x + (max_width - text_width) // 2
        else:
            x_center = x - text_width // 2
        draw.text((x_center, y), text, font=font, fill=fill)
    elif align == "right":
        if max_width > 0:
            x_right = x + max_width - text_width
        else:
            x_right = x - text_width
        draw.text((x_right, y), text, font=font, fill=fill)

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

    text = str(j.get("texto") or j.get("text") or "")
    x = to_px(j.get("x"), 0)
    y = to_px(j.get("y"), 0)
    fs = to_px(j.get("font_size"), 40)
    max_width = to_px(j.get("max_width"), 0)
    align = str(j.get("align", "left")).lower()
    if align not in ("left", "center", "right"):
        align = "left"
    align_vertical = str(j.get("align_vertical", "top")).lower()
    if align_vertical not in ("top", "center", "bottom"):
        align_vertical = "top"
    color = j.get("color", "#000000")
    opacity = to_px(j.get("opacity"), 100)
    font_name = j.get("font", "Archivo-Regular")

    draw = ImageDraw.Draw(img)
    font = load_font(fs, font_name, "font_archivo")
    fill = color_to_rgba(color, opacity)

    try:
        final_y = draw_text_simple(draw, text, x, y, font, fill, align, max_width, align_vertical)
    except Exception as e:
        return jsonify(error=f"Falha ao desenhar texto: {e}"), 500

    try:
        out_b64 = encode_b64_image(img, "PNG")
        return jsonify(image_b64=out_b64, width=img.width, height=img.height)
    except Exception as e:
        return jsonify(error=f"Falha ao codificar imagem: {e}"), 500

@app.get("/health")
def health():
    return "ok", 200

@app.get("/test")
def test():
    return jsonify({
        "status": "ok",
        "message": "API funcionando",
        "align_vertical_supported": True,
        "supported_align_vertical": ["top", "center", "bottom"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
