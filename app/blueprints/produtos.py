"""Produtos / modelos: catalogo com a situacao real na ANATEL.

Esta area junta tres coisas que antes viviam separadas:
  - o catalogo de modelos da ZKTeco (ficha tecnica usada nos processos);
  - a situacao de cada modelo na base publica da ANATEL (via homologacao);
  - as fotos do produto e a correlacao modulo -> produtos que o usam.
"""
from datetime import date, datetime

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)
from sqlalchemy import or_

from .. import anatel, importacao
from ..extensions import db
from ..models import (AplicacaoHomologacao, Fabricante, Foto, FotoHomologacao,
                      FotoProduto, Homologacao, HomologacaoModelo,
                      NATUREZAS_PRODUTO, Produto, SincronizacaoAnatel)
from ..utils import is_imagem, pasta_upload, remover_arquivo, salvar_arquivo, slugify

bp = Blueprint("produtos", __name__, url_prefix="/produtos")

DIAS_PARA_AVISAR = 15          # base publica muda quase todo dia util

SITUACOES_FILTRO = [
    ("processo", "Em certificação"),
    ("vencendo", "Vencem em 90 dias"),
    ("vigentes", "Vigentes na ANATEL"),
    ("problema", "Sem vigência"),
    ("sem", "Sem homologação e sem processo"),
]

# Ordem em que as situacoes aparecem na lista: primeiro o que pede acao
# (processo andando, homologacao vencendo), depois o que esta em ordem, e por
# ultimo o que ja morreu. Ordenar por nome do modelo escondia justamente o que
# interessa.
PESO_SITUACAO = {"processo": 1, "vencendo": 2, "vigentes": 3, "problema": 4, "sem": 5}


# ------------------------------------------------------------------ apoio

def _idade_da_base():
    """Ha quantos dias a base publica foi lida. None = nunca foi lida."""
    ultima = SincronizacaoAnatel.query.order_by(SincronizacaoAnatel.id.desc()).first()
    if ultima is None or not ultima.criado_em:
        return None, None
    return ultima, (datetime.now() - ultima.criado_em).days


def _homologacoes_do_produto(produto):
    """Homologacoes em que o modelo aparece no certificado."""
    vistos, saida = set(), []
    for vinculo in produto.homologacoes_modelo:
        h = vinculo.homologacao
        if h and h.id not in vistos:
            vistos.add(h.id)
            saida.append(h)
    return sorted(saida, key=lambda h: (h.validade or date.min), reverse=True)


def _modulos_do_produto(produto):
    """Modulos homologados que este produto acabado usa (o caminho inverso)."""
    vistos, saida = set(), []
    for ap in produto.aplicacoes:
        h = ap.homologacao
        if h and h.id not in vistos:
            vistos.add(h.id)
            saida.append(h)
    return sorted(saida, key=lambda h: (h.validade or date.min), reverse=True)


def _processo_aberto(produto):
    """Processo de certificacao ainda em andamento para este modelo."""
    abertos = [p for p in produto.processos if not _encerrado(p.status)]
    return abertos[0] if abertos else None


def _encerrado(nome_do_status):
    from ..models import status_por_nome
    situacao = status_por_nome(nome_do_status)
    return bool(situacao and situacao.encerra)


def _dias_de_aviso():
    from ..models import config_anatel
    return config_anatel().dias_de_aviso


def _situacao(produto, dias_de_aviso=None):
    """Resume a situacao do modelo.

    Ordem de importancia: homologacao valida > homologacao sem vigencia >
    processo em andamento > nada. Um modelo pode estar em varias homologacoes
    (renovacoes, variantes); o que interessa e se EXISTE alguma valida hoje.
    """
    todas = _homologacoes_do_produto(produto) + _modulos_do_produto(produto)
    if not todas:
        processo = _processo_aberto(produto)
        if processo:
            return dict(chave="processo", rotulo="Em certificação", cor="info",
                        homologacao=None, processo=processo)
        return dict(chave="sem", rotulo="Sem homologação", cor="neutro",
                    homologacao=None, processo=None)
    vigentes = [h for h in todas if h.vigente]
    if not vigentes:
        pior = todas[0]
        return dict(chave="problema", rotulo=pior.situacao or "Sem vigência",
                    cor="erro", homologacao=pior,
                    processo=_processo_aberto(produto))
    melhor = max(vigentes, key=lambda h: h.validade or date.min)
    dias = melhor.dias_para_vencer
    limite = dias_de_aviso if dias_de_aviso is not None else _dias_de_aviso()
    if dias is not None and dias <= limite:
        return dict(chave="vencendo", rotulo=f"Vence em {dias} dias", cor="warn",
                    homologacao=melhor, processo=_processo_aberto(produto))
    return dict(chave="vigentes", rotulo="Vigente", cor="ok", homologacao=melhor,
                processo=None)


