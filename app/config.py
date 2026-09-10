import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"

# As variaveis de ambiente permitem apontar para outro banco/pasta (testes, copia de
# homologacao) sem nunca tocar nos dados de producao em instance/.
BANCO = Path(os.environ.get("ANATEL_DB") or (INSTANCE_DIR / "anatel.db"))
UPLOAD_DIR = Path(os.environ.get("ANATEL_ARQUIVOS") or (INSTANCE_DIR / "arquivos"))
BACKUP_DIR = Path(os.environ.get("ANATEL_BACKUPS") or (BANCO.parent / "backups"))


class Config:
    SECRET_KEY = os.environ.get("ANATEL_SECRET_KEY", "zkteco-anatel-dev-key")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BANCO.as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 128 MB por requisicao (fotos em alta resolucao + PDFs de manual)
    MAX_CONTENT_LENGTH = 128 * 1024 * 1024
    BANCO = BANCO
    UPLOAD_DIR = UPLOAD_DIR
    BACKUP_DIR = BACKUP_DIR
    BASE_DIR = BASE_DIR
    JSON_AS_ASCII = False
    TEMPLATES_AUTO_RELOAD = True
    # quantas copias de seguranca do banco manter
    MANTER_BACKUPS = 30
