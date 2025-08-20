from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import base64, io, os, re

def resolve_font(font_name, fonts_dir=None):
# Use variável de ambiente FONTS_DIR ou pasta local "Fonts"
fonts_dir = Path(fonts_dir or os.getenv('FONTS_DIR', 'Fonts'))
if not fonts_dir.exists():
raise FileNotFoundError(f'Pasta de fontes não encontrada: {fonts_dir.resolve()}')

wanted = re.sub(r'[-_ \.]', '', (font_name or '').strip()).casefold()

candidates = []
for ext in ('*.ttf', '*.otf', '*.ttc'):
    candidates += list(fonts_dir.rglob(ext))

for p in candidates:
    key = re.sub(r'[-_ \.]', '', p.stem).casefold()
    if key == wanted:
        return str(p)

raise FileNotFoundError(
    f'Fonte "{font_name}" não encontrada em {fonts_dir.resolve()}. '
    f'Arquivos disponíveis: {[p.name for p in candidates][:10]}...'
)
def parse_color(hex_color, opacity_pct=100):
c = (hex_color or '#000').lstrip('#')
if len(c) == 3:
r, g, b = [int(ch*2, 16) for ch in c]
else:
r = int(c[0:2], 16)
g = int(c[2:4], 16)
b = int(c[4:6], 16)
a = max(0, min(100, int(opacity_pct)))
a = round(a * 255 / 100)
return (r, g, b, a)

def wrap_text(text, font, max_width, draw):
lines = []
for paragraph in (text or '').splitlines():
if not paragraph:
lines.append('')
continue
words = paragraph.split(' ')
line = ''
for w in words:
test = (line + ' ' + w).strip()
# textlength mede com a fonte atual
if draw.textlength(test, font=font) <= max_width or not line:
line = test
else:
lines.append(line)
line = w
if line:
lines.append(line)
return lines

def render_text_on_image(
image_b64,
texto,
x=0, y=0,
font='Archivo-BlackItalic',
font_size=48,
color='#000000',
align='left',
max_chars=None,
line_height=None,
max_width=None,
opacity=100,
fonts_dir=None
):
# Decodifica a imagem
raw = base64.b64decode(image_b64.split(',')[-1])
im = Image.open(io.BytesIO(raw)).convert('RGBA')

# Fonte
font_path = resolve_font(font, fonts_dir)
fnt = ImageFont.truetype(font_path, int(font_size))

# Área e medição
if max_width is None:
    max_width = im.width - int(x)
overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)

# Texto e quebra
if max_chars:
    texto = (texto or '')[:int(max_chars)]
if line_height is None:
    line_height = int(fnt.size * 1.2)

lines = wrap_text(texto or '', fnt, int(max_width), draw)

# Cor/alpha
fill = parse_color(color, opacity)

# Desenha respeitando alinhamento
cur_y = int(y)
for line in lines:
    line_width = draw.textlength(line, font=fnt)
    if align == 'center':
        cur_x = int(x) + int((int(max_width) - line_width) / 2)
    elif align == 'right':
        cur_x = int(x) + int(int(max_width) - line_width)
    else:
        cur_x = int(x)
    draw.text((cur_x, cur_y), line, font=fnt, fill=fill)
    cur_y += int(line_height)

out = Image.alpha_composite(im, overlay).convert('RGB')
buf = io.BytesIO()
out.save(buf, format='JPEG', quality=95)
return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
