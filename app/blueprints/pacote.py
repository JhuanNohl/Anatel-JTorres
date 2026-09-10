"""Pacote de envio para a OCD: um unico ZIP com tudo organizado em pastas.

So e gerado quando nao ha pendencia: fotos obrigatorias, declaracoes exigidas,
anexos obrigatorios e o checklist da OCD precisam estar resolvidos.
"""
import io
import zipfile
from datetime import date
from pathlib import Path

from flask import (Blueprint, abort, flash, redirect, render_template, request, send_file,
                   url_for)

from ..models import Processo, Vista
from ..utils import caminho_absoluto, data_br, slugify

bp = Blueprint("pacote", __name__)

# ---- o que precisa estar pronto ------------------------------------------

# categoria do anexo -> pasta no ZIP
PASTAS_ANEXO = {
    "Cartão CNPJ": "03_Solicitante",
    "Contrato Social": "03_Solicitante",
    "Certificado ISO de Qualidade Fabril": "04_Fabricante",
    "Tradução juramentada do ISO": "04_Fabricante",
    "Avaliação fabril (OCD)": "04_Fabricante",
    "Datasheet": "05_Produto",
    "Manual do usuário": "05_Produto",
    "Layout de etiqueta": "05_Produto",
    "Diagrama de blocos": "05_Produto",
    "Esquemático / PCB": "05_Produto",
    "Lista de materiais (BOM)": "05_Produto",
    "Relatório de ensaio": "06_Ensaios_e_certificados",
    "Certificado de conformidade (CCT)": "06_Ensaios_e_certificados",
    "Homologação ANATEL": "06_Ensaios_e_certificados",
    "Requisitos enviados pela OCD": "08_Outros",
    "E-mail / correspondência": "08_Outros",
    "Outros": "08_Outros",
}

# nao vao para a OCD, a menos que voce peca explicitamente
CATEGORIAS_INTERNAS = {
    "Proposta comercial - OCD", "Proposta comercial - Laboratório",
    "Nota fiscal - OCD", "Nota fiscal - Laboratório",
    "Boleto / comprovante de pagamento",
}

# rotulo -> (categorias que satisfazem, chave da verificacao equivalente no checklist)
# A chave evita que a mesma exigencia apareca duas vezes na lista de pendencias.
# CNPJ, contrato social e ISO sairam daqui: viraram documentos da empresa, guardados uma
# vez so e incluidos no pacote sob demanda.
ANEXOS_EXIGIDOS = [
    ("Manual do usuário ou Datasheet", ["Manual do usuário", "Datasheet"], "anexo_manual"),
]

# categoria do documento da empresa -> pasta no ZIP
PASTAS_DOCUMENTO_EMPRESA = {
    "Cartão CNPJ": "03_Solicitante",
    "Contrato Social": "03_Solicitante",
    "Procuração": "03_Solicitante",
    "Certificado ISO de Qualidade Fabril": "04_Fabricante",
    "Tradução juramentada do ISO": "04_Fabricante",
    "Avaliação fabril (OCD)": "04_Fabricante",
    "Outros": "08_Outros",
}


def documentos_exigidos(processo):
    """Declaracoes que a OCD exige para este processo."""
    exigidos = ["rastreabilidade", "direitos_garantia"]
    if processo.requer_ciberseguranca:
        exigidos.append("seguranca_cibernetica")
    if processo.requer_similaridade:
        exigidos.append("similaridade")
    if "Renova" in (processo.tipo_processo or ""):
        exigidos.append("manutencao")
    return exigidos


def documentos_do_pacote(processo):
    """Ultima versao de cada tipo de documento emitido."""
    por_tipo = {}
    for d in processo.documentos:
        atual = por_tipo.get(d.tipo)
        if not atual or d.versao > atual.versao:
            por_tipo[d.tipo] = d
    return sorted(por_tipo.values(), key=lambda d: d.tipo)


