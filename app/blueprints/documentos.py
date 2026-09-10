"""Geracao, edicao e consulta das declaracoes; manutencao dos templates."""
import re
from datetime import date

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)

from ..docgen import (MARCA_REQUISITOS, contexto, dividir_bilingue, gerar_docx, renderizar)
from ..extensions import db
from ..pdfgen import gerar_pdf
from ..models import (Documento, Empresa, Processo, Signatario, TemplateDocumento,
                      TIPOS_DOCUMENTO)
from ..utils import parse_data, remover_arquivo

bp = Blueprint("documentos", __name__)


def _gerar_arquivos(documento):
    """Gera o PDF (o que vai para a OCD) e o .docx (versao editavel)."""
    documento.arquivo_docx = gerar_docx(documento)
    try:
        documento.arquivo_pdf = gerar_pdf(documento)
    except Exception as exc:            # o .docx ja esta salvo; nao perder o documento
        documento.arquivo_pdf = ""
        current_app.logger.exception("falha ao gerar o PDF")
        flash(f"O .docx foi gerado, mas o PDF falhou: {exc}", "erro")


def _extras_do_form(processo, tipo, form=None):
    """Campos variaveis por tipo de documento (com valor sugerido)."""
    form = form or {}
    if tipo == "similaridade":
        pt = " e ".join([s.diferencas for s in processo.similares if s.diferencas]) or \
             "de um possuir leitor de impressão digital e o outro não"
        en = " and ".join([s.diferencas_en for s in processo.similares if s.diferencas_en]) or \
             "one with a fingerprint reader and the other without"
        return [
            ("diferenca_pt", "Diferença entre os modelos (português)",
             form.get("diferenca_pt") or pt, "texto"),
            ("diferenca_en", "Difference between models (english)",
             form.get("diferenca_en") or en, "texto"),
        ]
    if tipo == "direitos_garantia":
        empresa = Empresa.query.get(1)
        achado = re.findall(r"\d+", (empresa.prazo_garantia if empresa else "") or "")
        return [("meses_garantia", "Prazo de garantia (meses)",
                 form.get("meses_garantia") or (achado[0] if achado else "12"), "curto")]
    if tipo == "outros":
        return [("assunto", "Assunto do documento", form.get("assunto") or "", "texto")]
    return []


def _versoes(processo):
    """Separa a versao vigente de cada tipo de documento das versoes anteriores."""
    por_tipo = {}
    for d in processo.documentos:
        por_tipo.setdefault(d.tipo, []).append(d)
    ordem_tipo = list(TIPOS_DOCUMENTO)
    atuais, anteriores = [], []
    for docs in por_tipo.values():
        docs.sort(key=lambda d: d.versao, reverse=True)
        atuais.append(docs[0])
        anteriores.extend(docs[1:])
    atuais.sort(key=lambda d: ordem_tipo.index(d.tipo) if d.tipo in ordem_tipo else 99)
    anteriores.sort(key=lambda d: (ordem_tipo.index(d.tipo) if d.tipo in ordem_tipo else 99,
                                   -d.versao))
    return atuais, anteriores


@bp.route("/processos/<int:pid>/documentos")
def lista(pid):
    processo = Processo.query.get_or_404(pid)
    atuais, anteriores = _versoes(processo)
    return render_template("documentos/lista.html", p=processo, aba="documentos",
                           tipos=TIPOS_DOCUMENTO, atuais=atuais, anteriores=anteriores)


@bp.route("/processos/<int:pid>/documentos/limpar-versoes", methods=["POST"])
def limpar_versoes(pid):
    """Apaga as versoes anteriores, deixando so a mais recente de cada documento."""
    processo = Processo.query.get_or_404(pid)
    _atuais, anteriores = _versoes(processo)
    for documento in anteriores:
        remover_arquivo(documento.arquivo_docx)
        remover_arquivo(documento.arquivo_pdf)
        db.session.delete(documento)
    db.session.commit()
    if anteriores:
        flash(f"{len(anteriores)} versão(ões) anterior(es) removida(s). Ficou a mais recente "
              "de cada documento.", "ok")
    else:
        flash("Já havia só uma versão de cada documento.", "ok")
    return redirect(url_for("documentos.lista", pid=pid))


