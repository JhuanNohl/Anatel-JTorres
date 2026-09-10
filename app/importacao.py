"""Importa para este sistema os dados do app ANATEL antigo.

O app antigo guardava, em .anatel_cache/:
  anatel_produtos.sqlite   a base consolidada: natureza, tipo, produtos do modulo
                           e versao de placa (a planilha de categorias ja aplicada)
  fotos_homologacao.json   quais fotos pertencem a cada homologacao
  fotos/                   os arquivos das fotos
  categorias_config.json   os ajustes feitos na tela (complementam o sqlite)

Pode rodar quantas vezes quiser: nada e duplicado e nada que voce ajustou aqui
e sobrescrito. Sincronize a base da ANATEL ANTES, para as homologacoes existirem.

Chamado pela tela (Base ANATEL) e pelo importar_base_antiga.py na linha de comando.
"""
import json
import re
import shutil
import sqlite3
from pathlib import Path

from .anatel import sem_acento, so_digitos
from .extensions import db
from .models import (AplicacaoHomologacao, FotoHomologacao, Homologacao,
                     HomologacaoModelo, Produto)
from .utils import pasta_upload, slugify


NATUREZAS = {"modulo": "Módulo", "produto acabado": "Produto acabado"}


def _quebrar_na_barra(item):
    """Decide se a barra separa modelos ou faz parte do nome.

    "TF1700/FR1200/F16"   -> tres modelos.
    "Antena UHF 5/10 Pro" -> UM produto; a barra e do nome comercial.
    Regra: separa quando saem 3 ou mais pedacos, ou quando nenhum pedaco tem
    espaco (codigo de modelo raramente tem espaco).
    """
    if "/" not in item:
        return [item]
    pedacos = [p.strip() for p in item.split("/") if p.strip()]
    if len(pedacos) >= 3 or all(" " not in p for p in pedacos):
        return pedacos
    return [item]


def separar_produtos(texto):
    """A lista de produtos do modulo vem separada por virgula, ponto-e-virgula,
    barra ou quebra de linha.

    Ex.: "ZK8500R[ID], VFXX0, P160, (SF100, SF300, SF400(zlm60)), BR1200"
    Parenteses agrupam variantes do mesmo produto, entao nao quebro dentro deles.
    """
    itens, atual, profundidade = [], [], 0
    for ch in (texto or ""):
        if ch in "([":
            profundidade += 1
        elif ch in ")]":
            profundidade = max(0, profundidade - 1)
        if ch in ",;\n" and profundidade == 0:
            itens.append("".join(atual))
            atual = []
            continue
        atual.append(ch)
    itens.append("".join(atual))

    limpos, vistos = [], set()
    for bruto in itens:
        for item in _quebrar_na_barra(re.sub(r"\s+", " ", bruto).strip()):
            item = item.strip(" .-")
            chave = sem_acento(item)
            if item and chave not in vistos:
                vistos.add(chave)
                limpos.append(item)
    return limpos


def curadoria_do_app_antigo(cache):
    """Junta o que o app antigo sabia sobre cada modelo.

    Chave = modelo normalizado. O sqlite manda (ja tem a planilha aplicada) e o
    categorias_config.json complementa o que faltar.
    """
    registros = {}
    banco = cache / "anatel_produtos.sqlite"
    if banco.exists():
        con = sqlite3.connect(banco)
        con.row_factory = sqlite3.Row
        for linha in con.execute(
                "select modelo, homologacao, categoria_1, categoria_2, categoria_3, "
                "versao_placa_modulo from produtos"):
            chave = sem_acento(linha["modelo"])
            if not chave:
                continue
            atual = registros.setdefault(chave, dict(modelo=linha["modelo"], digitos=set()))
            atual["digitos"].add(so_digitos(linha["homologacao"]))
            for campo in ("categoria_1", "categoria_2", "categoria_3",
                          "versao_placa_modulo"):
                if (linha[campo] or "").strip() and not atual.get(campo):
                    atual[campo] = linha[campo].strip()
        con.close()

    arquivo = cache / "categorias_config.json"
    if arquivo.exists():
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        for reg in dados.get("categorias", []):
            chave = sem_acento(reg.get("modelo"))
            if not chave:
                continue
            atual = registros.setdefault(chave, dict(modelo=reg.get("modelo"),
                                                     digitos=set()))
            for campo in ("categoria_1", "categoria_2", "categoria_3",
                          "versao_placa_modulo"):
                if (reg.get(campo) or "").strip():
                    atual[campo] = reg[campo].strip()
    return registros


