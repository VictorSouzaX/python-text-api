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

def draw_text_simple(draw, text, x, y, font, fill, align="left", max_width=0, align_vertical="top"):
    """
    Desenha um bloco de texto usando uma 'caixa invisível' definida por:
      - referência x,y (interpreted conforme align/align_vertical)
      - largura da caixa: max_width (quando > 0)
    Regras:
      - x é o ponto de referência da caixa:
          align="left"   -> x = left edge da caixa
          align="center" -> x = center da caixa
          align="right"  -> x = right edge da caixa
      - max_width serve apenas para quebra de linha; o cálculo da posição usa a interpretação de x acima.
      - align_vertical similar: y é top/center/bottom da caixa.
    """
    if not text:
        return y

    # Quebra de linhas respeitando max_width (em px)
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
                    current_line = word
            if current_line:
                all_lines.append(current_line)
        else:
            all_lines.append(line)

    # Métricas de linha
    try:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
    except Exception:
        # fallback razoável
        line_height = int(font.size * 1.2)

    total_height = len(all_lines) * line_height

    # Calcula top da caixa invisível (onde começa o primeiro line_y)
    if align_vertical == "top":
        box_top = int(y)
    elif align_vertical == "center":
        box_top = int(y - total_height / 2)
    elif align_vertical == "bottom":
        box_top = int(y - total_height)
    else:
        box_top = int(y)

    # Se houver max_width, calcula left da caixa invisível a partir de x e align
    if max_width and max_width > 0:
        if align == "left":
            box_left = int(x)
        elif align == "center":
            box_left = int(x - max_width / 2)
        elif align == "right":
            box_left = int(x - max_width)
        else:
            box_left = int(x)
    else:
        box_left = None  # não existe caixa fixa

    # Desenha cada linha: calcula texto_x com base na caixa (quando existir) ou com base em x
    current_y = box_top
    for line in all_lines:
        if line.strip() == "":
            current_y += line_height
            continue

        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        if box_left is not None:
            # Temos uma caixa com largura max_width
            if align == "left":
                text_x = box_left
            elif align == "center":
                # centraliza dentro da caixa
                text_x = box_left + int((max_width - text_width) / 2)
            elif align == "right":
                text_x = box_left + int(max_width - text_width)
            else:
                text_x = box_left
        else:
            # Sem caixa, interpreta x como referência direta:
            if align == "left":
                text_x = int(x)
            elif align == "center":
                text_x = int(x - text_width / 2)
            elif align == "right":
                text_x = int(x - text_width)
            else:
                text_x = int(x)

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
        return jsonify(error="Campo 'textos' deve ser uma lista (array de objetos)"), 400

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

            # 1. Cria camada RGBA transparente para o texto
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            font = load_font(fs, font_name, "font_archivo")
            fill = color_to_rgba(color, opacity)

            # 2. Desenha texto na layer respeitando caixa invisível
            draw_text_simple(draw, text, x, y, font, fill, align, max_width, align_vertical)

            # 3. Compoe na imagem original
            img = Image.alpha_composite(img, layer)
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