def _contagens_de_modelos(dias_de_aviso=None):
    """Quantos MODELOS em cada grupo. A tela de Homologacoes usa para fechar
    a conta com a contagem de certificados dela."""
    limite = dias_de_aviso if dias_de_aviso is not None else _dias_de_aviso()
    contagens = {chave: 0 for chave, _ in SITUACOES_FILTRO}
    for produto in Produto.query.all():
        contagens[_situacao(produto, limite)["chave"]] += 1
    contagens["_total"] = sum(contagens.values())
    return contagens


def _fotos_dos_processos(produto):
    """Fotos tiradas durante a certificacao, na ordem das vistas.

    Enquanto o modelo nao tem homologacao, e nessas fotos que ele aparece - nao
    faz sentido a ficha do produto ignorar o que ja foi fotografado no processo.
    """
    fotos = []
    for processo in produto.processos:
        fotos.extend(processo.fotos)
    return sorted(fotos, key=lambda f: (f.vista.ordem if f.vista else 999, f.id))


def _todas_as_fotos(produto):
    """Todas as fotos que existem para o modelo, de todas as origens.

    Nenhuma e escondida nem copiada: a lista junta o que foi enviado no modelo,
    o que esta na homologacao e o que foi fotografado no processo. Cada item diz
    de onde veio, e e isso que permite marcar a capa sem mover nada.
    """
    itens = []
    for foto in produto.fotos:
        itens.append(dict(origem="produto", id=foto.id, arquivo=foto.arquivo,
                          titulo=foto.legenda or foto.nome_original or produto.modelo,
                          fonte="enviada no modelo", pode_excluir=True))
    for h in _homologacoes_do_produto(produto) + _modulos_do_produto(produto):
        for foto in h.fotos:
            itens.append(dict(origem="homologacao", id=foto.id, arquivo=foto.arquivo,
                              titulo=foto.legenda or f"Homologação {h.numero}",
                              fonte=f"homologação {h.numero}", pode_excluir=False))
    for processo in produto.processos:
        for foto in sorted(processo.fotos,
                           key=lambda f: (f.vista.ordem if f.vista else 999, f.id)):
            itens.append(dict(
                origem="processo", id=foto.id, arquivo=foto.arquivo,
                titulo=(foto.vista.nome if foto.vista else foto.legenda) or processo.numero,
                fonte=f"processo {processo.numero}", pode_excluir=False))

    escolhida = None
    for item in itens:
        item["e_capa"] = (produto.capa_origem == item["origem"]
                          and produto.capa_ref_id == item["id"])
        if item["e_capa"]:
            escolhida = item
    if escolhida is None and itens:
        itens[0]["e_capa"] = True          # sem marcacao, a primeira serve de capa
    return itens


def _capa(produto):
    """A foto marcada como capa - ou a primeira disponivel, se nada foi marcado."""
    for item in _todas_as_fotos(produto):
        if item["e_capa"]:
            return item
    return None


def _usado_por(homologacoes):
    """Produtos acabados que usam este modelo como modulo, sem repetir."""
    vistos, saida = set(), []
    for h in homologacoes:
        for ap in h.aplicacoes_produtos:
            chave = anatel.sem_acento(ap.modelo)
            if chave and chave not in vistos:
                vistos.add(chave)
                saida.append(ap)
    return saida


def _ordem_da_ficha(ficha):
    """Situacao primeiro; dentro dela, o vencimento mais proximo na frente."""
    situacao = ficha["situacao"]
    h = situacao.get("homologacao")
    dias = h.dias_para_vencer if h else None
    return (PESO_SITUACAO.get(situacao["chave"], 9),
            dias if dias is not None else 99999,
            ficha["produto"].modelo.lower())