@bp.route("/processos/<int:pid>/documentos/gerar/<tipo>", methods=["GET", "POST"])
def gerar(pid, tipo):
    processo = Processo.query.get_or_404(pid)
    if tipo not in TIPOS_DOCUMENTO:
        flash("Tipo de documento desconhecido.", "erro")
        return redirect(url_for("documentos.lista", pid=pid))

    templates = TemplateDocumento.query.filter_by(tipo=tipo, ativo=True).order_by(
        TemplateDocumento.nome).all()
    if not templates:
        flash("Nenhum template cadastrado para este documento. Cadastre em Modelos de documento.",
              "erro")
        return redirect(url_for("documentos.templates"))

    titulo_padrao, destinatario, _ = TIPOS_DOCUMENTO[tipo]

    if tipo == "seguranca_cibernetica":
        from .. import requisitos_ciber
        if requisitos_ciber.criar_para(processo, db):
            db.session.commit()
        faltando = processo.ciber_sem_justificativa
        if faltando:
            flash(f"{len(faltando)} requisito(s) marcado(s) como NA estão sem justificativa. "
                  "A OCD exige justificativa para cada NA — preencha antes de emitir.", "erro")
            return redirect(url_for("processos.ciberseguranca", pid=pid))
        # o formulario oficial (com a tabela C / NA) vem primeiro na escolha
        templates.sort(key=lambda t: MARCA_REQUISITOS not in (t.corpo or ""))

    if request.method == "POST":
        form = request.form
        template = TemplateDocumento.query.get(int(form["template_id"]))
        if (tipo == "seguranca_cibernetica"
                and MARCA_REQUISITOS not in (template.corpo or "")):
            flash("Este modelo não tem a tabela de requisitos C / NA. Escolha o "
                  "“formulário oficial” — é o formato que a OCD exige.", "erro")
            return redirect(url_for("documentos.gerar", pid=pid, tipo=tipo))
        signatario = (Signatario.query.get(int(form["signatario_id"]))
                      if form.get("signatario_id") else processo.signatario)
        cidade = (form.get("cidade") or "").strip()
        data_doc = parse_data(form.get("data_documento")) or date.today()
        extras = {chave: (form.get(chave) or "")
                  for chave, _, _, _ in _extras_do_form(processo, tipo, form)}

        ctx = contexto(processo, signatario=signatario, cidade=cidade, data_doc=data_doc,
                       extras=extras)
        corpo = renderizar(template.corpo, ctx)

        versao = 1 + Documento.query.filter_by(processo_id=pid, tipo=tipo).count()
        documento = Documento(processo=processo, template=template, signatario=signatario,
                              tipo=tipo, titulo=(form.get("titulo") or template.titulo
                                                 or titulo_padrao),
                              corpo=corpo, cidade=cidade, data_documento=data_doc,
                              versao=versao)
        db.session.add(documento)
        db.session.flush()
        _gerar_arquivos(documento)
        db.session.commit()
        flash(f"{documento.titulo} gerada (versão {versao}).", "ok")
        return redirect(url_for("documentos.ver", did=documento.id))

    empresa = Empresa.query.get(1)
    cidade_padrao = (empresa.cidade_assinatura or empresa.cidade) if empresa else ""
    return render_template("documentos/gerar.html", p=processo, tipo=tipo,
                           titulo_padrao=titulo_padrao, destinatario=destinatario,
                           templates=templates, extras=_extras_do_form(processo, tipo),
                           cidade_padrao=cidade_padrao, aba="documentos",
                           signatarios=Signatario.query.filter_by(ativo=True).all())


def _blocos_ciber(documento):
    from .. import requisitos_ciber
    return requisitos_ciber.agrupado(documento.processo.requisitos_ciber)


@bp.route("/documentos/<int:did>")
def ver(did):
    documento = Documento.query.get_or_404(did)
    pt, en = dividir_bilingue(documento.corpo)
    return render_template("documentos/ver.html", d=documento, p=documento.processo,
                           pt=pt, en=en, aba="documentos",
                           blocos_ciber=_blocos_ciber(documento))


@bp.route("/documentos/<int:did>/imprimir")
def imprimir(did):
    documento = Documento.query.get_or_404(did)
    pt, en = dividir_bilingue(documento.corpo)
    return render_template("documentos/imprimir.html", d=documento, p=documento.processo,
                           pt=pt, en=en, blocos_ciber=_blocos_ciber(documento))


