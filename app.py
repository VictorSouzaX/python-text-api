from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
import base64
from io import BytesIO
from pathlib import Path
import os
import re

app = Flask(name)

def parse_int(v, d):
try:
return int(str(v).replace('px', ''))
except Exception:
return d

def decode_img(b64):
b = base64.b64decode(str(b64).split(",")[-1])
return Image.open(BytesIO(b)).convert("RGBA")

def encode_img(img, fmt="PNG"):
buf = BytesIO()
img.save(buf, format=fmt)
return base64.b64encode(buf.getvalue()).decode()

def color_rgba(s, op=100):
try:
rgba = ImageColor.getcolor(s, "RGBA")
except Exception:
rgba = (0, 0, 0, 255)
a = int(rgba[3] * max(0, min(100, int(op))) / 100)
return (rgba[0], rgba[1], rgba[2], a)

def find_font_file(font_name, fonts_dir):
fonts_dir = Path(fonts_dir)
if not fonts_dir.exists():
raise FileNotFoundError(str(fonts_dir.resolve()))
name = (font_name or "").strip()
if name.lower().endswith(".ttf") or name.lower().endswith(".otf") or name.lower().endswith(".ttc"):
direct = fonts_dir / name
if direct.exists():
return str(direct)
else:
direct = fonts_dir / f"{name}.ttf"
if direct.exists():
return str(direct)
wanted = re.sub(r"[-_ .]", "", Path(name).stem).casefold()
candidates = []
for ext in (".ttf", ".otf", "*.ttc"):
candidates += list(fonts_dir.rglob(ext))
for p in candidates:
key = re.sub(r"[-_ .]", "", p.stem).casefold()
if key == wanted:
return str(p)
raise FileNotFoundError(name)

def get_font(fs, font_name="Archivo-Regular", fonts_dir=None):
fonts_dir = fonts_dir or os.getenv("FONTS_DIR", "font_archivo")
try:
path = find_font_file(font_name, fonts_dir)
return ImageFont.truetype(path, int(fs))
except Exception:
return ImageFont.load_default()

@app.route('/process-text', methods=['POST'])
def process_text():
j = request.get_json(silent=True) or {}
b64 = j.get("image_b64") or j.get("image") or ""
if not b64:
return jsonify(error="image_b64 ausente"), 400
try:
img = decode_img(b64)
except Exception as e:
return jsonify(error=f"b64 decode fail: {e}"), 400

t = str(j.get("texto", ""))
x = parse_int(j.get("x", 50), 50)
y = parse_int(j.get("y", 50), 50)
fs = parse_int(j.get("font_size", 40), 40)
color = j.get("color", "#000000")
align = j.get("align", "left")
op = parse_int(j.get("opacity", 100), 100)
font_name = j.get("font", "Archivo-Regular")
fonts_dir = j.get("fonts_dir") or os.getenv("FONTS_DIR", "font_archivo")

draw = ImageDraw.Draw(img)
font = get_font(fs, font_name=font_name, fonts_dir=fonts_dir)
fill = color_rgba(color, op)
draw.multiline_text((x, y), t, font=font, fill=fill, align=align)

out_b64 = encode_img(img, "PNG")
return jsonify(image_b64=out_b64)
if name == 'main':
app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
