from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO
from pathlib import Path
import base64, os, traceback

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

def draw_rectangle(layer, rect):
    x = to_px(rect.get("x"), 0)
    y = to_px(rect.get("y"), 0)
    w = to_px(rect.get("width"), 0)
    h = to_px(rect.get("height"), 0)
    r = to_px(rect.get("border_radius"), 0)

    fill_color = rect.get("color", "#000000")
    fill_opacity = to_px(rect.get("opacity"), 100)
    fill = color_to_rgba(fill_color, fill_opacity)

    stroke_color = rect.get("stroke_color", "#000000")
    stroke_opacity = to_px(rect.get("stroke_opacity"), 100)
    stroke_fill = color_to_rgba(stroke_color, stroke_opacity)

    sw_top = to_px(rect.get("stroke_width_top"), 0)
    sw_bottom = to_px(rect.get("stroke_width_bottom"), 0)
    sw_left = to_px(rect.get("stroke_width_left"), 0)
    sw_right = to_px(rect.get("stroke_width_right"), 0)

    draw = ImageDraw.Draw(layer)

    if r > 0:
        draw.rounded_rectangle([x, y, x+w, y+h], radius=r, fill=fill)
    else:
        draw.rectangle([x, y, x+w, y+h], fill=fill)

    if sw_top > 0:
        draw.line([(x, y), (x+w, y)], fill=stroke_fill, width=sw_top)
    if sw_bottom > 0:
        draw.line([(x, y+h), (x+w, y+h)], fill=stroke_fill, width=sw_bottom)
    if sw_left > 0:
        draw.line([(x, y), (x, y+h)], fill=stroke_fill, width=sw_left)
    if sw_right > 0:
        draw.line([(x+w, y), (x+w, y+h)], fill=stroke_fill, width=sw_right)

def list_assets_dir(base_path):
    files = []
    if base_path.exists() and base_path.is_dir():
        for f in sorted(base_path.iterdir()):
            if f.is_file():
                files.append(f.name)
    return files

def find_asset_file(base_path: Path, requested: str):
    """
    Busca arquivo em base_path tentando:
    - match exato (ignorando case)
    - adicionar extensões comuns
    - substring match (ex: 'verde' encontra 'CREDITO_VERDE.png')
    Retorna Path ou None
    """
    if not base_path.exists() or not base_path.is_dir():
        return None

    # mapa: lowercase name -> Path
    files_map = {f.name.lower(): f for f in base_path.iterdir() if f.is_file()}

    req = str(requested or "").strip()
    if not req:
        return None
    req_l = req.lower()

    # 1) exato
    if req_l in files_map:
        return files_map[req_l]

    # 2) tenta com extensões
    exts = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"]
    for ext in exts:
        if not req_l.endswith(ext):
            cand = req_l + ext
            if cand in files_map:
                return files_map[cand]

    # 3) substring (procura qualquer arquivo que contenha req_l)
    for name, path in files_map.items():
        if req_l in name:
            return path

    # 4) tenta padrão comum CREDITO_<REQ>.png
    cand_name = f"CREDITO_{req.upper()}.png".lower()
    if cand_name in files_map:
        return files_map[cand_name]

    return None

def draw_assets(img, imagens):
    base_path = Path(__file__).resolve().parent / "assets"
    attempted = []
    resolved = []
    missing = []
    available_files = list_assets_dir(base_path)

    for item in imagens:
        try:
            # determina qual nome procurar
            resolved_path = None
            candidate_text = None

            # 1) se passou 'file' direto
            if item.get("file"):
                candidate_text = Path(item.get("file")).name
                resolved_path = find_asset_file(base_path, candidate_text)

            # 2) se passou tipoCredito (mapeia para CREDITO_VERDE etc)
            if not resolved_path and item.get("tipoCredito"):
                candidato = f"credito_{item.get('tipoCredito')}".lower()
                candidate_text = candidato
                resolved_path = find_asset_file(base_path, candidate_text)

            # 3) fallback: tenta o valor bruto (por exemplo 'verde')
            if not resolved_path and item.get("tipoCredito"):
                candidate_text = item.get("tipoCredito")
                resolved_path = find_asset_file(base_path, candidate_text)

            attempted.append(candidate_text or "(nenhum candidato)")

            if not resolved_path:
                missing.append(candidate_text or "(nenhum candidato)")
                continue

            # coloca a imagem
            overlay = Image.open(resolved_path).convert("RGBA")
            x = to_px(item.get("x"), 0)
            y = to_px(item.get("y"), 0)
            anchor = str(item.get("anchor", "topleft")).lower()

            # ajusta por anchor
            if anchor in ("center", "middle"):
                x = int(round(x - overlay.width / 2))
                y = int(round(y - overlay.height / 2))
            elif anchor == "topright":
                x = int(round(x - overlay.width))
            elif anchor == "bottomleft":
                y = int(round(y - overlay.height))
            elif anchor == "bottomright":
                x = int(round(x - overlay.width))
                y = int(round(y - overlay.height))

            layer = Image.new("RGBA", img.size, (0,0,0,0))
            layer.paste(overlay, (x, y), overlay)
            img = Image.alpha_composite(img, layer)
            resolved.append(str(resolved_path))
        except Exception as e:
            missing.append(str(item.get("file") or item.get("tipoCredito") or "(erro)"))
            # não interromper o loop
            print("Erro ao inserir asset:", e)
            traceback.print_exc()

    debug = {
        "assets_base_path": str(base_path),
        "assets_base_exists": base_path.exists(),
        "assets_list": available_files,
        "attempted_candidates": attempted,
        "resolved_paths": resolved,
        "missing": missing
    }
    return img, debug

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

    # --- Retângulos ---
    retangulos = j.get("retangulos", [])
    if not isinstance(retangulos, list):
        return jsonify(error="Campo 'retangulos' deve ser uma lista"), 400

    try:
        for r in retangulos:
            layer = Image.new("RGBA", img.size, (0,0,0,0))
            draw_rectangle(layer, r)
            img = Image.alpha_composite(img, layer)
    except Exception as e:
        return jsonify(error=f"Falha ao desenhar retângulo: {e}"), 500

    # --- Textos ---
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

    # --- Imagens (assets) ---
    imagens = j.get("imagens", [])
    assets_debug = {}
    if isinstance(imagens, list) and imagens:
        try:
            img, debug = draw_assets(img, imagens)
            assets_debug = debug
        except Exception as e:
            assets_debug = {"error": str(e)}

    try:
        out_b64 = encode_b64_image(img, "PNG")
        resp = {"image_b64": out_b64, "width": img.width, "height": img.height, "assets": assets_debug}
        return jsonify(resp)
    except Exception as e:
        return jsonify(error=f"Falha ao codificar imagem: {e}"), 500

@app.get("/list-assets")
def list_assets():
    base_path = Path(__file__).resolve().parent / "assets"
    return jsonify({
        "assets_base_path": str(base_path),
        "assets_base_exists": base_path.exists(),
        "assets_list": list_assets_dir(base_path)
    })

@app.get("/health")
def health():
    return "ok", 200

@app.get("/test")
def test():
    base_path = Path(__file__).resolve().parent / "assets"
    return jsonify({
        "status": "ok",
        "message": "API funcionando",
        "assets_base_path": str(base_path),
        "assets_base_exists": base_path.exists(),
        "assets_list_sample": list_assets_dir(base_path)[:50]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
