"""Geracao do PDF das declaracoes.

O PDF e montado direto pelo sistema (ReportLab), com o mesmo layout do .docx: nao depende
do Word instalado nem de conversor externo. E o arquivo que vai para a OCD.
"""
import os
from pathlib import Path

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from .docgen import blocos, dividir_bilingue, partir_requisitos
from .models import Empresa
from .utils import caminho_absoluto, data_br, data_extenso, pasta_processo, slugify

CINZA = colors.HexColor("#474B4F")
TEXTO = colors.HexColor("#555555")
FRACO = colors.HexColor("#8B9094")
LINHA = colors.HexColor("#D8DCDE")

# fonte padrao e a "de simbolos", usada so nas caixinhas ☒ / ☐
FONTE = "Helvetica"
FONTE_NEGRITO = "Helvetica-Bold"
FONTE_SIMBOLO = None
_FONTES_PRONTAS = False


def _registrar_fontes():
    """Usa Calibri (mesma do .docx) quando disponivel; senao a Helvetica embutida."""
    global FONTE, FONTE_NEGRITO, FONTE_SIMBOLO, _FONTES_PRONTAS
    if _FONTES_PRONTAS:
        return
    _FONTES_PRONTAS = True
    pasta = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"

    for nome, arquivo, arquivo_negrito in [("Calibri", "calibri.ttf", "calibrib.ttf"),
                                           ("Arial", "arial.ttf", "arialbd.ttf")]:
        normal, negrito = pasta / arquivo, pasta / arquivo_negrito
        if normal.is_file() and negrito.is_file():
            try:
                pdfmetrics.registerFont(TTFont(nome, str(normal)))
                pdfmetrics.registerFont(TTFont(nome + "-Bold", str(negrito)))
                FONTE, FONTE_NEGRITO = nome, nome + "-Bold"
                break
            except Exception:
                continue

    # ☒ e ☐ nao existem nas fontes de texto comuns
    for arquivo in ("seguisym.ttf", "arialuni.ttf"):
        caminho = pasta / arquivo
        if caminho.is_file():
            try:
                pdfmetrics.registerFont(TTFont("Simbolos", str(caminho)))
                FONTE_SIMBOLO = "Simbolos"
                break
            except Exception:
                continue