def _texto_de_busca(ficha):
    """Tudo que a linha mostra, junto e sem acento, para o filtro ao vivo."""
    p = ficha["produto"]
    h = ficha["situacao"].get("homologacao")
    processo = ficha["situacao"].get("processo")
    pedacos = [p.modelo, p.nome_comercial, p.natureza, p.tipo_equipamento, p.familia,
               ficha["situacao"]["rotulo"]]
    if h:
        pedacos += [h.numero, h.certificado, h.situacao, h.situacao_certificado,
                    h.validade.strftime("%d/%m/%Y") if h.validade else ""]
        # os ensaios do certificado (leitor de cartao, transceptor Wi-Fi...):
        # filtrar por "radiacao restrita" tem de achar o modelo
        pedacos += h.ensaios
    for outra in ficha["homologacoes"] + ficha["modulos"]:
        pedacos += outra.ensaios
    if processo:
        pedacos += [processo.numero, processo.status]
    if ficha["usados_por"]:
        pedacos.append(f"{len(ficha['usados_por'])} produtos")
    return anatel.sem_acento(" ".join(x for x in pedacos if x))


def _ficha(produto, dias_de_aviso=None):
    homologacoes = _homologacoes_do_produto(produto)
    fotos = _todas_as_fotos(produto)
    ficha = dict(produto=produto, situacao=_situacao(produto, dias_de_aviso),
                 capa=next((f for f in fotos if f["e_capa"]), None),
                 fotos=fotos,
                 homologacoes=homologacoes, modulos=_modulos_do_produto(produto),
                 usados_por=_usado_por(homologacoes))
    ficha["busca"] = _texto_de_busca(ficha)
    return ficha


# ------------------------------------------------------------------ lista

@bp.route("/")
def lista():
    q = (request.args.get("q") or "").strip()
    natureza = (request.args.get("natureza") or "").strip()
    situacao = (request.args.get("situacao") or "").strip()
    consulta = Produto.query
    if q:
        like = f"%{q}%"
        consulta = consulta.filter(or_(Produto.modelo.ilike(like),
                                       Produto.nome_comercial.ilike(like),
                                       Produto.tipo_equipamento.ilike(like),
                                       Produto.familia.ilike(like)))
    if natureza:
        consulta = consulta.filter(Produto.natureza == natureza)
    dias_de_aviso = _dias_de_aviso()
    fichas = [_ficha(p, dias_de_aviso) for p in consulta.order_by(Produto.modelo).all()]
    fichas.sort(key=_ordem_da_ficha)

    contagens = {chave: 0 for chave, _ in SITUACOES_FILTRO}
    for f in fichas:
        contagens[f["situacao"]["chave"]] += 1
    if situacao:
        fichas = [f for f in fichas if f["situacao"]["chave"] == situacao]

    ultima, dias = _idade_da_base()
    # quantos CERTIFICADOS sustentam cada grupo de modelo: e o que liga esta
    # tela a de Homologacoes, que conta certificados em vez de modelos
    from ..situacao import por_grupo_de_modelo
    certificados = por_grupo_de_modelo(dias_de_aviso)
    return render_template("produtos/lista.html", fichas=fichas, q=q, natureza=natureza,
                           situacao=situacao, contagens=contagens, ultima=ultima,
                           certificados=certificados,
                           dias_da_base=dias, dias_para_avisar=DIAS_PARA_AVISAR,
                           situacoes_filtro=SITUACOES_FILTRO,
                           falta_importar=_falta_importar(),
                           dias_de_aviso=dias_de_aviso,
                           config=_config_para_tela(),
                           pasta_antiga=_dados_do_app_antigo(),
                           total=Produto.query.count())


@bp.route("/<int:pid>")
def detalhe(pid):
    produto = Produto.query.get_or_404(pid)
    return render_template("produtos/detalhe.html", **_ficha(produto), aba="geral")


# ------------------------------------------------------------------ base ANATEL