EXTENSOES_DE_IMAGEM = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"}


class ImportacaoInvalida(Exception):
    """Falta algo para importar - a mensagem e mostrada ao usuario."""


def indexar_imagens(raiz):
    """{nome do arquivo em minusculas: caminho} de toda imagem abaixo de raiz.

    Procurar por nome, e nao por caminho fixo, deixa a importacao imune a
    extracao aninhada ("...\\dados-app-antigo\\dados-app-antigo\\...") e a
    renomeacao da pasta de fotos.
    """
    achadas = {}
    raiz = Path(raiz)
    if not raiz.exists():
        return achadas
    for caminho in raiz.rglob("*"):
        if caminho.is_file() and caminho.suffix.lower() in EXTENSOES_DE_IMAGEM:
            achadas.setdefault(caminho.name.lower(), caminho)
    return achadas


def achar_cache(pasta):
    """Encontra a .anatel_cache mesmo que a extracao tenha aninhado pastas."""
    pasta = Path(pasta)
    if pasta.name == ".anatel_cache" and pasta.exists():
        return pasta
    direta = pasta / ".anatel_cache"
    if direta.exists():
        return direta
    if pasta.exists():                       # procura mais fundo, ate 3 niveis
        for nivel in ("*/.anatel_cache", "*/*/.anatel_cache", "*/*/*/.anatel_cache"):
            for achada in pasta.glob(nivel):
                if achada.is_dir():
                    return achada
    return None


