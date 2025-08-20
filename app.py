from flask import Flask, request, jsonify
from PIL import Image
import io

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "API rodando!"})

@app.route('/process-text', methods=['POST'])
def process_text():
    data = request.json
    text = data.get('text', '')
    # Aqui você pode adicionar processamento de texto que quiser
    processed = text.upper()  # exemplo simples
    return jsonify({"original": text, "processed": processed})

@app.route('/process-image', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        return jsonify({"error": "Nenhuma imagem enviada"}), 400
    
    file = request.files['image']
    img = Image.open(file.stream)
    
    # exemplo: converter para RGB
    img = img.convert('RGB')
    
    # salvar em memória
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    
    return jsonify({"message": "Imagem processada com sucesso!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
