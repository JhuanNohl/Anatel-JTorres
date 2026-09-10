"""Integracao com a base publica de produtos certificados da ANATEL.

A ANATEL publica um ZIP com TODOS os produtos certificados do pais (perto de
200 mil linhas). Este modulo baixa esse arquivo, filtra apenas o solicitante da
empresa e devolve os registros normalizados. Quem grava no banco e sincronizar().

Usa somente biblioteca padrao - o download nao depende de pacote extra.

A leitura de colunas e a parte chata: a base da ANATEL traz varias colunas em
pares codigo/descricao ("Codigo Situacao do Certificado" e "Situacao do
Certificado") e os nomes mudam de tempo em tempo. Por isso as colunas sao
localizadas por aproximacao, com match exato antes do parcial.
"""
import csv
import io
import os
import re
import unicodedata
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

URL_ZIP = ("https://www.anatel.gov.br/dadosabertos/paineis_de_dados/"
           "certificacao_de_produtos/produtos_certificados.zip")
SOLICITANTE_PADRAO = "ZKTECO DO BRASIL S.A."
SEGUNDOS_DE_ESPERA = 180

# Descricoes das situacoes, para quando a base vier so com o codigo.
SITUACAO_CERTIFICADO = {
    "1": "Em análise", "2": "Homologado", "3": "Indeferido", "4": "Cancelado",
    "5": "Vencido", "6": "Suspenso", "7": "Revogado", "8": "Expirado",
}
# A coluna "Categoria do Produto" vem como codigo (1, 2, 3).
CATEGORIA_PRODUTO = {"1": "Categoria I", "2": "Categoria II", "3": "Categoria III"}
PALAVRAS_DE_CODIGO = ("codigo", "cod", "id")


# ------------------------------------------------------------------ utilidades

def sem_acento(texto):
    valor = "" if texto is None else str(texto)
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    return " ".join(valor.lower().replace("_", " ").split())


def so_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def e_codigo(texto):
    valor = str(texto or "").strip()
    return bool(valor) and valor.isdigit() and len(valor) <= 4


def formatar_homologacao(valor):
    """Os 12 digitos da base viram 01034-22-12720, como a ANATEL publica."""
    digitos = so_digitos(valor)
    if len(digitos) == 12:
        return f"{digitos[:5]}-{digitos[5:7]}-{digitos[7:]}"
    return str(valor or "").strip()


