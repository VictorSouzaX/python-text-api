from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
import base64
from io import BytesIO
import textwrap

app = Flask(__name__)

def parse_int(v, d):
    try:
        return int(str(v).replace('px','').strip())
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
    # Converte string/cor do n8n + opacidade para RGBA
    try:
        rgba = ImageColor.getcolor(s, "RGBA")
    except:
        rgba = (0, 0, 0, 255)
    a = int(rgba[3] * op/100)
    return (rgba[0], rgba[1], rgba[2], a)

def get_font(fs, font_name):
    caminho = f"Fonts/{font_name}.ttf"
    print("Tentando abrir fonte:", caminho, "tam:", fs)
    try:
        return ImageFont.truetype(caminho, fs)
    except Exception as e:
        print("Erro abrindo fonte:", caminho, "->", e)
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
        return jsonify(error=f"b64 decode fail: {e}"),400

    texto = str(j.get("texto", ""))
    x = parse_int(j.get("x",50), 50)
    y = parse_int(j.get("y",50), 50)
    fs = parse_int(j.get("font_size",40), 40)
    font_name = j.get("font", "Archivo-Regular")
    font = get_font(fs, font_name)
    color = j.get("color","#000000")
    align = j.get("align","left")
    max_chars = parse_int(j.get("max_chars", 0), 0)
    max_width = parse_int(j.get("max_width", 0), 0)
    line_height = parse_int(j.get("line_height", fs+5), fs+5)
    opacity = parse_int(j.get("opacity", 100),100)

    # Ajuste de texto (max_chars e max_width)
    if max_chars and max_chars > 0:
        texto = "\n".join(textwrap.wrap(texto, width=max_chars))
    elif max_width and max_width > 0:
        lines, cur = [], ""
        for word in texto.split():
            test = cur + (" " if cur else "") + word
            w, _ = font.getsize(test)
            if w > max_width and cur:
                lines.append(cur)
                cur = word
            else:
                cur = test
        if cur:
            lines.append(cur)
        texto = "\n".join(lines)

    draw = ImageDraw.Draw(img)
    fill = color_rgba(color, opacity)

    # Linha por linha, se precisar controlar line_height
    if "\n" in texto and line_height > fs:
        y0 = y
        for line in texto.split("\n"):
            draw.text((x, y0), line, font=font, fill=fill, align=align)
            y0 += line_height
    else:
        draw.multiline_text((x, y), texto, font=font, fill=fill, align=align, spacing=(line_height - fs))

    out_b64 = encode_img(img,"PNG")
    return jsonify(image_b64=out_b64)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)
