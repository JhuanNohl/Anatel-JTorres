"""Processos de certificacao: cadastro, status, rastreabilidade, similares, amostras."""
from datetime import date

from flask import (Blueprint, flash, jsonify, redirect, render_template, request,
                   url_for)
from sqlalchemy import or_

from ..extensions import db
from ..models import (Amostra, Fabricante, Homologacao,
                      Laboratorio, OCD, Processo, Produto, ProdutoSimilar, Requisito,
                      Signatario, SITUACOES_CIBER, STATUS_REQUISITO, StatusLog,
                      status_por_nome, Vista)
from ..utils import parse_bool, parse_data, parse_float, proximo_numero_processo

bp = Blueprint("processos", __name__, url_prefix="/processos")


def _combos():
    return dict(
        produtos=Produto.query.order_by(Produto.modelo).all(),
        ocds=OCD.query.filter_by(ativo=True).order_by(OCD.nome).all(),
        laboratorios=Laboratorio.query.filter_by(ativo=True).order_by(Laboratorio.nome).all(),
        signatarios=Signatario.query.filter_by(ativo=True).order_by(Signatario.nome).all(),
        fabricantes=Fabricante.query.filter_by(ativo=True).order_by(Fabricante.nome).all(),
    )


def _criar_checklist(processo):
    """Monta o checklist da OCD a partir do cadastro de itens.

    A lista vem da tela "Checklist da OCD" (menu Padroes), nao mais do codigo.
    Itens que nao se aplicam ao produto ja nascem marcados como nao aplicavel.
    """
    from ..models import itens_do_checklist
    itens = [(i.categoria, i.descricao, i.detalhe, i.obrigatorio, i.chave)
             for i in itens_do_checklist(processo.tipo_processo)]
    produto = processo.produto
    for i, (categoria, descricao, detalhe, obrigatorio, chave) in enumerate(itens):
        status = "Pendente"
        observacao = ""
        if "Segurança Cibernética" in descricao and not processo.requer_ciberseguranca:
            status = "Não aplicável"
            observacao = ("Produto marcado como sem conexão à Internet. Se tiver função de "
                          "equipamento terminal com conexão direta ou indireta à Internet, "
                          "este item volta a ser obrigatório.")
        if ("acessórios" in descricao and produto
                and not produto.acessorios and not produto.fonte_externa):
            status = "Não aplicável"
            observacao = ("Produto cadastrado sem acessórios e sem fonte externa. Se for "
                          "comercializado com fonte, fone, microfone ou receptor, este item "
                          "volta a ser obrigatório.")
        db.session.add(Requisito(processo=processo, categoria=categoria, descricao=descricao,
                                 detalhe=detalhe, obrigatorio=obrigatorio, status=status,
                                 observacao=observacao, ordem=i * 10, chave=chave))


def _aplicar_form(processo, form):
    processo.tipo_processo = form.get("tipo_processo") or "Certificação nova"
    processo.categoria_anatel = form.get("categoria_anatel") or ""
    processo.ocd_id = int(form["ocd_id"]) if form.get("ocd_id") else None
    processo.laboratorio_id = int(form["laboratorio_id"]) if form.get("laboratorio_id") else None
    processo.signatario_id = int(form["signatario_id"]) if form.get("signatario_id") else None
    processo.requer_similaridade = parse_bool(form.get("requer_similaridade"))
    processo.requer_ciberseguranca = parse_bool(form.get("requer_ciberseguranca"))
    processo.data_abertura = parse_data(form.get("data_abertura")) or date.today()
    processo.data_previsao = parse_data(form.get("data_previsao"))
    processo.data_conclusao = parse_data(form.get("data_conclusao"))
    processo.referencia_ocd = (form.get("referencia_ocd") or "").strip()
    processo.proposta_ocd = (form.get("proposta_ocd") or "").strip()
    processo.proposta_laboratorio = (form.get("proposta_laboratorio") or "").strip()
    processo.numero_homologacao = (form.get("numero_homologacao") or "").strip()
    processo.certificado_numero = (form.get("certificado_numero") or "").strip()
    processo.certificado_validade = parse_data(form.get("certificado_validade"))
    processo.relatorio_ensaio = (form.get("relatorio_ensaio") or "").strip()
    processo.responsavel = (form.get("responsavel") or "").strip()
    processo.valor_ocd = parse_float(form.get("valor_ocd"))
    processo.valor_laboratorio = parse_float(form.get("valor_laboratorio"))
    processo.valor_outros = parse_float(form.get("valor_outros"))
    processo.observacoes = (form.get("observacoes") or "").strip()


