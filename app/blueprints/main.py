"""Painel, busca global e configuracoes (empresa e signatarios)."""
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from ..extensions import db
from ..models import (Anexo, CATEGORIAS_DOCUMENTO_EMPRESA, Documento, DocumentoEmpresa, Empresa,
                      Foto, Homologacao, HomologacaoModelo, Laboratorio, OCD, Processo, Produto,
                      Signatario, status_disponiveis, Vista)
from ..utils import (is_imagem, parse_bool, parse_data, pasta_upload, remover_arquivo,
                     salvar_arquivo, slugify)

bp = Blueprint("main", __name__)


@bp.route("/")
def painel():
    situacoes = status_disponiveis()
    contagens = [(s, Processo.query.filter_by(status=s.nome).count()) for s in situacoes]
    recentes = (Processo.query.order_by(Processo.atualizado_em.desc()).limit(8).all())
    em_aberto = [s.nome for s in situacoes if not s.encerra]
    abertos = (Processo.query
               .filter(Processo.status.in_(em_aberto))
               .order_by(Processo.data_abertura).all())

    limite = date.today() + timedelta(days=180)
    vencendo = (Homologacao.query
                .filter(Homologacao.validade.isnot(None), Homologacao.validade <= limite)
                .order_by(Homologacao.validade).all())

    obrigatorias = {v.id for v in Vista.query.filter_by(obrigatoria=True, ativo=True).all()}
    pendencias = []
    for p in abertos:
        vistas_ok = {f.vista_id for f in p.fotos if f.vista_id}
        exigidas = obrigatorias - p.vistas_nao_aplicaveis
        faltam_fotos = len(exigidas - vistas_ok)
        faltam_docs = [t for t in ("rastreabilidade", "direitos_garantia")
                       if not p.tem_documento(t)]
        if p.requer_ciberseguranca and not p.tem_documento("seguranca_cibernetica"):
            faltam_docs.append("seguranca_cibernetica")
        if p.requer_similaridade and not p.tem_documento("similaridade"):
            faltam_docs.append("similaridade")
        if faltam_fotos or faltam_docs:
            pendencias.append(dict(processo=p, fotos=faltam_fotos, docs=faltam_docs))

    ano = date.today().year
    custo_ano = sum(p.custo_total for p in Processo.query.filter_by(ano=ano).all())

    return render_template("painel.html", contagens=contagens, recentes=recentes,
                           vencendo=vencendo, pendencias=pendencias, custo_ano=custo_ano,
                           total_homologacoes=Homologacao.query.count(),
                           total_produtos=Produto.query.count(),
                           total_documentos=Documento.query.count(),
                           total_anexos=Anexo.query.count(),
                           total_fotos=Foto.query.count())


@bp.route("/busca")
def busca():
    termo = (request.args.get("q") or "").strip()
    resultado = dict(processos=[], produtos=[], homologacoes=[], anexos=[], documentos=[])
    if termo:
        like = f"%{termo}%"
        resultado["processos"] = (Processo.query.join(Produto)
                                 .filter(or_(Processo.numero.ilike(like),
                                             Produto.modelo.ilike(like),
                                             Produto.nome_comercial.ilike(like),
                                             Processo.numero_homologacao.ilike(like),
                                             Processo.certificado_numero.ilike(like),
                                             Processo.referencia_ocd.ilike(like)))
                                 .order_by(Processo.numero.desc()).limit(50).all())
        resultado["produtos"] = (Produto.query
                                 .filter(or_(Produto.modelo.ilike(like),
                                             Produto.nome_comercial.ilike(like),
                                             Produto.tipo_equipamento.ilike(like),
                                             Produto.familia.ilike(like)))
                                 .order_by(Produto.modelo).limit(50).all())
        resultado["homologacoes"] = (Homologacao.query
                                     .outerjoin(HomologacaoModelo)
                                     .filter(or_(Homologacao.numero.ilike(like),
                                                 Homologacao.certificado.ilike(like),
                                                 Homologacao.tipo.ilike(like),
                                                 Homologacao.aplicacoes.ilike(like),
                                                 HomologacaoModelo.modelo.ilike(like)))
                                     .distinct().limit(50).all())
        resultado["anexos"] = (Anexo.query
                               .filter(or_(Anexo.titulo.ilike(like),
                                           Anexo.nome_original.ilike(like),
                                           Anexo.numero_documento.ilike(like),
                                           Anexo.categoria.ilike(like)))
                               .order_by(Anexo.criado_em.desc()).limit(50).all())
        resultado["documentos"] = (Documento.query
                                   .filter(or_(Documento.titulo.ilike(like),
                                               Documento.corpo.ilike(like)))
                                   .order_by(Documento.criado_em.desc()).limit(50).all())
    total = sum(len(v) for v in resultado.values())
    return render_template("busca.html", termo=termo, resultados=resultado, total=total)


# ------------------------------------------------------------------ empresa

CAMPOS_EMPRESA = ["razao_social", "nome_fantasia", "cnpj", "inscricao_estadual", "endereco",
                  "bairro", "cidade", "uf", "cep", "pais", "telefone", "email", "site", "sac",
                  "prazo_garantia", "cidade_assinatura", "observacoes"]


