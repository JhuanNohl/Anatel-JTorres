FROM python:3.12-slim

# Locale/encoding explicitos: a imagem slim ja vem em UTF-8 por padrao,
# mas fixamos aqui para nao depender do locale do host que rodar o build.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY run.py .

# usuario sem privilegios — a aplicacao so precisa escrever em instance/ (volume)
RUN useradd --create-home --uid 1000 anatel \
    && mkdir -p /app/instance \
    && chown -R anatel:anatel /app
USER anatel

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", \
     "--timeout", "120", "run:app"]