@bp.route("/")
def lista():
    q = (request.args.get("q") or "").strip()
    status = request.args.get("status") or ""
    ocd_id = request.args.get("ocd_id") or ""
    consulta = Processo.query.join(Produto)
    if q:
        like = f"%{q}%"
        consulta = consulta.filter(or_(Processo.numero.ilike(like),
                                       Produto.modelo.ilike(like),
                                       Produto.nome_comercial.ilike(like),
                                       Processo.referencia_ocd.ilike(like),
                                       Processo.numero_homologacao.ilike(like)))
    if status:
        consulta = consulta.filter(Processo.status == status)
    if ocd_id:
        consulta = consulta.filter(Processo.ocd_id == int(ocd_id))
    itens = consulta.order_by(Processo.numero.desc()).all()
    return render_template("processos/lista.html", itens=itens, q=q, status=status,
                           ocd_id=ocd_id, **_combos())


@bp.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        form = request.form
        produto_id = form.get("produto_id")
        if produto_id == "novo" or not produto_id:
            modelo = (form.get("modelo_novo") or "").strip()
            if not modelo:
                flash("Informe o modelo do equipamento.", "erro")
                return redirect(url_for("processos.novo"))
            produto = Produto.query.filter_by(modelo=modelo).first()
            if not produto:
                produto = Produto(
                    modelo=modelo,
                    nome_comercial=(form.get("nome_comercial_novo") or "").strip(),
                    tipo_equipamento=(form.get("tipo_equipamento_novo") or "").strip(),
                    natureza=form.get("natureza_novo") or "Produto acabado",
                    fabricante_id=int(form["fabricante_novo"]) if form.get("fabricante_novo")
                    else None,
                    conecta_internet=parse_bool(form.get("requer_ciberseguranca")),
                    fonte_externa=parse_bool(form.get("fonte_externa_novo")),
                    classe_i=parse_bool(form.get("classe_i_novo")),
                )
                db.session.add(produto)
                db.session.flush()
        else:
            produto = Produto.query.get_or_404(int(produto_id))

        processo = Processo(numero=proximo_numero_processo(db), produto=produto,
                            ano=date.today().year, status="Iniciado")
        _aplicar_form(processo, form)
        if not processo.categoria_anatel:
            processo.categoria_anatel = produto.categoria_anatel
        if not processo.signatario_id:
            padrao = Signatario.query.filter_by(padrao=True).first()
            processo.signatario_id = padrao.id if padrao else None
        db.session.add(processo)
        db.session.flush()
        _criar_checklist(processo)
        db.session.add(StatusLog(processo=processo, de_status="", para_status="Iniciado",
                                 observacao="Processo criado.",
                                 autor=processo.responsavel or ""))
        db.session.commit()
        flash(f"Processo {processo.numero} criado.", "ok")
        return redirect(url_for("processos.detalhe", pid=processo.id))

    return render_template("processos/form.html", processo=None, **_combos())