def atualizar_arquivos(processo):
    """Regera os arquivos das declaracoes do pacote a partir do texto ja salvo.

    Garante que o ZIP leve exatamente o que a tela mostra, mesmo que o PDF gravado tenha
    sido feito por uma versao anterior do sistema ou antes de trocar o logotipo.
    """
    from ..extensions import db
    from ..utils import remover_arquivo
    from .documentos import _gerar_arquivos

    for documento in documentos_do_pacote(processo):
        remover_arquivo(documento.arquivo_docx)
        remover_arquivo(documento.arquivo_pdf)
        _gerar_arquivos(documento)
    db.session.commit()


def pendencias(processo):
    """Lista do que falta. Vazia = pode gerar o ZIP.

    Cada item traz o endpoint e os parametros para o template montar o link, em vez de
    construir a URL aqui - assim a funcao tambem serve fora de uma requisicao.
    """
    from ..models import TIPOS_DOCUMENTO
    faltando = []
    ja_listado = set()   # chaves ja cobradas em outro grupo, para nao repetir

    # 1) fotos das vistas obrigatorias (as marcadas como N/A no processo nao contam).
    # Cada vista faltante ja cobre o item de checklist equivalente - nao repetir depois.
    chave_por_grupo = {"Externas": "fotos_externas", "Internas": "fotos_internas"}
    chave_por_vista = {"selo_anatel": "foto_selo", "acessorios": "foto_acessorios"}
    vistas = Vista.query.filter_by(obrigatoria=True, ativo=True).order_by(Vista.ordem).all()
    com_foto = {f.vista_id for f in processo.fotos if f.vista_id}
    dispensadas = processo.vistas_nao_aplicaveis
    for v in vistas:
        if v.id not in com_foto and v.id not in dispensadas:
            ja_listado.add(chave_por_vista.get(v.codigo) or chave_por_grupo.get(v.grupo, ""))
            faltando.append(dict(grupo="Fotos", item=v.nome, endpoint="fotos.lista",
                                 params={"pid": processo.id}, ancora=f"vista-{v.codigo}"))

    # 2) declaracoes exigidas
    for tipo in documentos_exigidos(processo):
        if not processo.tem_documento(tipo):
            ja_listado.add("doc_" + tipo)
            faltando.append(dict(grupo="Declarações", item=TIPOS_DOCUMENTO[tipo][0],
                                 endpoint="documentos.gerar",
                                 params={"pid": processo.id, "tipo": tipo}, ancora=""))

    # 3) anexos obrigatorios
    categorias = {a.categoria for a in processo.anexos}
    for rotulo, aceitas, chave in ANEXOS_EXIGIDOS:
        if not categorias.intersection(aceitas):
            ja_listado.add(chave)
            faltando.append(dict(grupo="Anexos", item=rotulo, endpoint="anexos.lista",
                                 params={"pid": processo.id, "categoria": aceitas[0]},
                                 ancora="enviar"))

    # 3b) formulario de seguranca cibernetica: cada NA precisa de justificativa
    if processo.requer_ciberseguranca:
        sem_justificativa = processo.ciber_sem_justificativa
        if sem_justificativa:
            codigos = ", ".join(r.codigo for r in sem_justificativa[:6])
            faltando.append(dict(
                grupo="Declarações",
                item=f"Segurança cibernética: {len(sem_justificativa)} requisito(s) NA sem "
                     f"justificativa ({codigos})",
                endpoint="processos.ciberseguranca",
                params={"pid": processo.id}, ancora=""))

    # 4) checklist - so a documentacao trava o envio. Proposta comercial, amostras,
    # laudo e financeiro sao acompanhamento do processo, nao vao no pacote.
    for r in processo.requisitos:
        if not r.bloqueia_pacote or r.resolvido or r.chave in ja_listado:
            continue
        rotulo = r.descricao
        if r.avaliacao:
            rotulo += f" — {r.avaliacao['detalhe']}"
        faltando.append(dict(grupo="Checklist", item=rotulo,
                             endpoint="processos.detalhe",
                             params={"pid": processo.id}, ancora="checklist"))

    return faltando


