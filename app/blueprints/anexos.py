"""Anexos do processo: propostas, notas fiscais, boletos, datasheet, manual, laudos."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Anexo, CATEGORIAS_ANEXO, Processo
from ..utils import (parse_data, parse_float, pasta_processo, remover_arquivo, salvar_arquivo,
                     slugify)

bp = Blueprint("anexos", __name__)

# categorias que ganham campos financeiros no formulario
FINANCEIRAS = {"Nota fiscal - OCD", "Nota fiscal - Laboratório",
               "Boleto / comprovante de pagamento", "Proposta comercial - OCD",
               "Proposta comercial - Laboratório"}


@bp.route("/processos/<int:pid>/anexos")
def lista(pid):
    from .pacote import ANEXOS_EXIGIDOS
    processo = Processo.query.get_or_404(pid)
    por_categoria = {}
    for a in processo.anexos:
        por_categoria.setdefault(a.categoria, []).append(a)
    ordenadas = [(c, por_categoria[c]) for c in CATEGORIAS_ANEXO if c in por_categoria]
    total = sum(a.valor or 0 for a in processo.anexos
                if a.categoria.startswith("Nota fiscal"))
    # o que a OCD exige: rotulo, categorias que servem, ja anexado?
    exigidos = [(rotulo, aceitas, bool(set(aceitas) & set(por_categoria)))
                for rotulo, aceitas, _chave in ANEXOS_EXIGIDOS]
    return render_template("anexos/lista.html", p=processo, aba="anexos",
                           grupos=ordenadas, total_notas=total, financeiras=FINANCEIRAS,
                           exigidos=exigidos,
                           categoria_escolhida=request.args.get("categoria", ""))


@bp.route("/processos/<int:pid>/anexos/enviar", methods=["POST"])
def enviar(pid):
    processo = Processo.query.get_or_404(pid)
    categoria = request.form.get("categoria") or "Outros"
    arquivos = request.files.getlist("arquivos")
    enviados = 0
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename:
            continue
        caminho, tamanho = salvar_arquivo(arquivo, pasta_processo(processo, "anexos"),
                                          slugify(categoria, 24))
        db.session.add(Anexo(
            processo=processo, categoria=categoria,
            titulo=(request.form.get("titulo") or "").strip() or arquivo.filename,
            arquivo=caminho, nome_original=arquivo.filename, tamanho=tamanho,
            numero_documento=(request.form.get("numero_documento") or "").strip(),
            valor=parse_float(request.form.get("valor")),
            emissao=parse_data(request.form.get("emissao")),
            vencimento=parse_data(request.form.get("vencimento")),
            observacao=(request.form.get("observacao") or "").strip()))
        enviados += 1
    if enviados:
        db.session.commit()
        flash(f"{enviados} arquivo(s) anexado(s) em “{categoria}”.", "ok")
    else:
        flash("Selecione ao menos um arquivo.", "erro")
    return redirect(url_for("anexos.lista", pid=pid))


@bp.route("/processos/<int:pid>/anexos/<int:aid>/editar", methods=["POST"])
def editar(pid, aid):
    anexo = Anexo.query.get_or_404(aid)
    anexo.categoria = request.form.get("categoria") or anexo.categoria
    anexo.titulo = (request.form.get("titulo") or "").strip()
    anexo.numero_documento = (request.form.get("numero_documento") or "").strip()
    anexo.valor = parse_float(request.form.get("valor"))
    anexo.emissao = parse_data(request.form.get("emissao"))
    anexo.vencimento = parse_data(request.form.get("vencimento"))
    anexo.observacao = (request.form.get("observacao") or "").strip()
    db.session.commit()
    flash("Anexo atualizado.", "ok")
    return redirect(url_for("anexos.lista", pid=pid))


@bp.route("/processos/<int:pid>/anexos/<int:aid>/excluir", methods=["POST"])
def excluir(pid, aid):
    anexo = Anexo.query.get_or_404(aid)
    remover_arquivo(anexo.arquivo)
    db.session.delete(anexo)
    db.session.commit()
    flash("Anexo removido.", "ok")
    return redirect(url_for("anexos.lista", pid=pid))