@bp.route("/<int:pid>/editar", methods=["GET", "POST"])
def editar(pid):
    processo = Processo.query.get_or_404(pid)
    if request.method == "POST":
        form = request.form
        if form.get("produto_id") and form["produto_id"] != "novo":
            processo.produto_id = int(form["produto_id"])
        _aplicar_form(processo, form)
        db.session.commit()
        flash("Processo atualizado.", "ok")
        return redirect(url_for("processos.detalhe", pid=processo.id))
    return render_template("processos/form.html", processo=processo, **_combos())


@bp.route("/<int:pid>")
def detalhe(pid):
    processo = Processo.query.get_or_404(pid)
    obrigatorias = {v.id for v in Vista.query.filter_by(obrigatoria=True, ativo=True).all()}
    exigidas = obrigatorias - processo.vistas_nao_aplicaveis
    vistas_obrigatorias = len(exigidas)
    vistas_ok = len(exigidas & {f.vista_id for f in processo.fotos if f.vista_id})
    categorias = {}
    for r in processo.requisitos:
        categorias.setdefault(r.categoria, []).append(r)
    return render_template("processos/detalhe.html", p=processo, aba="geral",
                           vistas_obrigatorias=vistas_obrigatorias, vistas_ok=vistas_ok,
                           checklist=categorias)


@bp.route("/<int:pid>/status", methods=["POST"])
def status(pid):
    processo = Processo.query.get_or_404(pid)
    novo_status = request.form.get("status")
    observacao = (request.form.get("observacao") or "").strip()
    situacao = status_por_nome(novo_status)
    if situacao is None or not situacao.ativo:
        flash("Status inválido.", "erro")
        return redirect(url_for("processos.detalhe", pid=pid))
    if situacao.exige_justificativa and not observacao:
        flash(f"Descreva o motivo para registrar o status “{novo_status}”. "
              "Essa justificativa fica no histórico para consultas futuras.", "erro")
        return redirect(url_for("processos.detalhe", pid=pid))
    anterior = processo.status
    processo.status = novo_status
    if situacao.encerra and not processo.data_conclusao:
        processo.data_conclusao = date.today()
    db.session.add(StatusLog(processo=processo, de_status=anterior, para_status=novo_status,
                             observacao=observacao,
                             autor=(request.form.get("autor") or "").strip()))
    db.session.commit()
    flash(f"Status alterado de “{anterior}” para “{novo_status}”.", "ok")
    return redirect(url_for("processos.detalhe", pid=pid))


@bp.route("/<int:pid>/observacao", methods=["POST"])
def observacao(pid):
    """Registra uma anotacao no historico sem mudar o status."""
    processo = Processo.query.get_or_404(pid)
    texto = (request.form.get("observacao") or "").strip()
    if texto:
        db.session.add(StatusLog(processo=processo, de_status=processo.status,
                                 para_status=processo.status, observacao=texto,
                                 autor=(request.form.get("autor") or "").strip()))
        db.session.commit()
        flash("Anotação registrada no histórico.", "ok")
    return redirect(url_for("processos.detalhe", pid=pid))


@bp.route("/<int:pid>/excluir", methods=["POST"])
def excluir(pid):
    processo = Processo.query.get_or_404(pid)
    numero = processo.numero
    for h in processo.homologacoes:
        h.processo_id = None
    db.session.delete(processo)
    db.session.commit()
    flash(f"Processo {numero} excluído. Os arquivos continuam na pasta do processo.", "ok")
    return redirect(url_for("processos.lista"))


# ------------------------------------------------------------ rastreabilidade

@bp.route("/<int:pid>/rastreabilidade", methods=["GET", "POST"])
def rastreabilidade(pid):
    processo = Processo.query.get_or_404(pid)
    if request.method == "POST":
        form = request.form
        for campo in ("serie", "lote", "data_fab", "mac", "outros"):
            setattr(processo, f"rast_{campo}", parse_bool(form.get(f"rast_{campo}")))
            setattr(processo, f"rast_{campo}_valor",
                    (form.get(f"rast_{campo}_valor") or "").strip())
        db.session.commit()
        flash("Dados de rastreabilidade salvos.", "ok")
        return redirect(url_for("processos.rastreabilidade", pid=pid))
    return render_template("processos/rastreabilidade.html", p=processo, aba="rastreabilidade")