def _empresa_atual():
    reg = Empresa.query.get(1)
    if not reg:
        reg = Empresa(id=1, razao_social="")
        db.session.add(reg)
        db.session.commit()
    return reg


@bp.route("/configuracoes/empresa", methods=["GET", "POST"])
def empresa():
    reg = _empresa_atual()
    if request.method == "POST":
        for campo in CAMPOS_EMPRESA:
            setattr(reg, campo, (request.form.get(campo) or "").strip())
        db.session.commit()
        flash("Dados da empresa atualizados.", "ok")
        return redirect(url_for("main.empresa"))
    documentos = {}
    for d in DocumentoEmpresa.query.order_by(DocumentoEmpresa.criado_em.desc()).all():
        documentos.setdefault(d.categoria, []).append(d)
    return render_template("empresa.html", reg=reg,
                           categorias_doc=CATEGORIAS_DOCUMENTO_EMPRESA,
                           documentos=documentos,
                           total_documentos=sum(len(v) for v in documentos.values()))


# imagens da identidade visual: campo no banco, prefixo do arquivo e textos das mensagens
IMAGENS_EMPRESA = {
    "logotipo": ("logo_arquivo", "logo", "Logotipo",
                 "Ele já entra no cabeçalho das próximas declarações.",
                 "Os documentos voltam a mostrar o nome da empresa."),
    "selo": ("selo_anatel_arquivo", "selo-anatel", "Selo ANATEL",
             "Ele já entra na folha de selos das amostras.",
             "A folha de selos volta a sair sem a imagem do selo."),
}


@bp.route("/configuracoes/empresa/imagem/<qual>", methods=["POST"])
def empresa_imagem(qual):
    """Envio em formulario proprio: a imagem sobe assim que e escolhida."""
    if qual not in IMAGENS_EMPRESA:
        abort(404)
    campo, prefixo, rotulo, texto_ok, _ = IMAGENS_EMPRESA[qual]
    reg = _empresa_atual()
    imagem = request.files.get("imagem")
    if not imagem or not imagem.filename:
        flash("Selecione uma imagem.", "erro")
    elif not is_imagem(imagem.filename):
        flash(f"“{imagem.filename}” não é uma imagem. Use PNG, JPG ou WEBP.", "erro")
    else:
        remover_arquivo(getattr(reg, campo))
        caminho, _ = salvar_arquivo(imagem, pasta_upload("identidade"), prefixo)
        setattr(reg, campo, caminho)
        db.session.commit()
        flash(f"{rotulo} atualizado. {texto_ok}", "ok")
    return redirect(url_for("main.empresa"))


@bp.route("/configuracoes/empresa/imagem/<qual>/remover", methods=["POST"])
def empresa_imagem_remover(qual):
    if qual not in IMAGENS_EMPRESA:
        abort(404)
    campo, _prefixo, rotulo, _texto_ok, texto_removido = IMAGENS_EMPRESA[qual]
    reg = _empresa_atual()
    remover_arquivo(getattr(reg, campo))
    setattr(reg, campo, "")
    db.session.commit()
    flash(f"{rotulo} removido. {texto_removido}", "ok")
    return redirect(url_for("main.empresa"))


# --------------------------------------------------------------- signatarios

@bp.route("/configuracoes/empresa/documentos", methods=["POST"])
def empresa_documento():
    """Documentos que valem para todos os processos: CNPJ, contrato social, ISO."""
    arquivos = request.files.getlist("arquivos")
    categoria = request.form.get("categoria") or "Outros"
    enviados = 0
    for arquivo in arquivos:
        if not arquivo or not arquivo.filename:
            continue
        caminho, tamanho = salvar_arquivo(arquivo, pasta_upload("empresa"),
                                          slugify(categoria, 24))
        db.session.add(DocumentoEmpresa(
            categoria=categoria,
            titulo=(request.form.get("titulo") or "").strip() or arquivo.filename,
            arquivo=caminho, nome_original=arquivo.filename, tamanho=tamanho,
            numero=(request.form.get("numero") or "").strip(),
            emissao=parse_data(request.form.get("emissao")),
            validade=parse_data(request.form.get("validade")),
            observacao=(request.form.get("observacao") or "").strip()))
        enviados += 1
    if enviados:
        db.session.commit()
        flash(f"{enviados} documento(s) guardado(s) em “{categoria}”.", "ok")
    else:
        flash("Selecione ao menos um arquivo.", "erro")
    return redirect(url_for("main.empresa") + "#documentos")


@bp.route("/configuracoes/empresa/documentos/<int:did>/excluir", methods=["POST"])
def empresa_documento_excluir(did):
    reg = DocumentoEmpresa.query.get_or_404(did)
    remover_arquivo(reg.arquivo)
    db.session.delete(reg)
    db.session.commit()
    flash("Documento removido.", "ok")
    return redirect(url_for("main.empresa") + "#documentos")


