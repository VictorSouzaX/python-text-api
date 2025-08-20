from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
import base64
from io import BytesIO

app = Flask(__name__)

def parse_int(v, d):
    try:
        return int(str(v).replace('px',''))
    except:
        return d

def decode_img(b64):
    b = base64.b64decode(b64.split(",")[-1])
    return Image.open(BytesIO(b)).convert("RGBA")

def encode_img(img, fmt="PNG"):
    buf = BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

def color_rgba(s, op=100):
    try: rgba = ImageColor.getcolor(s, "RGBA")
    except: rgba = (0,0,0,255)
    a = int(rgba[3] * op/100)
    return (rgba[0], rgba[1], rgba[2], a)

def get_font(fs):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", fs)
    except:
        return ImageFont.load_default()

@app.route('/process-text', methods=['POST'])
def process_text():
    j = request.get_json(silent=True) or {}
    b64 = j.get("image_b64") or j.get("image") or ""
    if not b64: return jsonify(error="image_b64 ausente"), 400
    try: img = decode_img(b64)
    except Exception as e: return jsonify(error=f"b64 decode fail: {e}"),400
    t = str(j.get("texto", ""))
    x = parse_int(j.get("x",50), 50)
    y = parse_int(j.get("y",50), 50)
    fs = parse_int(j.get("font_size",40), 40)
    color = j.get("color","#000000")
    align = j.get("align","left")
    op = parse_int(j.get("opacity",100),100)
    draw = ImageDraw.Draw(img)
    font = get_font(fs)
    fill = color_rgba(color, op)
    draw.multiline_text((x, y), t, font=font, fill=fill, align=align)
    out_b64 = encode_img(img,"PNG")
    return jsonify(image_b64=out_b64)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