@bp.route("/documentos/<int:did>/editar", methods=["GET", "POST"])
def editar(did):
    documento = Documento.query.get_or_404(did)
    if request.method == "POST":
        documento.titulo = (request.form.get("titulo") or documento.titulo).strip()
        documento.corpo = request.form.get("corpo") or ""
        documento.cidade = (request.form.get("cidade") or "").strip()
        documento.data_documento = parse_data(request.form.get("data_documento")) or \
            documento.data_documento
        if request.form.get("signatario_id"):
            documento.signatario_id = int(request.form["signatario_id"])
        remover_arquivo(documento.arquivo_docx)
        remover_arquivo(documento.arquivo_pdf)
        _gerar_arquivos(documento)
        db.session.commit()
        flash("Documento atualizado: PDF e .docx regerados.", "ok")
        return redirect(url_for("documentos.ver", did=did))
    return render_template("documentos/editar.html", d=documento, p=documento.processo,
                           aba="documentos",
                           signatarios=Signatario.query.filter_by(ativo=True).all())


@bp.route("/documentos/<int:did>/arquivos", methods=["POST"])
def refazer_arquivos(did):
    """Refaz o PDF e o .docx a partir do texto que ja esta salvo, sem alterar o texto.

    Serve para quando o logotipo, a assinatura ou o layout mudaram.
    """
    documento = Documento.query.get_or_404(did)
    remover_arquivo(documento.arquivo_docx)
    remover_arquivo(documento.arquivo_pdf)
    _gerar_arquivos(documento)
    db.session.commit()
    flash("PDF e .docx refeitos. O texto do documento não foi alterado.", "ok")
    return redirect(url_for("documentos.ver", did=did))


@bp.route("/documentos/<int:did>/regerar", methods=["POST"])
def regerar(did):
    """Regera o texto a partir do template atual (perde ajustes manuais)."""
    documento = Documento.query.get_or_404(did)
    if not documento.template:
        flash("Este documento não está vinculado a um template.", "erro")
        return redirect(url_for("documentos.ver", did=did))
    extras = {chave: valor for chave, _, valor, _ in
              _extras_do_form(documento.processo, documento.tipo)}
    ctx = contexto(documento.processo, signatario=documento.signatario,
                   cidade=documento.cidade, data_doc=documento.data_documento, extras=extras)
    documento.corpo = renderizar(documento.template.corpo, ctx)
    remover_arquivo(documento.arquivo_docx)
    remover_arquivo(documento.arquivo_pdf)
    _gerar_arquivos(documento)
    db.session.commit()
    flash("Texto regerado a partir do modelo. PDF e .docx atualizados.", "ok")
    return redirect(url_for("documentos.ver", did=did))


@bp.route("/documentos/<int:did>/excluir", methods=["POST"])
def excluir(did):
    documento = Documento.query.get_or_404(did)
    pid = documento.processo_id
    remover_arquivo(documento.arquivo_docx)
    remover_arquivo(documento.arquivo_pdf)
    db.session.delete(documento)
    db.session.commit()
    flash("Documento excluído.", "ok")
    return redirect(url_for("documentos.lista", pid=pid))


# ------------------------------------------------------ modelos de documento

@bp.route("/modelos-documento")
def templates():
    itens = TemplateDocumento.query.order_by(TemplateDocumento.tipo,
                                             TemplateDocumento.nome).all()
    return render_template("documentos/templates.html", itens=itens, tipos=TIPOS_DOCUMENTO)


@bp.route("/modelos-documento/novo", methods=["GET", "POST"])
@bp.route("/modelos-documento/<int:tid>", methods=["GET", "POST"])
def template_form(tid=None):
    reg = TemplateDocumento.query.get_or_404(tid) if tid else None
    if request.method == "POST":
        if not reg:
            reg = TemplateDocumento(tipo=request.form.get("tipo") or "outros", nome="")
            db.session.add(reg)
        reg.tipo = request.form.get("tipo") or reg.tipo
        reg.nome = (request.form.get("nome") or "").strip()
        reg.titulo = (request.form.get("titulo") or "").strip()
        reg.corpo = request.form.get("corpo") or ""
        reg.versao = (request.form.get("versao") or "1.0").strip()
        reg.observacoes = (request.form.get("observacoes") or "").strip()
        reg.ativo = bool(request.form.get("ativo"))
        db.session.commit()
        flash("Modelo salvo.", "ok")
        return redirect(url_for("documentos.templates"))
    return render_template("documentos/template_form.html", reg=reg, tipos=TIPOS_DOCUMENTO)


@bp.route("/modelos-documento/<int:tid>/excluir", methods=["POST"])
def template_excluir(tid):
    reg = TemplateDocumento.query.get_or_404(tid)
    db.session.delete(reg)
    db.session.commit()
    flash("Modelo excluído.", "ok")
    return redirect(url_for("documentos.templates"))