def importar(pasta_antiga):
    """Le a pasta do app antigo e grava aqui. Devolve o relatorio do que entrou."""
    pasta_antiga = Path(pasta_antiga)
    cache = achar_cache(pasta_antiga)
    if cache is None:
        raise ImportacaoInvalida(
            f"Não encontrei a pasta “.anatel_cache” em {pasta_antiga}. "
            "Informe a pasta do app ANATEL antigo (a que tem o anatel_server.py) "
            "ou a pasta “dados-app-antigo” que veio no ZIP da atualização.")

    curadoria = curadoria_do_app_antigo(cache)
    fotos_cfg = {}
    arquivo_fotos = cache / "fotos_homologacao.json"
    if arquivo_fotos.exists():
        fotos_cfg = json.loads(arquivo_fotos.read_text(encoding="utf-8"))
    registros_fotos = fotos_cfg.get("fotos", [])

    homologacoes = Homologacao.query.all()
    if not homologacoes:
        raise ImportacaoInvalida(
            "A base de homologações está vazia. Clique em “Atualizar agora” para "
            "trazer as homologações da ANATEL antes de importar.")
    por_digitos = {}
    for h in homologacoes:
        por_digitos.setdefault(so_digitos(h.numero), h)
    por_modelo = {}
    for m in HomologacaoModelo.query.all():
        por_modelo.setdefault(sem_acento(m.modelo), []).append(m.homologacao)
    produtos = {sem_acento(p.modelo): p for p in Produto.query.all() if p.modelo}

    # ---------------------------------------------------------------- curadoria
    tocadas, vinculos, criados, sem_par = 0, 0, 0, []
    for chave, reg in sorted(curadoria.items()):
        natureza = NATUREZAS.get(sem_acento(reg.get("categoria_1")), "")
        tipo = reg.get("categoria_2", "")
        versao = reg.get("versao_placa_modulo", "")
        usados = separar_produtos(reg.get("categoria_3"))

        alvos = list(por_modelo.get(chave) or [])
        for digitos in reg.get("digitos", set()):
            h = por_digitos.get(digitos)
            if h is not None and h not in alvos:
                alvos.append(h)
        if not alvos:
            sem_par.append(reg["modelo"])

        for h in alvos:
            if natureza and not (h.natureza or "").strip():
                h.natureza = natureza
            if tipo and not (h.tipo or "").strip():
                h.tipo = tipo
            if versao and not (h.versao_placa or "").strip():
                h.versao_placa = versao
            if usados and not (h.aplicacoes or "").strip():
                h.aplicacoes = ", ".join(usados)
            ja = {sem_acento(a.modelo) for a in h.aplicacoes_produtos}
            for nome in usados:
                if sem_acento(nome) in ja:
                    continue
                ja.add(sem_acento(nome))
                db.session.add(AplicacaoHomologacao(homologacao=h, modelo=nome))
                vinculos += 1
            tocadas += 1

        # o modelo entra no catalogo, com a natureza e o tipo que voce definiu
        produto = produtos.get(chave)
        if produto is None:
            produto = Produto(modelo=reg["modelo"],
                              natureza=natureza or "Produto acabado",
                              tipo_equipamento=tipo)
            db.session.add(produto)
            produtos[chave] = produto
            criados += 1
        else:
            if natureza:
                produto.natureza = natureza
            if tipo and not (produto.tipo_equipamento or "").strip():
                produto.tipo_equipamento = tipo
    db.session.flush()

    # ------------------------------------------- modelos da ANATEL que faltam no catalogo
    for m in HomologacaoModelo.query.all():
        chave = sem_acento(m.modelo)
        if chave not in produtos:
            p = Produto(modelo=m.modelo,
                        natureza=(m.homologacao.natureza or "Produto acabado"),
                        tipo_equipamento=(m.homologacao.tipo or ""))
            db.session.add(p)
            produtos[chave] = p
            criados += 1
        if m.produto_id is None:
            m.produto = produtos[chave]
    db.session.flush()

    # ------------------------------------------- liga os vinculos ao catalogo
    fora_do_catalogo = 0
    for a in AplicacaoHomologacao.query.all():
        if a.produto_id is None:
            a.produto = produtos.get(sem_acento(a.modelo))
            if a.produto is None:
                fora_do_catalogo += 1
    db.session.flush()

    # ---------------------------------------------------------------- fotos
    # As fotos sao procuradas POR NOME em qualquer lugar abaixo da pasta
    # informada. Assim nao importa se a extracao aninhou um nivel a mais nem se
    # a pasta se chama "fotos" - o que importa e o arquivo existir.
    disponiveis = indexar_imagens(pasta_antiga if pasta_antiga != cache else cache.parent)
    copiadas, ja_tinha, nao_encontradas = 0, 0, []
    for reg in registros_fotos:
        alvo = por_digitos.get(so_digitos(reg.get("homologacao")))
        if not alvo:
            continue
        existentes = {f.nome_original for f in alvo.fotos}
        ordem = max([f.ordem for f in alvo.fotos] or [0])
        relativo = f"homologacoes/{slugify(alvo.numero)}"
        destino = pasta_upload("homologacoes", slugify(alvo.numero))
        for linha in (reg.get("fotos") or "").splitlines():
            nome = linha.strip().split("/")[-1]
            if not nome:
                continue
            if nome in existentes:
                ja_tinha += 1
                continue
            arquivo_origem = disponiveis.get(nome.lower())
            if arquivo_origem is None:
                nao_encontradas.append(nome)
                continue
            ordem += 1
            nome_final = f"{ordem:02d}-{nome}"
            shutil.copy2(arquivo_origem, destino / nome_final)
            db.session.add(FotoHomologacao(homologacao=alvo,
                                           arquivo=f"{relativo}/{nome_final}",
                                           nome_original=nome, ordem=ordem))
            existentes.add(nome)
            copiadas += 1

    db.session.commit()

    return dict(pasta=str(cache), modelos_lidos=len(curadoria),
                homologacoes_com_foto=len(registros_fotos), curadoria_aplicada=tocadas,
                vinculos=vinculos, produtos_criados=criados, fotos=copiadas,
                fotos_repetidas=ja_tinha, fora_do_catalogo=fora_do_catalogo,
                sem_homologacao=sem_par,
                imagens_na_pasta=len(disponiveis),
                fotos_nao_encontradas=nao_encontradas)