@bp.route("/base-anatel")
def base():
    historico = (SincronizacaoAnatel.query
                 .order_by(SincronizacaoAnatel.id.desc()).limit(12).all())
    homologacoes = Homologacao.query.all()
    resumo = dict(
        total=len(homologacoes),
        da_anatel=sum(1 for h in homologacoes if h.da_anatel),
        vigentes=sum(1 for h in homologacoes if h.vigente),
        problema=sum(1 for h in homologacoes if not h.vigente),
        com_foto=sum(1 for h in homologacoes if h.fotos),
        modelos=HomologacaoModelo.query.count(),
        aplicacoes=AplicacaoHomologacao.query.count(),
    )
    caminho = anatel.pasta_cache(current_app.config["BASE_DIR"]) / "produtos_certificados.zip"
    from ..models import UNIDADES_DE_PRAZO, config_anatel
    ultima, dias = _idade_da_base()
    return render_template("produtos/base_anatel.html", historico=historico,
                           diagnostico=_diagnostico_da_pasta(),
                           config=config_anatel(), unidades=UNIDADES_DE_PRAZO,
                           resumo=resumo, ultima=ultima, dias_da_base=dias,
                           dias_para_avisar=DIAS_PARA_AVISAR,
                           pasta_sugerida=_pasta_sugerida(),
                           solicitante=_solicitante(), arquivo_local=caminho.exists())


def _solicitante():
    from ..models import Empresa
    empresa = Empresa.query.get(1)
    return (empresa.razao_social if empresa and empresa.razao_social
            else anatel.SOLICITANTE_PADRAO)


@bp.route("/base-anatel/atualizar", methods=["POST"])
def atualizar():
    """Baixa a base publica e sincroniza as homologacoes."""
    try:
        relatorio = anatel.atualizar(db, solicitante=_solicitante(),
                                     base_dir=current_app.config["BASE_DIR"])
    except Exception as erro:                        # rede fora, ZIP mudou, etc.
        flash(f"Não consegui atualizar pela ANATEL: {erro}", "erro")
        return redirect(url_for("produtos.base"))
    partes = [f"{relatorio['encontradas']} registros da ANATEL",
              f"{relatorio['homologacoes']} homologações"]
    if relatorio["criadas"]:
        partes.append(f"{len(relatorio['criadas'])} nova(s)")
    if relatorio["mudancas"]:
        partes.append(f"{len(relatorio['mudancas'])} mudança(s)")
    flash("Base atualizada: " + ", ".join(partes) + ".", "ok")
    return redirect(url_for("produtos.base"))


def _config_para_tela():
    from ..models import config_anatel
    return config_anatel()


def _diagnostico_da_pasta():
    """O que o servidor esta vendo na pasta de dados do app antigo.

    Existe porque "importei e nao veio foto" e impossivel de resolver as cegas.
    """
    from pathlib import Path
    caminho = Path(_pasta_sugerida())
    cache = importacao.achar_cache(caminho)
    if cache is None:
        return dict(caminho=str(caminho), existe=caminho.exists(), cache=None,
                    imagens=0, tem_base=False, tem_lista=False)
    return dict(
        caminho=str(caminho), existe=True, cache=str(cache),
        imagens=len(importacao.indexar_imagens(cache.parent)),
        tem_base=(cache / "anatel_produtos.sqlite").exists(),
        tem_lista=(cache / "fotos_homologacao.json").exists(),
    )


def _recado_da_importacao(r):
    """Monta o aviso do que entrou - e o que NAO entrou, que e o que importa."""
    partes = []
    if r["curadoria_aplicada"]:
        partes.append(f"natureza e tipo em {r['curadoria_aplicada']} homologações")
    if r["vinculos"]:
        partes.append(f"{r['vinculos']} vínculos módulo → produto")
    if r["produtos_criados"]:
        partes.append(f"{r['produtos_criados']} modelos novos")
    if r["fotos"]:
        partes.append(f"{r['fotos']} fotos")
    faltando = r.get("fotos_nao_encontradas") or []
    if faltando:
        flash(
            f"{len(faltando)} foto(s) do app antigo não foram encontradas na pasta "
            f"{r['pasta']} — só {r.get('imagens_na_pasta', 0)} arquivo(s) de imagem "
            "existem lá. A extração do ZIP provavelmente não trouxe a pasta "
            "“fotos”. Extraia o ZIP de novo (com o sistema parado) e clique outra "
            f"vez. Exemplo de arquivo que faltou: {faltando[0]}", "erro")
    return partes


def _dados_do_app_antigo():
    """Pasta com os dados do app antigo, se ela estiver aqui. None se nao houver."""
    from pathlib import Path
    caminho = Path(_pasta_sugerida())
    return caminho if (caminho / ".anatel_cache").exists() else None


def _falta_importar():
    """Ha dados do app antigo esperando para entrar?"""
    if _dados_do_app_antigo() is None:
        return False
    return (AplicacaoHomologacao.query.count() == 0
            or FotoHomologacao.query.count() == 0)


