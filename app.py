from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO
from pathlib import Path
import base64, os, re

app = Flask(name)
def px(value, default):
if value is None:
return default
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
op = max(0, min(100, int(px(opacity, 100))))
a = int(rgba[3] * (op / 100.0))
return (rgba[0], rgba[1], rgba[2], a)

DEFAULT_FONTS_DIR = Path(os.getenv("FONTS_DIR", "font_archivo"))

def find_font_path(name, fonts_dir=None):
if not name:
raise FileNotFoundError("font: vazio")
root = Path(fonts_dir or DEFAULT_FONTS_DIR)
if not root.exists():
raise FileNotFoundError(f"fonts_dir não encontrado: {root.resolve()}")

p = root / name
if p.exists():
    return str(p)

for ext in (".ttf", ".otf", ".ttc"):
    q = root / (name if name.lower().endswith(ext) else f"{name}{ext}")
    if q.exists():
        return str(q)

wanted = re.sub(r"[-_ .]", "", Path(name).stem).casefold()
for ext in ("*.ttf", "*.otf", "*.ttc"):
    for f in root.rglob(ext):
        key = re.sub(r"[-_ .]", "", f.stem).casefold()
        if key == wanted:
            return str(f)

raise FileNotFoundError(f"Fonte não encontrada: {name}")
def load_font(size, name="Archivo-Regular", fonts_dir=None):
try:
path = find_font_path(name, fonts_dir)
return ImageFont.truetype(path, int(size))
except Exception:
return ImageFont.load_default()

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
w_px = draw.textbbox((0, 0), test, font=font)[2]
if w_px <= max_width:
line = test
else:
if line == "":
buff = ""
for ch in w:
t2 = buff + ch
if draw.textbbox((0, 0), t2, font=font)[2] > max_width:
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

@app.get("/health")
def health():
return "ok", 200

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
x = px(j.get("x"), 0)
y = px(j.get("y"), 0)
fs = px(j.get("font_size"), 40)
line_height = px(j.get("line_height"), 0)
if line_height <= 0:
    line_height = int(fs * 1.2)

max_width = px(j.get("max_width"), 0)
max_chars = px(j.get("max_chars"), 0)
if max_chars and len(text) > max_chars:
    text = text[:max_chars].rstrip()

align = str(j.get("align", "left")).lower()
if align not in ("left", "center", "right"):
    align = "left"

color = j.get("color", "#000000")
opacity = px(j.get("opacity"), 100)
font_name = j.get("font", "Archivo-Regular")
fonts_dir = j.get("fonts_dir") or os.getenv("FONTS_DIR", "font_archivo")

draw = ImageDraw.Draw(img)
font = load_font(fs, font_name, fonts_dir)
fill = color_to_rgba(color, opacity)

lines = wrap_lines(text, font, draw, max_width)

for line in lines:
    if align == "left" or not max_width:
        x_line = x
    else:
        w_line = draw.textbbox((0, 0), line, font=font)[2]
        if align == "center":
            x_line = x + (max_width - w_line) // 2
        else:
            x_line = x + (max_width - w_line)
    draw.text((x_line, y), line, font=font, fill=fill)
    y += line_height

out_b64 = encode_b64_image(img, "PNG")
return jsonify(image_b64=out_b64, width=img.width, height=img.height)
if name == "main":
app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