def conteudo(processo, incluir_comercial=False, incluir_empresa=False):
    """Monta a arvore de arquivos do pacote: {pasta: [(nome_no_zip, caminho)]}."""
    from ..models import DocumentoEmpresa
    arvore = {}

    def add(pasta, nome, caminho_relativo):
        caminho = caminho_absoluto(caminho_relativo)
        if caminho.is_file():
            arvore.setdefault(pasta, []).append((nome, caminho))

    # declaracoes: vai o PDF (o .docx e a versao de trabalho, fica no sistema)
    for d in documentos_do_pacote(processo):
        base = f"{slugify(d.titulo, 60)}-v{d.versao}"
        if d.arquivo_pdf:
            add("01_Declaracoes", f"{base}.pdf", d.arquivo_pdf)
        elif d.arquivo_docx:
            add("01_Declaracoes", f"{base}.docx", d.arquivo_docx)

    # fotos, agrupadas pelo grupo da vista e na ordem do roteiro (nao alfabetica)
    def ordem_da_foto(f):
        return (f.vista.ordem if f.vista else 999, f.id)

    grupos = {}
    for f in processo.fotos:
        grupos.setdefault(f.vista.grupo if f.vista else "Complementares", []).append(f)
    em_ordem = sorted(grupos.items(),
                      key=lambda item: min(ordem_da_foto(f) for f in item[1]))
    for i, (grupo, fotos) in enumerate(em_ordem, start=1):
        pasta = f"02_Fotos/{i:02d}_{slugify(grupo, 30)}"
        contador = {}
        for f in sorted(fotos, key=ordem_da_foto):
            codigo = f.vista.codigo if f.vista else "complementar"
            contador[codigo] = contador.get(codigo, 0) + 1
            ordem = f.vista.ordem if f.vista else 999
            add(pasta, f"{ordem:03d}_{codigo}_{contador[codigo]}{Path(f.arquivo).suffix}",
                f.arquivo)

    # anexos
    for a in processo.anexos:
        if a.categoria in CATEGORIAS_INTERNAS:
            if not incluir_comercial:
                continue
            pasta = "07_Comercial_interno"
        else:
            pasta = PASTAS_ANEXO.get(a.categoria, "08_Outros")
        rotulo = slugify(a.categoria, 30)
        base = slugify(Path(a.titulo or a.nome_original or a.categoria).stem, 60)
        nome = base if base.startswith(rotulo) else f"{rotulo}_{base}"
        add(pasta, f"{nome}{Path(a.arquivo).suffix}", a.arquivo)

    # documentos da empresa (CNPJ, contrato social, ISO): so quando a OCD pedir
    if incluir_empresa:
        for d in DocumentoEmpresa.query.all():
            pasta = PASTAS_DOCUMENTO_EMPRESA.get(d.categoria, "08_Outros")
            rotulo = slugify(d.categoria, 30)
            base = slugify(Path(d.titulo or d.nome_original or d.categoria).stem, 60)
            nome = base if base.startswith(rotulo) else f"{rotulo}_{base}"
            add(pasta, f"{nome}{Path(d.arquivo).suffix}", d.arquivo)

    return arvore