# ------------------------------------------------------ seguranca cibernetica

@bp.route("/<int:pid>/ciberseguranca", methods=["GET", "POST"])
def ciberseguranca(pid):
    """Formulário do Ato nº 77/2021: cada requisito como C ou NA + justificativa."""
    from .. import requisitos_ciber
    processo = Processo.query.get_or_404(pid)

    criados = requisitos_ciber.criar_para(processo, db)
    if criados:
        db.session.commit()
        flash(f"Formulário criado com {criados} requisitos, todos marcados como "
              "C (conformidade). Ajuste apenas o que não se aplica.", "ok")

    if request.method == "POST":
        for r in processo.requisitos_ciber:
            situacao = request.form.get(f"situacao_{r.id}")
            if situacao in SITUACOES_CIBER:
                r.situacao = situacao
            r.justificativa = (request.form.get(f"justificativa_{r.id}") or "").strip()
        db.session.commit()
        faltando = processo.ciber_sem_justificativa
        if faltando:
            flash(f"Salvo. Atenção: {len(faltando)} requisito(s) marcado(s) como NA ainda "
                  "sem justificativa — a OCD exige justificativa para cada NA.", "erro")
        else:
            flash("Formulário de segurança cibernética salvo.", "ok")
        return redirect(url_for("processos.ciberseguranca", pid=pid))

    return render_template("processos/ciberseguranca.html", p=processo, aba="ciber",
                           blocos=requisitos_ciber.agrupado(processo.requisitos_ciber),
                           total=len(processo.requisitos_ciber))


@bp.route("/<int:pid>/ciberseguranca/todos-c", methods=["POST"])
def ciberseguranca_todos_c(pid):
    processo = Processo.query.get_or_404(pid)
    for r in processo.requisitos_ciber:
        r.situacao = "C"
        r.justificativa = ""
    db.session.commit()
    flash("Todos os requisitos voltaram para C (conformidade).", "ok")
    return redirect(url_for("processos.ciberseguranca", pid=pid))


# ----------------------------------------------------------------- similares

@bp.route("/<int:pid>/similares", methods=["GET", "POST"])
def similares(pid):
    processo = Processo.query.get_or_404(pid)
    if request.method == "POST":
        modelo = (request.form.get("modelo") or "").strip()
        if modelo:
            db.session.add(ProdutoSimilar(
                processo=processo, modelo=modelo,
                nome_comercial=(request.form.get("nome_comercial") or "").strip(),
                diferencas=(request.form.get("diferencas") or "").strip(),
                diferencas_en=(request.form.get("diferencas_en") or "").strip(),
                observacoes=(request.form.get("observacoes") or "").strip()))
            processo.requer_similaridade = True
            db.session.commit()
            flash(f"Modelo similar {modelo} adicionado.", "ok")
        return redirect(url_for("processos.similares", pid=pid))
    return render_template("processos/similares.html", p=processo, aba="similares")


@bp.route("/<int:pid>/similares/<int:sid>/excluir", methods=["POST"])
def excluir_similar(pid, sid):
    reg = ProdutoSimilar.query.get_or_404(sid)
    db.session.delete(reg)
    db.session.commit()
    flash("Modelo similar removido.", "ok")
    return redirect(url_for("processos.similares", pid=pid))


# ------------------------------------------------------------------ amostras

AMOSTRAS_PADRAO = ["Amostra comercial", "Amostra radiada"]


def _dados_da_amostra(form):
    return dict(
        identificacao=(form.get("identificacao") or "").strip() or "Amostra",
        rastreabilidade=(form.get("rastreabilidade") or "").strip(),
        numero_homologacao=(form.get("numero_homologacao") or "").strip(),
        numero_serie=(form.get("numero_serie") or "").strip(),
        observacoes=(form.get("observacoes") or "").strip(),
    )