@bp.route("/preparar", methods=["POST"])
def preparar():
    """Faz tudo de uma vez: le a base da ANATEL e traz os dados do app antigo.

    Existe porque exigir dois cliques na ordem certa e um jeito bom de a pessoa
    achar que instalou e nao ter instalado nada.
    """
    recado = []
    try:
        rel = anatel.atualizar(db, solicitante=_solicitante(),
                               base_dir=current_app.config["BASE_DIR"])
        recado.append(f"{rel['encontradas']} registros da ANATEL, "
                      f"{rel['homologacoes']} homologações")
        if rel["produtos_novos"]:
            recado.append(f"{rel['produtos_novos']} modelos novos no catálogo")
    except Exception as erro:
        flash(f"Não consegui ler a base da ANATEL: {erro}. "
              "Os dados do app antigo não foram importados — tente de novo.", "erro")
        return redirect(url_for("produtos.lista"))

    pasta = _dados_do_app_antigo()
    if pasta is not None:
        try:
            recado += _recado_da_importacao(importacao.importar(pasta))
        except importacao.ImportacaoInvalida as erro:
            flash(f"Base da ANATEL lida, mas a importação parou: {erro}", "erro")
            return redirect(url_for("produtos.lista"))
    flash("Pronto: " + ", ".join(recado) + ".", "ok")
    return redirect(url_for("produtos.lista"))


@bp.route("/base-anatel/agendamento", methods=["POST"])
def agendamento():
    """Liga/desliga a releitura automatica e ajusta de quanto em quanto tempo."""
    from ..models import HORAS_POR_UNIDADE, config_anatel
    config = config_anatel()
    config.automatico = bool(request.form.get("automatico"))
    valor = (request.form.get("intervalo_valor") or "").strip()
    config.intervalo_valor = max(1, int(valor)) if valor.isdigit() else 1
    unidade = (request.form.get("intervalo_unidade") or "dias").strip()
    config.intervalo_unidade = unidade if unidade in HORAS_POR_UNIDADE else "dias"
    dias = (request.form.get("dias_aviso_vencimento") or "").strip()
    if dias.isdigit():
        config.dias_aviso_vencimento = min(720, max(1, int(dias)))
    db.session.commit()
    if config.automatico:
        flash(f"A base será relida sozinha a cada {config.intervalo_por_extenso}.", "ok")
    else:
        flash("Releitura automática desligada — a base só muda quando você clicar.", "ok")
    return redirect(url_for("produtos.base"))


@bp.route("/base-anatel/importar", methods=["POST"])
def importar_antigo():
    """Traz a curadoria e as fotos do app ANATEL antigo, por caminho de pasta."""
    caminho = (request.form.get("pasta") or "").strip().strip('"')
    if not caminho:
        flash("Informe a pasta do app ANATEL antigo.", "erro")
        return redirect(url_for("produtos.base"))
    try:
        r = importacao.importar(caminho)
    except importacao.ImportacaoInvalida as erro:
        flash(str(erro), "erro")
        return redirect(url_for("produtos.base"))
    except Exception as erro:                        # permissao, disco, arquivo corrompido
        flash(f"Não consegui importar: {erro}", "erro")
        return redirect(url_for("produtos.base"))
    partes = _recado_da_importacao(r)
    if not partes:
        flash("Nada novo para importar — os dados do app antigo já estão aqui.", "info")
    else:
        flash("Importado do app antigo: " + ", ".join(partes) + ".", "ok")
    return redirect(url_for("produtos.base"))


def _pasta_sugerida():
    """Onde estao os dados do app antigo, para o campo vir preenchido.

    A pasta "dados-app-antigo" vem no ZIP da atualizacao, entao ela e a
    primeira tentativa: assim nao e preciso alcancar a maquina do app antigo.
    """
    from pathlib import Path
    raiz = Path(current_app.config["BASE_DIR"])
    for candidata in (raiz / "dados-app-antigo", raiz.parent / "ANATEL",
                      raiz / "ANATEL", raiz.parent / "anatel",
                      Path.home() / "ANATEL"):
        if (candidata / ".anatel_cache").exists():
            return str(candidata)
    return str(raiz / "dados-app-antigo")


# ------------------------------------------------------------------ fotos do modelo

def _pasta_do_produto(produto):
    return pasta_upload("produtos", slugify(produto.modelo))


