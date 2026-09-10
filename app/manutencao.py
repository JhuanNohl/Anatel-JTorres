"""Preservacao dos dados: copia de seguranca e atualizacao de esquema sem perder nada.

O sistema evolui (colunas e tabelas novas). Este modulo garante que uma versao nova do
codigo abra um banco antigo sem apagar nada:

    1. compara o banco com o modelo atual;
    2. se houver diferenca, faz uma copia de seguranca do arquivo .db;
    3. cria as tabelas que faltam e ACRESCENTA as colunas que faltam.

Nada e apagado: colunas removidas do modelo continuam no banco, ignoradas.
"""
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text


def caminho_banco(app):
    return Path(app.config["BANCO"])


# ------------------------------------------------------------------ backup

def fazer_backup(app, motivo="manual"):
    """Copia o arquivo do banco para instance/backups. Devolve o caminho ou None."""
    origem = caminho_banco(app)
    if not origem.is_file():
        return None
    pasta = Path(app.config["BACKUP_DIR"])
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = pasta / f"{origem.stem}-{carimbo}-{motivo}.db"
    shutil.copy2(origem, destino)
    _limpar_backups(pasta, app.config.get("MANTER_BACKUPS", 30))
    return destino


def _limpar_backups(pasta, manter):
    copias = sorted(pasta.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for antiga in copias[manter:]:
        try:
            antiga.unlink()
        except OSError:
            pass


def listar_backups(app):
    pasta = Path(app.config["BACKUP_DIR"])
    if not pasta.is_dir():
        return []
    copias = sorted(pasta.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [dict(nome=p.name, tamanho=p.stat().st_size,
                 data=datetime.fromtimestamp(p.stat().st_mtime)) for p in copias]


# --------------------------------------------------------------- migracao

def _literal(valor):
    """Converte um default do modelo para literal SQL."""
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str):
        return "'" + valor.replace("'", "''") + "'"
    return None


def _default_da_coluna(coluna):
    padrao = coluna.default
    if padrao is None or getattr(padrao, "is_callable", False):
        return None
    if getattr(padrao, "is_scalar", False):
        return _literal(padrao.arg)
    return None


def diferencas(app, db):
    """O que existe no modelo e ainda nao existe no banco: (tabelas, colunas)."""
    inspetor = inspect(db.engine)
    existentes = set(inspetor.get_table_names())
    tabelas_novas = []
    colunas_novas = []
    for nome, tabela in db.metadata.tables.items():
        if nome not in existentes:
            tabelas_novas.append(nome)
            continue
        no_banco = {c["name"] for c in inspetor.get_columns(nome)}
        for coluna in tabela.columns:
            if coluna.name not in no_banco:
                colunas_novas.append((nome, coluna))
    return tabelas_novas, colunas_novas


def preparar(app, db):
    """Deixa o banco pronto para esta versao do codigo, preservando os dados.

    Devolve a lista de mudancas aplicadas (vazia quando nada mudou).
    """
    caminho_banco(app).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    banco_existe = caminho_banco(app).is_file()
    tabelas_novas, colunas_novas = diferencas(app, db)

    # banco novo: cria tudo e pronto, nao ha o que preservar
    if not banco_existe:
        db.create_all()
        return []

    if not tabelas_novas and not colunas_novas:
        return []

    # ha mudanca de esquema em um banco com dados: copia de seguranca ANTES de mexer
    copia = fazer_backup(app, "antes-de-atualizar")
    mudancas = []
    if copia:
        mudancas.append(f"cópia de segurança criada em {copia.name}")

    db.create_all()  # cria apenas as tabelas que faltam
    for nome in tabelas_novas:
        mudancas.append(f"tabela criada: {nome}")

    with db.engine.begin() as conexao:
        for tabela, coluna in colunas_novas:
            tipo = coluna.type.compile(dialect=db.engine.dialect)
            sql = f'ALTER TABLE "{tabela}" ADD COLUMN "{coluna.name}" {tipo}'
            padrao = _default_da_coluna(coluna)
            if padrao is not None:
                sql += f" DEFAULT {padrao}"
            conexao.execute(text(sql))
            mudancas.append(f"coluna acrescentada: {tabela}.{coluna.name}")

    return mudancas