@bp.route("/<int:pid>/amostras", methods=["GET", "POST"])
def amostras(pid):
    processo = Processo.query.get_or_404(pid)
    if request.method == "POST":
        db.session.add(Amostra(processo=processo, **_dados_da_amostra(request.form)))
        db.session.commit()
        flash("Amostra cadastrada. Cada amostra gera uma etiqueta.", "ok")
        return redirect(url_for("processos.amostras", pid=pid))
    editando = None
    if request.args.get("editar"):
        editando = Amostra.query.filter_by(id=request.args.get("editar", type=int),
                                           processo_id=pid).first()
    faltando = [nome for nome in AMOSTRAS_PADRAO
                if not any(a.identificacao.strip().lower() == nome.lower()
                           for a in processo.amostras)]
    return render_template("processos/amostras.html", p=processo, aba="amostras",
                           editando=editando, faltando=faltando)


@bp.route("/<int:pid>/amostras/<int:aid>", methods=["POST"])
def editar_amostra(pid, aid):
    """Corrige uma amostra ja cadastrada, sem precisar remover e cadastrar de novo."""
    reg = Amostra.query.filter_by(id=aid, processo_id=pid).first_or_404()
    for campo, valor in _dados_da_amostra(request.form).items():
        setattr(reg, campo, valor)
    db.session.commit()
    flash(f"Amostra “{reg.identificacao}” atualizada.", "ok")
    return redirect(url_for("processos.amostras", pid=pid))


@bp.route("/<int:pid>/numero-homologacao", methods=["POST"])
def numero_homologacao(pid):
    """Grava o numero de homologacao direto da aba de amostras.

    O campo tambem existe em "Editar dados", mas quem vai imprimir o selo esta
    nesta tela - nao faz sentido mandar a pessoa procurar o campo em outro lugar.
    """
    processo = Processo.query.get_or_404(pid)
    numero = (request.form.get("numero_homologacao") or "").strip()
    processo.numero_homologacao = numero
    db.session.commit()
    flash(f"Nº de homologação gravado: {numero}." if numero
          else "Nº de homologação apagado.", "ok")
    return redirect(url_for("processos.amostras", pid=pid))


@bp.route("/<int:pid>/amostras/padrao", methods=["POST"])
def amostras_padrao(pid):
    """Cria de uma vez as amostras que faltam do par comercial + radiada."""
    processo = Processo.query.get_or_404(pid)
    rast = (processo.rast_mac_valor or processo.rast_serie_valor
            or processo.rast_lote_valor or "").strip()
    criadas = []
    for nome in AMOSTRAS_PADRAO:
        if any(a.identificacao.strip().lower() == nome.lower() for a in processo.amostras):
            continue
        db.session.add(Amostra(processo=processo, identificacao=nome, rastreabilidade=rast))
        criadas.append(nome)
    db.session.commit()
    if criadas:
        flash("Cadastrada(s): " + ", ".join(criadas)
              + ". Ajuste a rastreabilidade de cada uma — uma etiqueta por amostra.", "ok")
    else:
        flash("As duas amostras padrão já estão cadastradas.", "info")
    return redirect(url_for("processos.amostras", pid=pid))


@bp.route("/<int:pid>/amostras/<int:aid>/excluir", methods=["POST"])
def excluir_amostra(pid, aid):
    reg = Amostra.query.filter_by(id=aid, processo_id=pid).first_or_404()
    db.session.delete(reg)
    db.session.commit()
    flash("Amostra removida.", "ok")
    return redirect(url_for("processos.amostras", pid=pid))


