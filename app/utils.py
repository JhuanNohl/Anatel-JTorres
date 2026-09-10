"""Funcoes utilitarias: upload de arquivos, formatacao e datas em portugues."""
import os
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

MESES = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def slugify(texto, tamanho=60):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:tamanho] or "arquivo"


def pasta_upload(*sub):
    """Retorna (e cria) uma pasta dentro de instance/arquivos."""
    caminho = Path(current_app.config["UPLOAD_DIR"]).joinpath(*sub)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def pasta_processo(processo, *sub):
    """Retorna (e cria) a pasta fisica do processo dentro de instance/arquivos."""
    return pasta_upload("processos", slugify(processo.numero), *sub)


def caminho_absoluto(relativo):
    return Path(current_app.config["UPLOAD_DIR"]) / relativo


def salvar_arquivo(file_storage, destino_pasta, prefixo=""):
    """Salva o upload evitando sobrescrita. Devolve (caminho_relativo, tamanho)."""
    nome_original = file_storage.filename or "arquivo"
    ext = Path(nome_original).suffix.lower()
    base = slugify(Path(nome_original).stem)
    nome = secure_filename(f"{prefixo + '-' if prefixo else ''}{base}{ext}")
    destino = Path(destino_pasta) / nome
    i = 2
    while destino.exists():
        destino = Path(destino_pasta) / secure_filename(
            f"{prefixo + '-' if prefixo else ''}{base}-{i}{ext}")
        i += 1
    file_storage.save(destino)
    raiz = Path(current_app.config["UPLOAD_DIR"])
    return destino.relative_to(raiz).as_posix(), destino.stat().st_size


def remover_arquivo(relativo):
    if not relativo:
        return
    try:
        alvo = caminho_absoluto(relativo)
        if alvo.is_file():
            alvo.unlink()
    except OSError:
        pass


def dimensoes_imagem(relativo):
    try:
        from PIL import Image
        with Image.open(caminho_absoluto(relativo)) as img:
            return img.size
    except Exception:
        return (None, None)


# ------------------------------------------------------------------ formato

def data_extenso(d=None):
    d = d or date.today()
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def data_br(d):
    if not d:
        return "-"
    return d.strftime("%d/%m/%Y")


def data_hora_br(d):
    if not d:
        return "-"
    return d.strftime("%d/%m/%Y %H:%M")


def moeda(valor):
    if valor in (None, ""):
        return "-"
    return "R$ " + f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tamanho_humano(bytes_):
    if not bytes_:
        return "-"
    for unidade in ["B", "KB", "MB", "GB"]:
        if bytes_ < 1024:
            return f"{bytes_:.0f} {unidade}" if unidade == "B" else f"{bytes_:.1f} {unidade}"
        bytes_ /= 1024
    return f"{bytes_:.1f} TB"


def parse_data(valor):
    if not valor:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_float(valor):
    if valor in (None, ""):
        return None
    txt = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def parse_bool(valor):
    return str(valor).lower() in {"1", "true", "on", "sim", "yes"}


def is_imagem(nome):
    return Path(nome or "").suffix.lower() in EXT_IMAGEM


def proximo_numero_processo(db, ano=None):
    """Gera numero sequencial no formato ANATEL-2026-001."""
    from .models import Processo
    ano = ano or date.today().year
    prefixo = f"ANATEL-{ano}-"
    ultimo = (db.session.query(Processo.numero)
              .filter(Processo.numero.like(f"{prefixo}%"))
              .order_by(Processo.numero.desc()).first())
    seq = 1
    if ultimo:
        try:
            seq = int(str(ultimo[0]).split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefixo}{seq:03d}"