def leia_me(processo, arvore):
    """Indice em texto que vai na raiz do ZIP."""
    from ..models import Empresa
    p = processo
    empresa = Empresa.query.get(1)
    linhas = [
        "PACOTE DE CERTIFICACAO ANATEL",
        "=" * 60,
        "",
        f"Processo ............. {p.numero}",
        f"Tipo ................. {p.tipo_processo}",
        f"Modelo(s) ............ {', '.join(p.modelos_declarados)}",
        f"Nome comercial ....... {p.produto.nome_comercial or '-'}",
        f"Tipo de equipamento .. {p.produto.tipo_equipamento or '-'}",
        f"Categoria ANATEL ..... {p.categoria_anatel or '-'}",
        f"Fabricante ........... {p.produto.fabricante.nome if p.produto.fabricante else '-'}",
        f"Pais de origem ....... {p.produto.fabricante.pais if p.produto.fabricante else '-'}",
        "",
        f"Requerente ........... {empresa.razao_social if empresa else '-'}",
        f"CNPJ ................. {empresa.cnpj if empresa else '-'}",
    ]
    linhas += [
        f"OCD .................. {p.ocd.nome if p.ocd else '-'}",
        f"Laboratorio .......... {p.laboratorio.nome if p.laboratorio else '-'}",
        f"Referencia OCD ....... {p.referencia_ocd or '-'}",
        f"Responsavel .......... {p.signatario.nome if p.signatario else '-'}",
        f"Gerado em ............ {data_br(date.today())}",
        "",
        "RASTREABILIDADE DECLARADA",
        "-" * 60,
    ]
    marcados = [(n, v) for n, m, v in p.rastreabilidade_itens if m]
    if marcados:
        for nome, valor in marcados:
            linhas.append(f"  [X] {nome}: {valor}")
    else:
        linhas.append("  (nenhum dado marcado)")

    if p.similares:
        linhas += ["", "MODELOS SIMILARES", "-" * 60]
        for s in p.similares:
            linhas.append(f"  {s.modelo} - {s.diferencas or 'sem diferencas informadas'}")

    linhas += ["", "CONTEUDO DO PACOTE", "-" * 60]
    total = 0
    for pasta in sorted(arvore):
        linhas.append(f"  {pasta}/")
        for nome, _ in sorted(arvore[pasta]):
            linhas.append(f"      {nome}")
            total += 1
    linhas += ["", f"Total de arquivos: {total}", ""]
    return "\n".join(linhas)


# ---- telas ---------------------------------------------------------------

@bp.route("/processos/<int:pid>/pacote")
def ver(pid):
    from ..models import DocumentoEmpresa
    processo = Processo.query.get_or_404(pid)
    faltando = pendencias(processo)
    incluir_comercial = request.args.get("comercial") == "1"
    incluir_empresa = request.args.get("empresa") == "1"
    arvore = conteudo(processo, incluir_comercial, incluir_empresa)
    total = sum(len(v) for v in arvore.values())
    por_grupo = {}
    for f in faltando:
        por_grupo.setdefault(f["grupo"], []).append(f)
    return render_template("processos/pacote.html", p=processo, aba="pacote",
                           pendencias=por_grupo, total_pendencias=len(faltando),
                           arvore=dict(sorted(arvore.items())), total=total,
                           incluir_comercial=incluir_comercial,
                           incluir_empresa=incluir_empresa,
                           total_docs_empresa=DocumentoEmpresa.query.count())


@bp.route("/processos/<int:pid>/pacote.zip")
def baixar(pid):
    processo = Processo.query.get_or_404(pid)
    faltando = pendencias(processo)
    if faltando:
        flash(f"O pacote não pode ser gerado: {len(faltando)} pendência(s) em aberto.", "erro")
        return redirect(url_for("pacote.ver", pid=pid))

    # Refaz PDF e .docx das declaracoes que vao no pacote, com o logotipo, a assinatura e
    # o layout atuais. Sem isso o ZIP poderia levar um arquivo gerado por uma versao antiga
    # do sistema, diferente do que a tela mostra.
    atualizar_arquivos(processo)

    incluir_comercial = request.args.get("comercial") == "1"
    incluir_empresa = request.args.get("empresa") == "1"
    arvore = conteudo(processo, incluir_comercial, incluir_empresa)
    if not arvore:
        abort(404)

    raiz = f"{slugify(processo.numero)}_{slugify(processo.produto.modelo)}"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{raiz}/00_LEIA-ME.txt",
                    leia_me(processo, arvore).encode("utf-8-sig"))
        for pasta, arquivos in arvore.items():
            for nome, caminho in arquivos:
                zf.write(caminho, f"{raiz}/{pasta}/{nome}")
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                     download_name=f"{raiz}_{date.today().isoformat()}.zip")
