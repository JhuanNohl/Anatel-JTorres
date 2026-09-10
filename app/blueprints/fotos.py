"""Fotos do produto organizadas pelas vistas exigidas pela OCD."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Foto, Processo, Vista, VistaProcesso
from ..utils import (dimensoes_imagem, is_imagem, parse_bool, pasta_processo, remover_arquivo,
                     salvar_arquivo, slugify)
from ..vistas_svg import desenho

bp = Blueprint("fotos", __name__)


@bp.route("/processos/<int:pid>/fotos")
def lista(pid):
    processo = Processo.query.get_or_404(pid)
    vistas = Vista.query.filter_by(ativo=True).order_by(Vista.ordem).all()
    por_vista = {}
    for f in processo.fotos:
        por_vista.setdefault(f.vista_id, []).append(f)
    por_grupo = {}
    for vista in vistas:
        por_grupo.setdefault(vista.grupo, []).append(vista)
    grupos = list(por_grupo.items())
    nao_aplicaveis = processo.vistas_nao_aplicaveis
    # uma vista marcada como N/A neste processo deixa de ser cobrada
    obrigatorias = [v for v in vistas if v.obrigatoria and v.id not in nao_aplicaveis]
    faltando = [v for v in obrigatorias if not por_vista.get(v.id)]
    # captura pelo celular: se ha sessao viva, a tela mostra o QR dela
    from .captura import endereco_da_sessao, sessao_do_processo
    from ..qr import svg as qr_svg
    sessao = sessao_do_processo(processo)
    endereco = endereco_da_sessao(sessao) if sessao else ""
    return render_template("fotos/lista.html", p=processo, aba="fotos", grupos=grupos,
                           por_vista=por_vista, faltando=faltando,
                           total_obrigatorias=len(obrigatorias),
                           nao_aplicaveis=nao_aplicaveis, motivos=processo.motivos_vista,
                           extras=por_vista.get(None, []), desenho=desenho,
                           sessao=sessao, endereco_celular=endereco,
                           qr=qr_svg(endereco, 200, "QR para fotografar pelo celular")
                           if endereco else "")


@bp.route("/processos/<int:pid>/fotos/<int:vid>/aplicavel", methods=["POST"])
def aplicavel(pid, vid):
    """Marca / desmarca uma vista como nao aplicavel neste processo."""
    processo = Processo.query.get_or_404(pid)
    vista = Vista.query.get_or_404(vid)
    ajuste = VistaProcesso.query.filter_by(processo_id=pid, vista_id=vid).first()
    if not ajuste:
        ajuste = VistaProcesso(processo=processo, vista=vista)
        db.session.add(ajuste)
    ajuste.nao_aplicavel = parse_bool(request.form.get("nao_aplicavel"))
    ajuste.motivo = (request.form.get("motivo") or "").strip()
    db.session.commit()
    if ajuste.nao_aplicavel:
        flash(f"“{vista.nome}” marcada como não aplicável neste processo.", "ok")
    else:
        flash(f"“{vista.nome}” voltou a ser exigida.", "ok")
    return redirect(url_for("fotos.lista", pid=pid) + f"#vista-{vista.codigo}")


def _pede_json():
    """A tela de fotos envia por fetch para nao recarregar a pagina."""
    return request.headers.get("X-Requested-With") == "fetch"


def _resumo(processo):
    """Quantas vistas obrigatorias ainda faltam (ignorando as marcadas como N/A)."""
    dispensadas = processo.vistas_nao_aplicaveis
    obrigatorias = [v for v in Vista.query.filter_by(obrigatoria=True, ativo=True).all()
                    if v.id not in dispensadas]
    com_foto = {f.vista_id for f in processo.fotos if f.vista_id}
    faltando = [v for v in obrigatorias if v.id not in com_foto]
    return dict(total_obrigatorias=len(obrigatorias), faltando=len(faltando),
                nomes_faltando=[v.nome for v in faltando],
                codigos_faltando=[v.codigo for v in faltando])


def _json_foto(foto):
    return dict(id=foto.id, url=url_for("arquivo", relativo=foto.arquivo),
                nome=foto.nome_original, legenda=foto.legenda,
                largura=foto.largura, altura=foto.altura,
                excluir_url=url_for("fotos.excluir", pid=foto.processo_id, fid=foto.id))


@bp.route("/processos/<int:pid>/fotos/enviar", methods=["POST"])
def enviar(pid):
    processo = Processo.query.get_or_404(pid)
    vista_id = request.form.get("vista_id")
    vista = Vista.query.get(int(vista_id)) if vista_id else None
    arquivos = request.files.getlist("fotos")
    novas, erros = [], []
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename:
            continue
        if not is_imagem(arquivo.filename):
            erros.append(f"“{arquivo.filename}” não é uma imagem. "
                         "Use a aba Anexos para PDFs e documentos.")
            continue
        prefixo = slugify(vista.codigo) if vista else "extra"
        caminho, tamanho = salvar_arquivo(arquivo, pasta_processo(processo, "fotos"), prefixo)
        largura, altura = dimensoes_imagem(caminho)
        foto = Foto(processo=processo, vista=vista, arquivo=caminho,
                    nome_original=arquivo.filename,
                    legenda=(request.form.get("legenda") or "").strip(),
                    largura=largura, altura=altura, tamanho=tamanho)
        db.session.add(foto)
        novas.append(foto)
    if novas:
        db.session.commit()

    if _pede_json():
        return jsonify(ok=bool(novas), fotos=[_json_foto(f) for f in novas],
                       erros=erros, resumo=_resumo(processo))

    for erro in erros:
        flash(erro, "erro")
    if novas:
        flash(f"{len(novas)} foto(s) enviada(s).", "ok")
    return redirect(url_for("fotos.lista", pid=pid) +
                    (f"#vista-{vista.codigo}" if vista else ""))


@bp.route("/processos/<int:pid>/fotos/<int:fid>/legenda", methods=["POST"])
def legenda(pid, fid):
    foto = Foto.query.get_or_404(fid)
    foto.legenda = (request.form.get("legenda") or "").strip()
    db.session.commit()
    return redirect(url_for("fotos.lista", pid=pid))


@bp.route("/processos/<int:pid>/fotos/<int:fid>/excluir", methods=["POST"])
def excluir(pid, fid):
    processo = Processo.query.get_or_404(pid)
    foto = Foto.query.get_or_404(fid)
    codigo = foto.vista.codigo if foto.vista else ""
    remover_arquivo(foto.arquivo)
    db.session.delete(foto)
    db.session.commit()
    if _pede_json():
        return jsonify(ok=True, resumo=_resumo(processo))
    flash("Foto removida.", "ok")
    return redirect(url_for("fotos.lista", pid=pid) + (f"#vista-{codigo}" if codigo else ""))


@bp.route("/processos/<int:pid>/fotos/dossie")
def dossie(pid):
    """Dossie de fotos pronto para imprimir / gerar PDF e enviar a OCD."""
    processo = Processo.query.get_or_404(pid)
    vistas = Vista.query.filter_by(ativo=True).order_by(Vista.ordem).all()
    por_vista = {}
    for f in processo.fotos:
        por_vista.setdefault(f.vista_id, []).append(f)
    itens = [(v, por_vista.get(v.id, [])) for v in vistas if por_vista.get(v.id)]
    return render_template("fotos/dossie.html", p=processo, itens=itens,
                           extras=por_vista.get(None, []))


@bp.route("/vistas/<codigo>/exemplo")
def exemplo(codigo):
    """Desenho SVG da vista (usado no modal de ajuda)."""
    return desenho(codigo), 200, {"Content-Type": "image/svg+xml; charset=utf-8"}