def _proxima_ordem(produto):
    return max([f.ordem for f in produto.fotos] or [0]) + 1


@bp.route("/<int:pid>/fotos", methods=["POST"])
def enviar_fotos_produto(pid):
    """Anexa fotos ao modelo. Vale mesmo sem homologacao - modelo em certificacao
    tambem tem foto de catalogo."""
    produto = Produto.query.get_or_404(pid)
    arquivos = [f for f in request.files.getlist("fotos") if f and f.filename]
    if not arquivos:
        flash("Escolha ao menos uma imagem.", "erro")
        return redirect(url_for("produtos.detalhe", pid=pid))
    caminho = _pasta_do_produto(produto)
    ordem = _proxima_ordem(produto) - 1
    enviadas = 0
    for arquivo in arquivos:
        if not is_imagem(arquivo.filename):
            flash(f"“{arquivo.filename}” não é imagem e foi ignorado.", "erro")
            continue
        ordem += 1
        relativo, _tamanho = salvar_arquivo(arquivo, caminho, prefixo=f"{ordem:02d}")
        db.session.add(FotoProduto(produto=produto, arquivo=relativo,
                                   nome_original=arquivo.filename, ordem=ordem))
        enviadas += 1
    db.session.commit()
    if enviadas:
        flash(f"{enviadas} foto(s) anexada(s) a {produto.modelo}."
              + (" A primeira é a capa." if enviadas == ordem else ""), "ok")
    return redirect(url_for("produtos.detalhe", pid=pid))


@bp.route("/<int:pid>/capa/<origem>/<int:fid>", methods=["POST"])
def marcar_capa(pid, origem, fid):
    """Marca qual foto e a capa do modelo. Nao move, nao copia, nao esconde.

    A capa pode ser uma foto enviada no modelo, uma da homologacao ou uma do
    processo - todas continuam visiveis na ficha do jeito que estavam.
    """
    produto = Produto.query.get_or_404(pid)
    if origem not in ("produto", "homologacao", "processo"):
        abort(404)
    existe = any(f["origem"] == origem and f["id"] == fid
                 for f in _todas_as_fotos(produto))
    if not existe:
        flash("Essa foto não pertence a este modelo.", "erro")
        return redirect(url_for("produtos.detalhe", pid=pid))
    produto.capa_origem = origem
    produto.capa_ref_id = fid
    db.session.commit()
    flash("Capa definida — é esta foto que aparece na lista de produtos.", "ok")
    return redirect(url_for("produtos.detalhe", pid=pid))


@bp.route("/<int:pid>/capa/limpar", methods=["POST"])
def limpar_capa(pid):
    produto = Produto.query.get_or_404(pid)
    produto.capa_origem, produto.capa_ref_id = "", None
    db.session.commit()
    flash("Marcação de capa removida — volta a valer a primeira foto.", "ok")
    return redirect(url_for("produtos.detalhe", pid=pid))


@bp.route("/foto-produto/<int:fid>/capa", methods=["POST"])
def capa_do_produto(fid):
    """Atalho antigo: marca a foto enviada no modelo como capa."""
    foto = FotoProduto.query.get_or_404(fid)
    return marcar_capa(foto.produto_id, "produto", foto.id)


@bp.route("/foto-produto/<int:fid>/excluir", methods=["POST"])
def excluir_foto_produto(fid):
    foto = FotoProduto.query.get_or_404(fid)
    pid = foto.produto_id
    produto = foto.produto
    if produto.capa_origem == "produto" and produto.capa_ref_id == foto.id:
        produto.capa_origem, produto.capa_ref_id = "", None
    remover_arquivo(foto.arquivo)
    db.session.delete(foto)
    db.session.commit()
    flash("Foto removida do modelo.", "ok")
    return redirect(url_for("produtos.detalhe", pid=pid))


# ------------------------------------------------------------------ fotos da homologacao

