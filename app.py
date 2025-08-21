from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO
from pathlib import Path
import base64, os, re

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

def load_font(size, font_name, fonts_dir):
    size = int(size)
    root = Path(fonts_dir or os.getenv("FONTS_DIR", "font_archivo"))
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

def wrap_lines(text, font, draw, max_width):
    if not max_width or max_width <= 0:
        return str(text).split("\n")
    result = []
    for raw_line in str(text).splitlines() or [""]:
        words = raw_line.split(" ")
        if not words:
            result.append("")
            continue
        line = ""
        for w in words:
            test = w if line == "" else f"{line} {w}"
            if text_width(draw, test, font) <= max_width:
                line = test
            else:
                if line == "":
                    buff = ""
                    for ch in w:
                        t2 = buff + ch
                        if text_width(draw, t2, font) > max_width:
                            if buff:
                                result.append(buff)
                            buff = ch
                        else:
                            buff = t2
                    line = buff
                else:
                    result.append(line)
                    line = w
        result.append(line)
    return result

def parse_bold_segments(text):
    tokens = re.split(r'(<\/?b>)', str(text), flags=re.IGNORECASE)
    segments = []
    is_bold = False
    for tok in tokens:
        if not tok:
            continue
        if re.fullmatch(r'<b>', tok, flags=re.IGNORECASE):
            is_bold = True
            continue
        if re.fullmatch(r'</b>', tok, flags=re.IGNORECASE):
            is_bold = False
            continue
        segments.append((tok, is_bold))
    return segments

def split_segments_by_newline(segments):
    lines = [[]]
    for txt, bold in segments:
        parts = txt.split("\n")
        for i, part in enumerate(parts):
            if part:
                lines[-1].append((part, bold))
            if i < len(parts) - 1:
                lines.append([])
    return lines

def segments_width(draw, segs, font_regular, font_bold):
    total = 0
    for txt, bold in segs:
        if not txt:
            continue
        font = font_bold if bold else font_regular
        total += draw.textlength(txt, font=font)
    return int(total)

def wrap_segments_line(segs, draw, font_regular, font_bold, max_width):
    if not max_width or max_width <= 0:
        return [segs]
    lines = []
    cur = []
    curw = 0
    for txt, bold in segs:
        font = font_bold if bold else font_regular
        parts = re.split(r'(\s+)', txt)
        for part in parts:
            if part is None or part == "":
                continue
            w = draw.textlength(part, font=font)
            if part.isspace():
                if cur and curw + w <= max_width:
                    cur.append((part, bold))
                    curw += w
                continue
            if curw + w <= max_width:
                cur.append((part, bold))
                curw += w
            else:
                if cur:
                    lines.append(cur)
                    cur = []
                    curw = 0
                buff = ""
                for ch in part:
                    if draw.textlength(buff + ch, font=font) <= max_width:
                        buff += ch
                    else:
                        if buff:
                            cur.append((buff, bold))
                            lines.append(cur)
                            cur = []
                            buff = ch
                        else:
                            cur.append((ch, bold))
                            lines.append(cur)
                            cur = []
                            buff = ""
                if buff:
                    cur.append((buff, bold))
                    curw = draw.textlength(buff, font=font)
    if cur:
        lines.append(cur)
    return lines

def layout_rich_lines(text, draw, font_regular, font_bold, max_width):
    segs = parse_bold_segments(text)
    logical_lines = split_segments_by_newline(segs)
    out = []
    for seg_line in logical_lines:
        wrapped = wrap_segments_line(seg_line, draw, font_regular, font_bold, max_width)
        out.extend(wrapped)
    return out

def draw_rich_line(draw, x, y, line_segs, font_regular, font_bold, fill):
    cx = x
    for tok, bold in line_segs:
        if not tok:
            continue
        font = font_bold if bold else font_regular
        draw.text((cx, y), tok, font=font, fill=fill)
        cx += draw.textlength(tok, font=font)

@app.post("/process-text")
def process_text():
    j = request.get_json(silent=True) or {}
    img_b64 = j.get("image_b64") or j.get("image")
    if not img_b64:
        return jsonify(error="image_b64 ausente"_