def para_data(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    texto = texto.split(".")[0]                     # 2025-12-17 00:00:00.000000
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S",
                    "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def pasta_cache(base_dir=None):
    caminho = os.environ.get("ANATEL_CACHE")
    if caminho:
        return Path(caminho)
    raiz = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    return raiz / "instance" / "anatel-cache"


# ------------------------------------------------------------------ leitura do ZIP

def baixar_zip(destino, forcar=True, url=None):
    """Baixa o ZIP da ANATEL. Sem forcar, reaproveita o arquivo ja baixado."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not forcar and destino.exists():
        return destino
    pedido = urllib.request.Request(
        url or URL_ZIP,
        headers={"User-Agent": "Mozilla/5.0 (certificacao-anatel-zkteco/1.0)"})
    with urllib.request.urlopen(pedido, timeout=SEGUNDOS_DE_ESPERA) as resposta:
        dados = resposta.read()
    if not zipfile.is_zipfile(io.BytesIO(dados)):
        raise RuntimeError("O endereço da ANATEL não devolveu um arquivo ZIP válido.")
    parcial = destino.with_suffix(".parcial")
    parcial.write_bytes(dados)
    parcial.replace(destino)
    return destino


def _decodificar(bruto):
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return bruto.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", errors="replace")


def ler_csv(bruto):
    texto = _decodificar(bruto)
    try:
        dialeto = csv.Sniffer().sniff(texto[:8192], delimiters=";,\t|")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";"
    linhas = []
    for linha in csv.DictReader(io.StringIO(texto), dialect=dialeto):
        linhas.append({(k or "").strip(): (v or "").strip() for k, v in linha.items()})
    return linhas


def maior_csv_do_zip(caminho_zip):
    with zipfile.ZipFile(caminho_zip) as z:
        candidatos = [(n, z.read(n), z.getinfo(n).file_size) for n in z.namelist()
                      if n.lower().endswith((".csv", ".txt"))]
    if not candidatos:
        raise RuntimeError("Não encontrei CSV dentro do ZIP da ANATEL.")
    candidatos.sort(key=lambda item: item[2], reverse=True)
    return candidatos[0][0], candidatos[0][1]


# ------------------------------------------------------------------ colunas

def achar_coluna(colunas, procurados, excluir=()):
    normalizadas = [(c, sem_acento(c)) for c in colunas]
    fora = [sem_acento(e) for e in excluir]

    def permitida(norm):
        return not any(f and f in norm for f in fora)

    for procurado in procurados:                     # 1o: nome exato
        alvo = sem_acento(procurado)
        for original, norm in normalizadas:
            if permitida(norm) and alvo == norm:
                return original
    for procurado in procurados:                     # 2o: nome parecido
        alvo = sem_acento(procurado)
        for original, norm in normalizadas:
            if permitida(norm) and alvo in norm:
                return original
    return None


def resolver_colunas(colunas):
    colunas = list(colunas)
    sem_cod = dict(excluir=PALAVRAS_DE_CODIGO)
    return {
        "modelo": achar_coluna(colunas, ["modelo"], **sem_cod),
        "marca": achar_coluna(colunas, ["marca", "nome comercial"], **sem_cod),
        "fabricante": achar_coluna(colunas, ["nome do fabricante", "fabricante"], **sem_cod),
        # categoria = Categoria I/II/III; tipo = o ensaio ("Sistemas de
        # Identificacao por Radiofrequencias", "Transceptor de Radiacao
        # Restrita"...). Sao colunas diferentes e sempre foram: antes as duas
        # caiam na mesma chave e o ensaio nunca chegava ao banco.
        "categoria_produto": achar_coluna(colunas, ["categoria do produto",
                                                    "categoria produto"], **sem_cod),
        "tipo_produto": achar_coluna(colunas, ["tipo do produto", "tipo de produto",
                                               "tipo produto"], **sem_cod),
        "homologacao": achar_coluna(colunas, ["numero de homologacao", "n homologacao",
                                              "homologacao"], excluir=["data"]),
        "certificado": achar_coluna(colunas, ["numero do certificado",
                                              "certificado de conformidade", "certificado"],
                                    excluir=["situacao", "validade", "data"]),
        "situacao_certificado": achar_coluna(
            colunas, ["situacao do certificado", "situacao certificado"], **sem_cod),
        "situacao_certificado_codigo": achar_coluna(
            colunas, ["codigo situacao do certificado", "cod situacao certificado"]),
        "situacao_requerimento": achar_coluna(
            colunas, ["situacao do requerimento", "situacao requerimento"], **sem_cod),
        "validade": achar_coluna(colunas, ["data de validade do certificado",
                                           "validade do certificado", "validade"],
                                 excluir=["codigo", "situacao"]),
        "data_homologacao": achar_coluna(colunas, ["data da homologacao", "data de homologacao"],
                                         excluir=["numero"]),
        "solicitante": achar_coluna(colunas, ["nome do solicitante", "solicitante",
                                              "requerente"], **sem_cod),
        "cnpj": achar_coluna(colunas, ["cnpj do solicitante", "cnpj solicitante", "cnpj"],
                             **sem_cod),
    }


def _valor(linha, mapa, chave):
    coluna = mapa.get(chave)
    return (linha.get(coluna, "") or "").strip() if coluna else ""


def _texto_ou_codigo(linha, mapa, chave, descricoes):
    """Devolve a descricao. Se a coluna trouxer o codigo, traduz pelo mapa."""
    valor = _valor(linha, mapa, chave)
    if valor and not e_codigo(valor):
        return valor
    codigo = so_digitos(valor) or so_digitos(_valor(linha, mapa, chave + "_codigo"))
    if not codigo:
        return ""
    return descricoes.get(codigo, f"Código {codigo}")


# ------------------------------------------------------------------ registros

def registros(caminho_zip, solicitante=SOLICITANTE_PADRAO):
    """Le o ZIP e devolve (lista de registros do solicitante, resumo da leitura)."""
    nome_csv, bruto = maior_csv_do_zip(caminho_zip)
    linhas = ler_csv(bruto)
    colunas = list(linhas[0].keys()) if linhas else []
    mapa = resolver_colunas(colunas)
    if not mapa.get("solicitante"):
        raise RuntimeError("Não encontrei a coluna de solicitante no CSV da ANATEL.")

    alvo = sem_acento(solicitante)
    achados = []
    for linha in linhas:
        if sem_acento(_valor(linha, mapa, "solicitante")) != alvo:
            continue
        numero = formatar_homologacao(_valor(linha, mapa, "homologacao"))
        achados.append(dict(
            numero=numero,
            digitos=so_digitos(numero),
            modelo=_valor(linha, mapa, "modelo"),
            certificado=_valor(linha, mapa, "certificado"),
            validade=para_data(_valor(linha, mapa, "validade")),
            data_homologacao=para_data(_valor(linha, mapa, "data_homologacao")),
            situacao_certificado=_texto_ou_codigo(linha, mapa, "situacao_certificado",
                                                  SITUACAO_CERTIFICADO),
            situacao_requerimento=_valor(linha, mapa, "situacao_requerimento"),
            categoria=_texto_ou_codigo(linha, mapa, "categoria_produto",
                                       CATEGORIA_PRODUTO),
            tipo_produto=_valor(linha, mapa, "tipo_produto"),
            marca=_valor(linha, mapa, "marca"),
            fabricante=_valor(linha, mapa, "fabricante"),
            solicitante=_valor(linha, mapa, "solicitante"),
            cnpj=so_digitos(_valor(linha, mapa, "cnpj")),
        ))
    resumo = dict(arquivo=nome_csv, linhas_no_arquivo=len(linhas),
                  linhas_do_solicitante=len(achados), solicitante=solicitante,
                  colunas_encontradas={k: v for k, v in mapa.items() if v})
    return achados, resumo


# ------------------------------------------------------------------ sincronizacao

# Campos que a ANATEL manda. O resto da ficha (natureza, tipo, aplicacoes,
# observacoes, OCD) e curadoria sua e a sincronizacao nunca sobrescreve.
CAMPOS_DA_ANATEL = ("certificado", "validade", "data_homologacao", "situacao",
                    "situacao_certificado", "tipo_produto_anatel", "ensaios_anatel",
                    "marca", "fabricante_nome", "solicitante", "cnpj")


def _do_registro(reg):
    return dict(
        certificado=reg["certificado"],
        validade=reg["validade"],
        data_homologacao=reg["data_homologacao"],
        situacao=reg["situacao_requerimento"] or reg["situacao_certificado"],
        situacao_certificado=reg["situacao_certificado"],
        tipo_produto_anatel=reg["categoria"],
        marca=reg["marca"],
        fabricante_nome=reg["fabricante"],
        solicitante=reg["solicitante"],
        cnpj=reg["cnpj"],
    )


def sincronizar(db, achados, solicitante=SOLICITANTE_PADRAO, resumo=None):
    """Grava os registros da ANATEL nas homologacoes, sem apagar sua curadoria.

    Devolve o relatorio do que mudou, para a tela mostrar e ficar no historico.
    """
    from .models import Homologacao, HomologacaoModelo, Produto, SincronizacaoAnatel

    por_digitos = {}
    for reg in achados:
        if not reg["digitos"]:
            continue
        por_digitos.setdefault(reg["digitos"], []).append(reg)

    existentes = {}
    for h in Homologacao.query.all():
        chave = so_digitos(h.numero)
        if chave:
            existentes.setdefault(chave, h)

    produtos = {sem_acento(p.modelo): p for p in Produto.query.all() if p.modelo}
    agora = datetime.now()
    criadas, atualizadas, mudancas = [], [], []
    modelos_novos = produtos_novos = 0

    for digitos, grupo in sorted(por_digitos.items()):
        principal = grupo[0]
        dados = _do_registro(principal)
        # A base publica traz UMA LINHA POR ENSAIO. Um mesmo certificado pode
        # ter sido ensaiado como leitor de cartao E como transceptor Wi-Fi: sao
        # duas linhas com o mesmo numero de homologacao. A chave e o numero, e
        # os tipos se somam - senao ficava valendo so o do primeiro ensaio.
        ensaios = []
        for reg in grupo:
            tipo = (reg.get("tipo_produto") or "").strip()
            if tipo and tipo not in ensaios:
                ensaios.append(tipo)
        dados["ensaios_anatel"] = "\n".join(sorted(ensaios))
        h = existentes.get(digitos)
        if h is None:
            h = Homologacao(numero=principal["numero"], origem="ANATEL")
            db.session.add(h)
            criadas.append(principal["numero"])
        else:
            for campo, valor in dados.items():
                anterior = getattr(h, campo, None)
                if valor and anterior != valor:
                    rotulo = {"validade": "validade", "situacao": "situação",
                              "situacao_certificado": "situação do certificado",
                              "ensaios_anatel": "ensaios"}.get(campo)
                    if rotulo:
                        mudancas.append(dict(numero=h.numero, campo=rotulo,
                                             de=str(anterior or "—"), para=str(valor)))
            if h.numero != principal["numero"]:
                h.numero = principal["numero"]
            atualizadas.append(h.numero)
        for campo, valor in dados.items():
            if valor:
                setattr(h, campo, valor)
        h.sincronizado_em = agora
        # Achou na base publica: a origem E a ANATEL, mesmo que a ficha tenha
        # nascido digitada aqui. "Manual" fica para o que so existe localmente -
        # senao a tela dizia "origem: Manual" num registro que a sincronizacao
        # reescreve a cada leitura, e a contagem "da ANATEL" saia menor.
        h.origem = "ANATEL"
        db.session.flush()

        ja_tem = {sem_acento(m.modelo) for m in h.modelos}
        for reg in grupo:
            chave = sem_acento(reg["modelo"])
            if not reg["modelo"] or chave in ja_tem:
                continue
            ja_tem.add(chave)
            # Todo modelo certificado entra no catalogo de Produtos. Sem isto a
            # tela de Produtos ficaria menor que a base da ANATEL.
            produto = produtos.get(chave)
            if produto is None:
                produto = Produto(modelo=reg["modelo"],
                                  natureza=h.natureza or "Produto acabado",
                                  tipo_equipamento=h.tipo or "",
                                  categoria_anatel=reg["categoria"] or "Categoria II")
                db.session.add(produto)
                produtos[chave] = produto
                produtos_novos += 1
            db.session.add(HomologacaoModelo(homologacao=h, modelo=reg["modelo"],
                                             produto=produto))
            modelos_novos += 1

        # modelos que ja estavam na homologacao mas sem ficha ligada
        for vinculo in h.modelos:
            if vinculo.produto_id is None:
                vinculo.produto = produtos.get(sem_acento(vinculo.modelo))

    registro = SincronizacaoAnatel(
        criado_em=agora, solicitante=solicitante,
        linhas_no_arquivo=(resumo or {}).get("linhas_no_arquivo", 0),
        encontradas=len(achados), homologacoes=len(por_digitos),
        criadas=len(criadas), atualizadas=len(atualizadas), modelos_novos=modelos_novos,
        produtos_novos=produtos_novos,
        mudancas="\n".join(f"{m['numero']}: {m['campo']} {m['de']} → {m['para']}"
                           for m in mudancas))
    db.session.add(registro)
    db.session.commit()
    return dict(criadas=criadas, atualizadas=atualizadas, mudancas=mudancas,
                modelos_novos=modelos_novos, produtos_novos=produtos_novos,
                homologacoes=len(por_digitos),
                encontradas=len(achados), resumo=resumo or {}, registro=registro)


def atualizar(db, solicitante=SOLICITANTE_PADRAO, forcar_download=True, base_dir=None):
    """Baixa a base e sincroniza. E o que o botao 'Atualizar agora' chama."""
    caminho = baixar_zip(pasta_cache(base_dir) / "produtos_certificados.zip",
                         forcar=forcar_download)
    achados, resumo = registros(caminho, solicitante)
    return sincronizar(db, achados, solicitante=solicitante, resumo=resumo)
