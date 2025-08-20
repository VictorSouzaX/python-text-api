# imagem base com Python 3.11
FROM python:3.11-slim

# definir diretório de trabalho
WORKDIR /app

# copiar arquivos para o container
COPY requirements.txt requirements.txt
COPY app.py app.py

# instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# expor a porta
EXPOSE 8080

# comando para rodar a aplicação
CMD ["python", "app.py"]