@bp.route("/homologacao/<int:hid>/fotos", methods=["POST"])
def enviar_fotos(hid):
    h = Homologacao.query.get_or_404(hid)
    arquivos = [f for f in request.files.getlist("fotos") if f and f.filename]
    if not arquivos:
        flash("Escolha ao menos uma imagem.", "erro")
        return redirect(_voltar(h))
    caminho = pasta_upload("homologacoes", slugify(h.numero))
    ordem = max([f.ordem for f in h.fotos] or [0])
    enviadas = 0
    for arquivo in arquivos:
        if not is_imagem(arquivo.filename):
            flash(f"“{arquivo.filename}” não é imagem e foi ignorado.", "erro")
            continue
        ordem += 1
        relativo, _tamanho = salvar_arquivo(arquivo, caminho, prefixo=f"{ordem:02d}")
        db.session.add(FotoHomologacao(homologacao=h, arquivo=relativo,
                                       nome_original=arquivo.filename, ordem=ordem))
        enviadas += 1
    db.session.commit()
    if enviadas:
        flash(f"{enviadas} foto(s) anexada(s) à homologação {h.numero}.", "ok")
    return redirect(_voltar(h))


@bp.route("/foto/<int:fid>/excluir", methods=["POST"])
def excluir_foto(fid):
    foto = FotoHomologacao.query.get_or_404(fid)
    h = foto.homologacao
    remover_arquivo(foto.arquivo)
    db.session.delete(foto)
    db.session.commit()
    flash("Foto removida.", "ok")
    return redirect(_voltar(h))


@bp.route("/foto/<int:fid>/capa", methods=["POST"])
def virar_capa(fid):
    """A capa e a primeira foto - manda esta para a frente da fila."""
    foto = FotoHomologacao.query.get_or_404(fid)
    h = foto.homologacao
    foto.ordem = 0
    for i, outra in enumerate([f for f in h.fotos if f.id != foto.id], start=1):
        outra.ordem = i
    db.session.commit()
    flash("Capa alterada.", "ok")
    return redirect(_voltar(h))


# ------------------------------------------------------------------ produtos do modulo

@bp.route("/homologacao/<int:hid>/aplicacao", methods=["POST"])
def nova_aplicacao(hid):
    """Liga um produto acabado a um modulo homologado."""
    h = Homologacao.query.get_or_404(hid)
    texto = (request.form.get("modelo") or "").strip()
    if not texto:
        flash("Informe o modelo do produto.", "erro")
        return redirect(_voltar(h))
    ja = {anatel.sem_acento(a.modelo) for a in h.aplicacoes_produtos}
    novos = 0
    for nome in [n.strip() for n in texto.split(",") if n.strip()]:
        if anatel.sem_acento(nome) in ja:
            continue
        ja.add(anatel.sem_acento(nome))
        produto = next((p for p in Produto.query.all()
                        if anatel.sem_acento(p.modelo) == anatel.sem_acento(nome)), None)
        db.session.add(AplicacaoHomologacao(homologacao=h, modelo=nome, produto=produto))
        novos += 1
    db.session.commit()
    flash(f"{novos} produto(s) vinculado(s) a esta homologação." if novos
          else "Esse produto já estava vinculado.", "ok" if novos else "info")
    return redirect(_voltar(h))


@bp.route("/aplicacao/<int:aid>/promover", methods=["POST"])
def promover_aplicacao(aid):
    """Transforma um nome solto de produto em modelo do catalogo.

    A lista de produtos que usam o modulo e texto livre (veio assim da planilha).
    Quando um desses nomes precisa de ficha propria, este botao o cadastra.
    """
    ap = AplicacaoHomologacao.query.get_or_404(aid)
    if ap.produto:
        flash(f"“{ap.modelo}” já está no catálogo.", "info")
        return redirect(_voltar(ap.homologacao))
    produto = Produto(modelo=ap.modelo, natureza="Produto acabado",
                      tipo_equipamento=ap.homologacao.tipo or "")
    db.session.add(produto)
    db.session.flush()
    ap.produto = produto
    db.session.commit()
    flash(f"“{ap.modelo}” cadastrado no catálogo e vinculado.", "ok")
    return redirect(_voltar(ap.homologacao))


@bp.route("/aplicacao/<int:aid>/excluir", methods=["POST"])
def excluir_aplicacao(aid):
    ap = AplicacaoHomologacao.query.get_or_404(aid)
    h = ap.homologacao
    db.session.delete(ap)
    db.session.commit()
    flash("Vínculo removido.", "ok")
    return redirect(_voltar(h))


def _voltar(homologacao):
    """Volta para a tela de onde a acao partiu (produto ou homologacao)."""
    destino = request.form.get("voltar") or request.args.get("voltar")
    if destino and destino.startswith("/"):
        return destino
    return url_for("homologacoes.detalhe", hid=homologacao.id)
