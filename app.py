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

def load_font(size, font_name):
    size = int(size)
    root = Path("font_archivo")  # fixo no seu caso
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

# ---------- PARSER PARA <b>...</b> ----------
def tokenize_rich(text):
    segs = []
    bold = False
    buf = []
    i = 0
    n = len(text)
    while i < n:
        if text[i:i+3].lower() == "<b>":
            if buf:
                segs.append(("".join(buf), bold))
                buf = []
            bold = True
            i += 3
            continue
        if text[i:i+4].lower() == "</b>":
            if buf:
                segs.append(("".join(buf), bold))
                buf = []
            bold = False
            i += 4
            continue
        buf.append(text[i])
        i += 1
    if buf:
        segs.append(("".join(buf), bold))
    return segs

def split_segments_by_newline(segments):
    lines = [[]]
    for txt, bold in segments:
        parts = txt.split("\n")
        for idx, part in enumerate(parts):
            if part:
                lines[-1].append((part, bold))
            if idx < len(parts) - 1:
                lines.append([])
    return lines

def segments_width(draw, segs, font_regular, font_bold):
    total = 0
    for txt, is_bold in segs:
        if not txt:
            continue
        font = font_bold if is_bold else font_regular
        total += draw.textlength(txt, font=font)
    return int(total)

def layout_rich_lines(text, draw, font_regular, font_bold, max_width):
    segs = tokenize_rich(text)
    logical_lines = split_segments_by_newline(segs)
    out = []
    for seg_line in logical_lines:
        out.append(seg_line)
    return out

def draw_rich_line(draw, x, y, line_segs, font_regular, font_bold, fill):
    cx = x
    for tok, is_bold in line_segs:
        if not tok:
            continue
        font = font_bold if is_bold else font_regular
        draw.text((cx, y), tok, font=font, fill=fill)
        cx += draw.textlength(tok, font=font)

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
    line_height = to_px(j.get("line_height"), int(fs * 1.2))
    max_width = to_px(j.get("max_width"), 0)
    align = str(j.get("align", "left")).lower()
    if align not in ("left", "center", "right"):
        align = "left"
    color = j.get("color", "#000000")
    opacity = to_px(j.get("opacity"), 100)
    font_name = j.get("font", "Archivo-Regular")

    draw = ImageDraw.Draw(img)
    font_regular = load_font(fs, font_name)
    font_bold = load_font(fs, "Archivo-Bold")
    fill = color_to_rgba(color, opacity)

    rich_lines = layout_rich_lines(text, draw, font_regular, font_bold, max_width)

    for seg_line in rich_lines:
        if align == "left" or not max_width:
            x_line = x
        else:
            w_line = segments_width(draw, seg_line, font_regular, font_bold)
            if align == "center":
                x_line = x + (max_width - w_line) // 2
            else:
                x_line = x + (max_width - w_line)
        draw_rich_line(draw, x_line, y, seg_line, font_regular, font_bold, fill)
        y += line_height

    out_b64 = encode_b64_image(img, "PNG")
    return jsonify(image_b64=out_b64, width=img.width, height=img.height)

@app.get("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