@bp.route("/configuracoes/signatarios", methods=["GET", "POST"])
def signatarios():
    if request.method == "POST":
        sid = request.form.get("id")
        reg = Signatario.query.get(int(sid)) if sid else Signatario(nome="")
        reg.nome = (request.form.get("nome") or "").strip()
        reg.cargo = (request.form.get("cargo") or "").strip()
        reg.cpf = (request.form.get("cpf") or "").strip()
        reg.email = (request.form.get("email") or "").strip()
        reg.email_alternativo = (request.form.get("email_alternativo") or "").strip()
        reg.telefone = (request.form.get("telefone") or "").strip()
        reg.padrao = parse_bool(request.form.get("padrao"))
        reg.ativo = parse_bool(request.form.get("ativo"))
        assinatura = request.files.get("assinatura")
        if assinatura and assinatura.filename:
            caminho, _ = salvar_arquivo(assinatura, pasta_upload("identidade"), "assinatura")
            reg.assinatura_arquivo = caminho
        if reg.padrao:
            for outro in Signatario.query.filter(Signatario.id != reg.id).all():
                outro.padrao = False
        if not sid:
            db.session.add(reg)
        db.session.commit()
        flash("Signatário salvo.", "ok")
        return redirect(url_for("main.signatarios"))

    editar = request.args.get("editar")
    return render_template("signatarios.html",
                           lista=Signatario.query.order_by(Signatario.nome).all(),
                           editar=Signatario.query.get(int(editar)) if editar else None)


@bp.route("/configuracoes/signatarios/<int:sid>/assinatura/remover", methods=["POST"])
def remover_assinatura(sid):
    reg = Signatario.query.get_or_404(sid)
    remover_arquivo(reg.assinatura_arquivo)
    reg.assinatura_arquivo = ""
    db.session.commit()
    flash("Imagem de assinatura removida. Os documentos ficam só com a linha e o nome.", "ok")
    return redirect(url_for("main.signatarios"))


@bp.route("/configuracoes/signatarios/<int:sid>/excluir", methods=["POST"])
def excluir_signatario(sid):
    reg = Signatario.query.get_or_404(sid)
    db.session.delete(reg)
    db.session.commit()
    flash("Signatário removido.", "ok")
    return redirect(url_for("main.signatarios"))


@bp.route("/configuracoes/vistoria", methods=["GET", "POST"])
def vistoria_config():
    """Como a foto e conferida quando chega do celular."""
    from ..models import SessaoCaptura, config_vistoria
    from ..utils import parse_bool
    config = config_vistoria()
    if request.method == "POST":
        config.horas_da_sessao = max(1, min(72, int(request.form.get("horas") or 12)))
        config.ia_ligada = parse_bool(request.form.get("ia_ligada"))
        config.ia_reprova = parse_bool(request.form.get("ia_reprova"))
        config.ia_modelo = (request.form.get("ia_modelo") or "claude-opus-5").strip()
        chave = (request.form.get("ia_chave") or "").strip()
        if chave and not chave.startswith("•"):        # o campo mostra mascarado
            config.ia_chave = chave
        if request.form.get("apagar_chave"):
            config.ia_chave = ""
        if config.ia_ligada and not config.ia_disponivel:
            config.ia_ligada = False
            flash("Sem chave de API não dá para ligar a verificação por IA. "
                  "Informe a chave e ligue de novo.", "erro")
        else:
            flash("Configuração da vistoria salva.", "ok")
        db.session.commit()
        return redirect(url_for("main.vistoria_config"))

    from .. import vistoria as regras
    sessoes = (SessaoCaptura.query.order_by(SessaoCaptura.id.desc()).limit(8).all())
    return render_template("vistoria.html", config=config, sessoes=sessoes,
                           limiares=dict(
                               lado=regras.LADO_MINIMO, brilho=regras.BRILHO_ESCURO,
                               nitidez=regras.NITIDEZ_MINIMA,
                               contraste=regras.CONTRASTE_GRAVE))


@bp.route("/configuracoes/backup", methods=["GET", "POST"])
def backup():
    from flask import current_app
    from .. import manutencao
    if request.method == "POST":
        copia = manutencao.fazer_backup(current_app, "manual")
        if copia:
            flash(f"Cópia de segurança criada: {copia.name}", "ok")
        else:
            flash("O banco ainda não existe — nada para copiar.", "erro")
        return redirect(url_for("main.backup"))

    banco = manutencao.caminho_banco(current_app)
    return render_template(
        "backup.html",
        copias=manutencao.listar_backups(current_app),
        banco=banco,
        tamanho_banco=banco.stat().st_size if banco.is_file() else 0,
        pasta_backup=current_app.config["BACKUP_DIR"],
        pasta_arquivos=current_app.config["UPLOAD_DIR"],
        contagens=dict(processos=Processo.query.count(),
                       documentos=Documento.query.count(),
                       fotos=Foto.query.count(),
                       anexos=Anexo.query.count(),
                       homologacoes=Homologacao.query.count(),
                       produtos=Produto.query.count()))


@bp.route("/ajuda")
def ajuda():
    return render_template("ajuda.html",
                           vistas=Vista.query.order_by(Vista.ordem).all(),
                           ocds=OCD.query.count(), labs=Laboratorio.query.count())
