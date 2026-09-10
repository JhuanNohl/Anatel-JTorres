"""Base de homologacoes ANATEL: consulta, cadastro e controle de vencimento."""
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from .. import situacao as situacao_anatel
from ..anatel import sem_acento
from ..extensions import db
from ..models import Homologacao, HomologacaoModelo, OCD, Produto, config_anatel
from ..utils import parse_bool, parse_data

bp = Blueprint("homologacoes", __name__, url_prefix="/homologacoes")

# A taxonomia mora em app/situacao.py: as duas telas (Homologacoes e Produtos)
# classificam pela MESMA regra, senao os numeros divergem sem ninguem notar.
GRUPOS = situacao_anatel.GRUPOS_CERTIFICADO
PESO_GRUPO = situacao_anatel.PESO_CERTIFICADO


def _grupo(h, limite):
    return situacao_anatel.grupo_do_certificado(h, limite)


def _texto_de_busca(h, rotulo):
    """Tudo o que a linha mostra, para o filtro ao vivo comparar."""
    partes = [h.lista_modelos, h.numero, h.certificado, h.natureza, h.tipo,
              h.ocd.nome if h.ocd else "", h.situacao, rotulo, h.ensaios_anatel,
              h.validade.strftime("%d/%m/%Y %Y") if h.validade else ""]
    if h.dias_para_vencer is not None:
        partes.append(f"{h.dias_para_vencer} dias")
    if h.nao_vai_renovar:
        partes.append("nao renovar " + (h.renovacao_motivo or ""))
    return sem_acento(" ".join(p for p in partes if p)).lower()


@bp.route("/")
def lista():
    q = (request.args.get("q") or "").strip()
    grupo = request.args.get("grupo") or request.args.get("situacao") or ""
    if grupo not in PESO_GRUPO:
        grupo = ""          # link antigo com o texto da ANATEL: mostra tudo
    prazo = request.args.get("prazo") or ""

    consulta = Homologacao.query.outerjoin(HomologacaoModelo)
    if q:
        like = f"%{q}%"
        consulta = consulta.filter(or_(Homologacao.numero.ilike(like),
                                       Homologacao.certificado.ilike(like),
                                       Homologacao.tipo.ilike(like),
                                       Homologacao.aplicacoes.ilike(like),
                                       HomologacaoModelo.modelo.ilike(like)))
    if prazo:
        dias = int(prazo)
        consulta = consulta.filter(Homologacao.validade.isnot(None),
                                   Homologacao.validade <= date.today() + timedelta(days=dias))
    todas = consulta.distinct().all()

    limite = config_anatel().dias_de_aviso
    rotulos = {chave: rotulo for chave, rotulo, _cor in GRUPOS}
    cores = {chave: cor for chave, _rot, cor in GRUPOS}

    contagens = {chave: 0 for chave, _rot, _cor in GRUPOS}
    fichas = []
    for h in todas:
        chave = _grupo(h, limite)
        contagens[chave] += 1
        if grupo and chave != grupo:
            continue
        fichas.append(dict(h=h, chave=chave, rotulo=rotulos[chave], cor=cores[chave],
                           busca=_texto_de_busca(h, rotulos[chave])))

    # dentro de cada grupo, o vencimento mais proximo primeiro
    fichas.sort(key=lambda f: (PESO_GRUPO[f["chave"]],
                               f["h"].validade or date.max,
                               f["h"].numero or ""))

    modelos = {sem_acento(m.modelo).lower()
               for f in fichas for m in f["h"].modelos if m.modelo}
    # o mesmo resumo que a tela de Produtos usa, para as contas fecharem
    resumo = situacao_anatel.resumo(limite)
    from .produtos import _contagens_de_modelos
    modelos_por_grupo = _contagens_de_modelos(limite)
    return render_template("homologacoes/lista.html", fichas=fichas, q=q, grupo=grupo,
                           prazo=prazo, contagens=contagens, grupos=GRUPOS,
                           total=len(todas), modelos=len(modelos), resumo=resumo,
                           modelos_por_grupo=modelos_por_grupo, dias_de_aviso=limite)


@bp.route("/<int:hid>")
def detalhe(hid):
    reg = Homologacao.query.get_or_404(hid)
    return render_template("homologacoes/detalhe.html", h=reg)


@bp.route("/nova", methods=["GET", "POST"])
@bp.route("/<int:hid>/editar", methods=["GET", "POST"])
def form(hid=None):
    reg = Homologacao.query.get_or_404(hid) if hid else None
    if request.method == "POST":
        if not reg:
            reg = Homologacao()
            db.session.add(reg)
        f = request.form
        reg.numero = (f.get("numero") or "").strip()
        reg.certificado = (f.get("certificado") or "").strip()
        reg.validade = parse_data(f.get("validade"))
        reg.situacao = f.get("situacao") or "Homologação Emitida"
        reg.natureza = f.get("natureza") or "Produto acabado"
        reg.tipo = (f.get("tipo") or "").strip()
        # o campo saiu do formulario (virou lista de vinculos); so grava se vier
        if "aplicacoes" in f:
            reg.aplicacoes = (f.get("aplicacoes") or "").strip()
        reg.ocd_id = int(f["ocd_id"]) if f.get("ocd_id") else None
        reg.renovar = parse_bool(f.get("renovar"))
        reg.observacoes = (f.get("observacoes") or "").strip()
        db.session.flush()

        modelos = [m.strip() for m in (f.get("modelos") or "").splitlines() if m.strip()]
        for antigo in list(reg.modelos):
            db.session.delete(antigo)
        db.session.flush()
        for modelo in modelos:
            produto = Produto.query.filter_by(modelo=modelo).first()
            db.session.add(HomologacaoModelo(homologacao=reg, modelo=modelo, produto=produto))
        db.session.commit()
        flash("Homologação salva.", "ok")
        return redirect(url_for("homologacoes.detalhe", hid=reg.id))

    return render_template("homologacoes/form.html", reg=reg,
                           ocds=OCD.query.order_by(OCD.nome).all())