def _guardar_tamanho(processo, modo):
    """Grava a medida vinda da barra da tela, na folha certa.

    Etiqueta e selo tem medidas SEPARADAS: sao coisas diferentes, com conteudo
    diferente, e quase nunca do mesmo tamanho. As quebras de linha so existem na
    etiqueta - o selo nao tem colunas de rotulo e valor.
    """
    if not request.args.get("aplicar"):
        return
    minimo, maximo = Processo.ETIQUETA_MIN, Processo.ETIQUETA_MAX
    largura = request.args.get("largura", type=int)
    altura = request.args.get("altura", type=int)
    if largura:
        largura = max(minimo[0], min(maximo[0], largura))
        if modo == "selo":
            processo.selo_largura_mm = largura
        else:
            processo.etiqueta_largura_mm = largura
    if altura:
        altura = max(minimo[1], min(maximo[1], altura))
        if modo == "selo":
            processo.selo_altura_mm = altura
        else:
            processo.etiqueta_altura_mm = altura
    if modo != "selo":
        # caixa desmarcada nao viaja no GET; por isso a barra manda "aplicar=1" e
        # a ausencia da caixa passa a significar desmarcada, nao "nao mexeu"
        processo.etiqueta_quebra_rotulo = bool(request.args.get("quebra_rotulo"))
        processo.etiqueta_quebra_valor = bool(request.args.get("quebra_valor"))
    db.session.commit()


@bp.route("/<int:pid>/etiquetas/medida", methods=["POST"])
def etiqueta_medida(pid):
    """Salva a medida sem recarregar a folha.

    A barra aplica o tamanho na hora, enquanto se digita; este endereco so
    guarda o que ficou, para nao ter de redigitar na proxima impressao.
    """
    processo = Processo.query.get_or_404(pid)
    modo = "selo" if request.form.get("alvo") == "selo" else "etiqueta"
    minimo, maximo = Processo.ETIQUETA_MIN, Processo.ETIQUETA_MAX
    largura = request.form.get("largura", type=int)
    altura = request.form.get("altura", type=int)
    if largura:
        largura = max(minimo[0], min(maximo[0], largura))
        setattr(processo, f"{'selo' if modo == 'selo' else 'etiqueta'}_largura_mm", largura)
    if altura:
        altura = max(minimo[1], min(maximo[1], altura))
        setattr(processo, f"{'selo' if modo == 'selo' else 'etiqueta'}_altura_mm", altura)
    if modo == "etiqueta":
        processo.etiqueta_quebra_rotulo = parse_bool(request.form.get("quebra_rotulo"))
        processo.etiqueta_quebra_valor = parse_bool(request.form.get("quebra_valor"))
    db.session.commit()
    largura_final, altura_final = processo.medida_da_folha(modo)
    return jsonify(ok=True, largura=largura_final, altura=altura_final,
                   quebra_rotulo=processo.etiqueta_quebras[0],
                   quebra_valor=processo.etiqueta_quebras[1])


@bp.route("/<int:pid>/etiquetas")
def etiquetas(pid):
    """Etiqueta da amostra para o laboratorio: sem numero de homologacao.

    O numero de homologacao so existe no fim do processo, mas a amostra vai ao
    laboratorio antes disso — por isso a etiqueta e o selo ANATEL sao folhas separadas.
    """
    processo = Processo.query.get_or_404(pid)
    _guardar_tamanho(processo, "etiqueta")
    divergentes = [a for a in processo.amostras if a.rastreabilidade_confere is False]
    largura, altura = processo.etiqueta_mm
    quebra_rotulo, quebra_valor = processo.etiqueta_quebras
    return render_template("processos/etiquetas.html", p=processo, modo="etiqueta",
                           divergentes=divergentes, largura=largura, altura=altura,
                           quebra_rotulo=quebra_rotulo, quebra_valor=quebra_valor)