def _escapar(texto):
    return (str(texto or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _marcar_simbolos(texto):
    """Deixa ☒/☐ legiveis: fonte propria quando existe, senao [X] / [  ]."""
    if FONTE_SIMBOLO:
        for simbolo in ("☒", "☐"):
            texto = texto.replace(simbolo, f'<font name="{FONTE_SIMBOLO}">{simbolo}</font>')
        return texto
    return texto.replace("☒", "[X]").replace("☐", "[  ]")


def _para(texto, estilo):
    return Paragraph(_marcar_simbolos(_escapar(texto).replace("\n", "<br/>")), estilo)


def _para_rico(texto, estilo):
    """Paragrafo que aceita <b>/<i>. Quem chama e responsavel por escapar o conteudo."""
    return Paragraph(_marcar_simbolos(texto.replace("\n", "<br/>")), estilo)


TAMANHO_BASE = 10.5
# escalas testadas quando o documento passa de uma pagina; a menor da 8 pt
ESCALAS = (0.95, 0.90, 0.86, 0.82, 0.78, 0.76)


def _estilos(escala=1.0):
    tam_base = TAMANHO_BASE * escala
    normal = ParagraphStyle("corpo", fontName=FONTE, fontSize=tam_base, leading=tam_base * 1.42,
                            textColor=TEXTO, spaceAfter=7 * escala)
    return {
        "normal": normal,
        "justificado": ParagraphStyle("just", parent=normal, alignment=TA_JUSTIFY),
        "titulo": ParagraphStyle("titulo", parent=normal, fontName=FONTE_NEGRITO,
                                 fontSize=13 * escala, leading=17 * escala, textColor=CINZA,
                                 alignment=TA_CENTER, spaceAfter=16 * escala,
                                 spaceBefore=4 * escala),
        "direita": ParagraphStyle("dir", parent=normal, alignment=TA_RIGHT),
        "cabecalho": ParagraphStyle("cab", parent=normal, fontSize=8, leading=10.5,
                                    textColor=TEXTO, alignment=TA_RIGHT, spaceAfter=0),
        "empresa": ParagraphStyle("emp", parent=normal, fontName=FONTE_NEGRITO, fontSize=12,
                                  textColor=CINZA, alignment=TA_LEFT, spaceAfter=0),
        "dados": ParagraphStyle("dados", parent=normal, spaceAfter=1),
        "assina": ParagraphStyle("assina", parent=normal, fontName=FONTE_NEGRITO,
                                 textColor=CINZA, spaceAfter=0),
        "coluna": ParagraphStyle("col", parent=normal, fontSize=9 * escala,
                                 leading=12.6 * escala, spaceAfter=6 * escala),
        "tabela": ParagraphStyle("tab", parent=normal, fontSize=9 * escala,
                                 leading=11.5 * escala, spaceAfter=0),
        "tabela_titulo": ParagraphStyle("tabt", parent=normal, fontName=FONTE_NEGRITO,
                                        fontSize=9 * escala, leading=11.5 * escala,
                                        textColor=CINZA, spaceAfter=0),
    }


def _imagem(caminho_relativo, largura_max, altura_max):
    if not caminho_relativo:
        return None
    caminho = caminho_absoluto(caminho_relativo)
    if not caminho.is_file():
        return None
    try:
        img = Image(str(caminho))
        proporcao = img.imageWidth / float(img.imageHeight or 1)
        largura, altura = largura_max, largura_max / proporcao
        if altura > altura_max:
            altura, largura = altura_max, altura_max * proporcao
        img.drawWidth, img.drawHeight = largura, altura
        return img
    except Exception:
        return None


def _blocos_requisitos(processo, estilos, largura, escala):
    """Tabelas C / NA dos requisitos de seguranca cibernetica."""
    from . import requisitos_ciber
    if not processo.requisitos_ciber:
        return [_para("[o formulário de requisitos ainda não foi preenchido]",
                      estilos["normal"])]

    titulo_secao = ParagraphStyle("secao", parent=estilos["tabela"],
                                  fontName=FONTE_NEGRITO, textColor=CINZA,
                                  spaceBefore=6 * escala, spaceAfter=3 * escala)
    just = ParagraphStyle("just_req", parent=estilos["tabela"],
                          fontSize=8.2 * escala, leading=10.4 * escala,
                          textColor=FRACO, spaceBefore=1.5 * escala)
    situacao_estilo = ParagraphStyle("sit", parent=estilos["tabela"],
                                     fontName=FONTE_NEGRITO, alignment=TA_CENTER,
                                     textColor=CINZA)

    partes = []
    col_situacao = 1.1 * cm
    for titulo, secoes in requisitos_ciber.agrupado(processo.requisitos_ciber):
        if titulo:
            partes.append(_para(titulo, titulo_secao))
        for secao, itens in secoes:
            if secao:
                partes.append(_para(secao, titulo_secao))
            linhas = []
            for r in itens:
                conteudo = [_para_rico(f"<b>{_escapar(r.codigo)}</b> {_escapar(r.texto)}",
                                       estilos["tabela"])]
                if r.situacao == "NA":
                    conteudo.append(_para_rico(f"<b>Justificativa:</b> "
                                               f"<i>{_escapar(r.justificativa or '—')}</i>",
                                               just))
                linhas.append([_para(r.situacao, situacao_estilo), conteudo])
            tabela = Table(linhas, colWidths=[col_situacao, largura - col_situacao],
                           repeatRows=0)
            tabela.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9AA0A4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F7F8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            partes.append(tabela)
    partes.append(Spacer(1, 0.3 * cm * escala))
    return partes


def _cabecalho_rodape(documento, empresa, estilos):
    """Desenha cabecalho (logo + endereco) e rodape em todas as paginas."""
    def desenhar(canvas, doc):
        canvas.saveState()
        topo = A4[1] - 1.4 * cm
        logo = _imagem(empresa.logo_arquivo if empresa else "", 4.2 * cm, 1.5 * cm)
        if logo:
            logo.drawOn(canvas, 2.2 * cm, topo - logo.drawHeight)
        elif empresa:
            canvas.setFont(FONTE_NEGRITO, 12)
            canvas.setFillColor(CINZA)
            canvas.drawString(2.2 * cm, topo - 0.4 * cm, empresa.nome_fantasia
                              or empresa.razao_social)
        if empresa:
            canvas.setFont(FONTE, 8)
            canvas.setFillColor(TEXTO)
            y = topo - 0.25 * cm
            for linha in empresa.cabecalho:
                canvas.drawRightString(A4[0] - 2.2 * cm, y, linha)
                y -= 0.36 * cm

        canvas.setStrokeColor(LINHA)
        canvas.setLineWidth(0.6)
        canvas.line(2.2 * cm, topo - 1.9 * cm, A4[0] - 2.2 * cm, topo - 1.9 * cm)

        canvas.setFont(FONTE, 7)
        canvas.setFillColor(FRACO)
        emitido = documento.criado_em.strftime("%d/%m/%Y %H:%M") if documento.criado_em else ""
        canvas.drawCentredString(
            A4[0] / 2, 1.2 * cm,
            f"{documento.processo.numero}  |  {documento.titulo}  |  v{documento.versao}"
            f"  |  emitido em {emitido}")
        canvas.drawRightString(A4[0] - 2.2 * cm, 1.2 * cm, f"página {doc.page}")
        canvas.restoreState()
    return desenhar


def gerar_pdf(documento):
    """Monta o PDF e devolve o caminho relativo salvo em instance/arquivos.

    Se o documento passar de uma pagina por pouco, tenta de novo um pouco mais compacto:
    e feio o fecho com a assinatura sozinho na folha seguinte.
    """
    _registrar_fontes()
    processo = documento.processo
    destino = pasta_processo(processo, "documentos")
    nome = f"{slugify(processo.numero)}-{slugify(documento.tipo)}-v{documento.versao}.pdf"
    caminho = destino / nome

    if _construir(documento, caminho, escala=1.0) > 1:
        for escala in ESCALAS:
            if _construir(documento, caminho, escala) == 1:
                break
        else:
            # nem na menor escala coube: o texto e longo mesmo, volta ao tamanho normal
            _construir(documento, caminho, escala=1.0)

    raiz = Path(current_app.config["UPLOAD_DIR"])
    return caminho.relative_to(raiz).as_posix()


def _construir(documento, caminho, escala=1.0):
    """Gera o arquivo e devolve quantas paginas sairam."""
    estilos = _estilos(escala)
    processo = documento.processo
    empresa = Empresa.query.get(1)
    sig = documento.signatario or processo.signatario

    doc = BaseDocTemplate(str(caminho), pagesize=A4,
                          leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                          topMargin=3.6 * cm,
                          bottomMargin=max(1.6, 2.0 * escala) * cm,
                          title=documento.titulo,
                          author=(empresa.razao_social if empresa else ""),
                          subject=f"{processo.numero} - {processo.produto.modelo}")
    quadro = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="corpo")
    doc.addPageTemplates([PageTemplate(id="padrao", frames=[quadro],
                                       onPage=_cabecalho_rodape(documento, empresa, estilos))])

    esp = lambda cm_: Spacer(1, cm_ * cm * escala)
    partes = [_para(f"Data: {data_br(documento.data_documento)}", estilos["direita"]),
              esp(0.3),
              _para(documento.titulo.upper(), estilos["titulo"])]

    pt, en = dividir_bilingue(documento.corpo)
    if en:
        coluna_pt = [_para(b, estilos["coluna"]) for b in blocos(pt)]
        coluna_en = [_para(b, estilos["coluna"]) for b in blocos(en)]
        largura = (doc.width - 0.8 * cm) / 2
        tabela = Table([[coluna_pt, coluna_en]], colWidths=[largura, largura + 0.8 * cm])
        tabela.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (0, 0), 0.7 * cm),
                                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        partes.append(tabela)
    else:
        def escrever(texto):
            for bloco in blocos(texto):
                linhas = [l for l in bloco.split("\n") if l.strip()]
                marcador = bloco.lstrip().startswith(("•", "-", "*", "☐", "☒", "·",
                                                      "1)", "2)", "3)"))
                estilo = (estilos["justificado"] if len(linhas) == 1 and not marcador
                          and len(bloco) > 110 else estilos["normal"])
                partes.append(_para(bloco, estilo))

        antes, depois = partir_requisitos(pt)
        escrever(antes)
        if depois is not None:
            partes += _blocos_requisitos(processo, estilos, doc.width, escala)
            escrever(depois)

    # tabela de modelos similares
    if documento.tipo == "similaridade" and processo.similares:
        dados = [[_para(t, estilos["tabela_titulo"]) for t in
                  ("Modelo", "Nome comercial", "Diferenças em relação ao modelo base")]]
        for s in processo.similares:
            dados.append([_para(s.modelo, estilos["tabela"]),
                          _para(s.nome_comercial or "-", estilos["tabela"]),
                          _para(s.diferencas or "-", estilos["tabela"])])
        largura = doc.width
        tabela = Table(dados, colWidths=[largura * .26, largura * .28, largura * .46])
        tabela.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9AA0A4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F5F6")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        partes += [esp(0.2), tabela, esp(0.3)]

    # Fecho do documento: responsavel + local/data + assinatura.
    # Vai tudo em KeepTogether para a assinatura nunca ficar sozinha na pagina seguinte.
    fecho = [esp(0.45)]
    mostrar_responsavel = not (documento.template and not documento.template.bloco_responsavel)
    if sig and mostrar_responsavel:
        for rotulo, valor in [("Nome do responsável", sig.nome), ("Cargo", sig.cargo),
                              ("E-mail", sig.email), ("E-mail", sig.email_alternativo),
                              ("Telefone", sig.telefone)]:
            if valor:
                fecho.append(_para(f"{rotulo}: {valor}", estilos["dados"]))

    fecho.append(esp(0.4))
    local_data = f"{documento.cidade or ''}, {data_extenso(documento.data_documento)}."
    fecho.append(_para(local_data.lstrip(", "), estilos["normal"]))
    fecho.append(esp(0.35))
    fecho.append(_para("Assinatura:", estilos["normal"]))

    assinatura = _imagem(sig.assinatura_arquivo if sig else "",
                         4.5 * cm * escala, 1.8 * cm * escala)
    if assinatura:
        assinatura.hAlign = "LEFT"
        fecho.append(assinatura)
    else:
        fecho.append(esp(0.9))
    fecho.append(_para("_" * 44, estilos["normal"]))
    if sig:
        fecho.append(_para(sig.nome, estilos["assina"]))
    if empresa:
        fecho.append(_para(empresa.razao_social +
                           (f" - CNPJ {empresa.cnpj}" if empresa.cnpj else ""),
                           ParagraphStyle("emp2", parent=estilos["normal"], fontSize=9,
                                          textColor=FRACO)))
    partes.append(KeepTogether(fecho))

    doc.build(partes)
    return doc.page