@bp.route("/<int:hid>/aviso", methods=["POST"])
def aviso(hid):
    """Marca que o aviso de renovacao ja foi enviado (equivale a coluna de e-mail da planilha)."""
    reg = Homologacao.query.get_or_404(hid)
    reg.aviso_enviado_em = datetime.now()
    reg.renovar = True
    db.session.commit()
    flash("Aviso de renovação registrado.", "ok")
    return redirect(request.referrer or url_for("homologacoes.lista"))


@bp.route("/<int:hid>/nao-renovar", methods=["POST"])
def nao_renovar(hid):
    """Registra a decisao de NAO renovar, com o motivo.

    O motivo e obrigatorio: e ele que responde, meses depois, por que um produto
    deixou de poder ser vendido. Fica visivel na lista de produtos.
    """
    h = Homologacao.query.get_or_404(hid)
    motivo = (request.form.get("motivo") or "").strip()
    if not motivo:
        flash("Escreva o motivo de não renovar — é o que explica a decisão depois.",
              "erro")
        return redirect(request.referrer or url_for("homologacoes.detalhe", hid=hid))
    h.renovacao_decisao = "nao"
    h.renovacao_motivo = motivo
    h.renovacao_decidida_em = datetime.now()
    h.renovacao_decidida_por = (request.form.get("autor") or "").strip()
    h.renovar = False
    db.session.commit()
    flash(f"Registrado: a homologação {h.numero} não será renovada.", "ok")
    return redirect(request.referrer or url_for("homologacoes.detalhe", hid=hid))


@bp.route("/<int:hid>/reabrir-decisao", methods=["POST"])
def reabrir_decisao(hid):
    """Desfaz a decisao, voltando a oferecer renovar."""
    h = Homologacao.query.get_or_404(hid)
    h.renovacao_decisao = ""
    h.renovacao_motivo = ""
    h.renovacao_decidida_em = None
    h.renovacao_decidida_por = ""
    db.session.commit()
    flash("Decisão desfeita — a renovação volta a ser oferecida.", "ok")
    return redirect(request.referrer or url_for("homologacoes.detalhe", hid=hid))


@bp.route("/<int:hid>/renovar", methods=["POST"])
def renovar(hid):
    """Abre o processo de renovacao desta homologacao, ja preenchido.

    Renovar exige o mesmo dossie de uma certificacao nova (ensaio, declaracoes,
    fotos), entao o caminho e criar um processo - com o que ja se sabe: modelo,
    OCD, numero da homologacao que esta vencendo e o checklist de renovacao.
    """
    from ..blueprints.processos import _criar_checklist
    from ..models import Processo
    from ..utils import proximo_numero_processo
    h = Homologacao.query.get_or_404(hid)

    produto = None
    if h.modelos:
        produto = h.modelos[0].produto or Produto.query.filter_by(
            modelo=h.modelos[0].modelo).first()
    if produto is None:
        flash("Esta homologação não tem um modelo no catálogo — abra o processo à mão.",
              "erro")
        return redirect(url_for("processos.novo"))

    aberto = next((p for p in produto.processos
                   if p.tipo_processo.startswith("Renovação")
                   and p.numero_homologacao == h.numero
                   and p.status not in ("Finalizado", "Cancelado")), None)
    if aberto:
        flash(f"Já existe o processo {aberto.numero} renovando esta homologação.", "info")
        return redirect(url_for("processos.detalhe", pid=aberto.id))

    processo = Processo(
        numero=proximo_numero_processo(db), produto=produto,
        ano=date.today().year, status="Iniciado",
        tipo_processo="Renovação / Manutenção",
        numero_homologacao=h.numero, certificado_numero=h.certificado or "",
        certificado_validade=h.validade, ocd_id=h.ocd_id,
        categoria_anatel=produto.categoria_anatel or "Categoria II",
        observacoes=(f"Renovação da homologação {h.numero}"
                     + (f", que vence em {h.validade.strftime('%d/%m/%Y')}"
                        if h.validade else "") + "."),
    )
    db.session.add(processo)
    db.session.flush()
    _criar_checklist(processo)        # o mesmo checklist de renovacao da tela de processos
    h.renovar = True
    h.processo_id = processo.id
    h.renovacao_decisao = "renovar"
    h.renovacao_decidida_em = datetime.now()
    db.session.commit()
    flash(f"Processo {processo.numero} aberto para renovar a homologação {h.numero}. "
          "Confira os dados e o checklist de renovação.", "ok")
    return redirect(url_for("processos.detalhe", pid=processo.id))


@bp.route("/<int:hid>/excluir", methods=["POST"])
def excluir(hid):
    reg = Homologacao.query.get_or_404(hid)
    db.session.delete(reg)
    db.session.commit()
    flash("Homologação excluída.", "ok")
    return redirect(url_for("homologacoes.lista"))