@bp.route("/<int:pid>/selos")
def selos(pid):
    """Folha do selo ANATEL.

    O selo e do PROCESSO (do modelo homologado), nao de cada amostra: o numero de
    homologacao e um so. A folha imprime varias copias iguais para recortar.
    """
    processo = Processo.query.get_or_404(pid)
    _guardar_tamanho(processo, "selo")
    copias = min(max(request.args.get("copias", 12, type=int) or 12, 1), 60)
    largura, altura = processo.selo_mm
    quebra_rotulo, quebra_valor = processo.etiqueta_quebras
    return render_template("processos/etiquetas.html", p=processo, modo="selo",
                           copias=copias, divergentes=[], largura=largura, altura=altura,
                           quebra_rotulo=quebra_rotulo, quebra_valor=quebra_valor)


# ----------------------------------------------------------------- checklist

@bp.route("/<int:pid>/requisitos/<int:rid>", methods=["POST"])
def requisito(pid, rid):
    reg = Requisito.query.get_or_404(rid)
    novo = request.form.get("status")
    if novo in STATUS_REQUISITO:
        reg.status = novo
    if "observacao" in request.form:
        reg.observacao = (request.form.get("observacao") or "").strip()
    db.session.commit()
    return redirect(url_for("processos.detalhe", pid=pid) + "#checklist")


@bp.route("/<int:pid>/requisitos/novo", methods=["POST"])
def novo_requisito(pid):
    processo = Processo.query.get_or_404(pid)
    descricao = (request.form.get("descricao") or "").strip()
    if descricao:
        ordem = max([r.ordem for r in processo.requisitos] or [0]) + 10
        db.session.add(Requisito(processo=processo,
                                 categoria=(request.form.get("categoria") or "Outros").strip(),
                                 descricao=descricao,
                                 detalhe=(request.form.get("detalhe") or "").strip(),
                                 obrigatorio=parse_bool(request.form.get("obrigatorio")),
                                 ordem=ordem))
        db.session.commit()
        flash("Item adicionado ao checklist.", "ok")
    return redirect(url_for("processos.detalhe", pid=pid) + "#checklist")


@bp.route("/<int:pid>/requisitos/<int:rid>/excluir", methods=["POST"])
def excluir_requisito(pid, rid):
    reg = Requisito.query.get_or_404(rid)
    db.session.delete(reg)
    db.session.commit()
    return redirect(url_for("processos.detalhe", pid=pid) + "#checklist")


# ------------------------------------------------- registrar homologacao final

@bp.route("/<int:pid>/homologar", methods=["POST"])
def homologar(pid):
    """Cria a homologacao na base a partir do resultado do processo."""
    processo = Processo.query.get_or_404(pid)
    numero = (request.form.get("numero") or processo.numero_homologacao or "").strip()
    if not numero:
        flash("Informe o número de homologação.", "erro")
        return redirect(url_for("processos.detalhe", pid=pid))
    homologacao = Homologacao(
        numero=numero,
        certificado=(request.form.get("certificado") or processo.certificado_numero or "").strip(),
        validade=parse_data(request.form.get("validade")) or processo.certificado_validade,
        situacao=request.form.get("situacao") or "Homologação Emitida",
        natureza=processo.produto.natureza if processo.produto else "Produto acabado",
        tipo=processo.produto.tipo_equipamento if processo.produto else "",
        ocd_id=processo.ocd_id,
        processo=processo,
    )
    db.session.add(homologacao)
    db.session.flush()
    from ..models import HomologacaoModelo
    db.session.add(HomologacaoModelo(homologacao=homologacao, produto=processo.produto,
                                     modelo=processo.produto.modelo))
    for s in processo.similares:
        db.session.add(HomologacaoModelo(homologacao=homologacao, modelo=s.modelo))
    processo.numero_homologacao = numero
    if homologacao.certificado:
        processo.certificado_numero = homologacao.certificado
    if homologacao.validade:
        processo.certificado_validade = homologacao.validade
    db.session.commit()
    flash(f"Homologação {numero} registrada na base.", "ok")
    return redirect(url_for("homologacoes.detalhe", hid=homologacao.id))
