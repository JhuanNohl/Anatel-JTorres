"""Captura guiada de fotos pelo celular, uma vista por vez.

Como funciona: na tela de fotos do processo aparece um QR code. Quem está com o
produto na bancada lê o QR com o celular e cai numa tela simples, sem menu e sem
login, que mostra UMA vista por vez - o desenho de exemplo, o que a OCD cobra e
um botão grande de tirar foto. A foto sobe, é conferida na hora e a tela
responde: serve (vai para a próxima) ou não serve e por quê (refaz).

Parar e voltar é natural: a próxima vista é calculada do banco, não guardada no
celular. Fechar a página, trocar de aparelho ou continuar no dia seguinte cai
sempre no mesmo ponto.

Por que a câmera nativa e não a câmera dentro da página: o preview ao vivo
(getUserMedia) só funciona em HTTPS, e o sistema roda em http na rede interna. O
input com capture="environment" abre a câmera do próprio celular, funciona em
http e não exige instalar certificado em aparelho nenhum.
"""
import secrets
from datetime import datetime, timedelta

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)

from .. import vistoria
from ..extensions import db
from ..models import (Foto, Processo, SessaoCaptura, Vista, VistaProcesso,
                      config_vistoria)
from ..utils import (caminho_absoluto, dimensoes_imagem, is_imagem, pasta_processo,
                     remover_arquivo, salvar_arquivo, slugify)
from ..vistas_svg import desenho

bp = Blueprint("captura", __name__)


# ------------------------------------------------------------------ sessao

def abrir_sessao(processo):
    """Abre (ou renova) a sessao do processo. Uma sessao viva por processo."""
    config = config_vistoria()
    viva = (SessaoCaptura.query
            .filter_by(processo_id=processo.id, encerrada=False)
            .order_by(SessaoCaptura.id.desc()).first())
    horas = max(1, config.horas_da_sessao or 12)
    if viva and viva.valida:
        viva.expira_em = datetime.now() + timedelta(hours=horas)
        db.session.commit()
        return viva
    sessao = SessaoCaptura(token=secrets.token_urlsafe(16)[:22],
                           processo=processo,
                           expira_em=datetime.now() + timedelta(hours=horas))
    db.session.add(sessao)
    db.session.commit()
    return sessao


def sessao_do_processo(processo):
    """A sessao viva, se houver - para a tela do computador mostrar o QR."""
    sessao = (SessaoCaptura.query
              .filter_by(processo_id=processo.id, encerrada=False)
              .order_by(SessaoCaptura.id.desc()).first())
    return sessao if sessao and sessao.valida else None


def _sessao(token):
    sessao = SessaoCaptura.query.filter_by(token=token).first()
    if sessao is None:
        abort(404)
    sessao.ultimo_acesso = datetime.now()
    aparelho = (request.headers.get("User-Agent") or "")[:250]
    if aparelho and sessao.aparelho != aparelho:
        sessao.aparelho = aparelho
    db.session.commit()
    return sessao


LOCAIS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def ip_da_maquina():
    """O IP que os outros aparelhos usam para chegar neste servidor."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))      # nao envia nada; so descobre a rota
            return s.getsockname()[0]
    except OSError:
        return ""


def endereco_da_sessao(sessao):
    """URL absoluta para o QR.

    Normalmente basta o endereco que o navegador ja esta usando. Mas se alguem
    abrir o sistema NO PROPRIO servidor (localhost), o QR sairia com "localhost"
    dentro - e o celular nunca chegaria la. Nesse caso trocamos pelo IP da
    maquina na rede.
    """
    endereco = url_for("captura.entrar", token=sessao.token, _external=True)
    servidor = (request.host or "").split(":")[0]
    if servidor in LOCAIS:
        ip = ip_da_maquina()
        if ip:
            endereco = endereco.replace(f"//{servidor}", f"//{ip}", 1)
    return endereco


# ------------------------------------------------------------------ roteiro

def _nao_aplicaveis(processo):
    return processo.vistas_nao_aplicaveis


def _fotos_por_vista(processo):
    por_vista = {}
    for foto in processo.fotos:
        por_vista.setdefault(foto.vista_id, []).append(foto)
    return por_vista


def roteiro(processo):
    """As vistas na ordem em que o celular vai pedir.

    A FILA e so o que a OCD cobra: obrigatorias, nao dispensadas, sem foto. As
    opcionais nao entram na contagem - dizer "vista 1 de 12" quando o pacote so
    exige 9 faz a pessoa achar que falta mais do que falta. Elas aparecem no
    resumo do fim, como convite.
    """
    dispensadas = _nao_aplicaveis(processo)
    feitas = _fotos_por_vista(processo)
    vistas = Vista.query.filter_by(ativo=True).order_by(Vista.ordem).all()
    itens = []
    for vista in vistas:
        if vista.id in dispensadas:
            continue
        itens.append(dict(vista=vista, fotos=feitas.get(vista.id, []),
                          obrigatoria=vista.obrigatoria))
    return dict(
        itens=itens,
        pendentes=[i for i in itens if i["obrigatoria"] and not i["fotos"]],
        opcionais_pendentes=[i for i in itens
                             if not i["obrigatoria"] and not i["fotos"]],
        obrigatorias=[i for i in itens if i["obrigatoria"]],
        faltando=[i for i in itens if i["obrigatoria"] and not i["fotos"]],
    )


def _progresso(processo):
    mapa = roteiro(processo)
    total = len(mapa["obrigatorias"])
    feitas = total - len(mapa["faltando"])
    return dict(total=total, feitas=feitas, faltando=len(mapa["faltando"]),
                porcento=round(feitas * 100 / total) if total else 100)


# ------------------------------------------------------------------ telas

@bp.route("/captura/<token>")
def entrar(token):
    """Porta de entrada do QR: manda para onde parou."""
    sessao = _sessao(token)
    if not sessao.valida:
        return render_template("captura/encerrada.html", s=sessao), 410
    mapa = roteiro(sessao.processo)
    if mapa["pendentes"]:
        return redirect(url_for("captura.vista", token=token,
                                vid=mapa["pendentes"][0]["vista"].id))
    return redirect(url_for("captura.fim", token=token))


@bp.route("/captura/<token>/v/<int:vid>")
def vista(token, vid):
    sessao = _sessao(token)
    if not sessao.valida:
        return render_template("captura/encerrada.html", s=sessao), 410
    alvo = Vista.query.get_or_404(vid)
    mapa = roteiro(sessao.processo)
    fila = [i["vista"].id for i in mapa["pendentes"]]
    fotos = _fotos_por_vista(sessao.processo).get(vid, [])
    return render_template(
        "captura/vista.html", s=sessao, p=sessao.processo, v=alvo, fotos=fotos,
        desenho=desenho, progresso=_progresso(sessao.processo),
        posicao=(fila.index(vid) + 1) if vid in fila else None,
        pendentes=len(fila), mapa=mapa, ultima=None)


@bp.route("/captura/<token>/v/<int:vid>/foto", methods=["POST"])
def enviar(token, vid):
    """Recebe a foto, confere na hora e responde com o veredito."""
    sessao = _sessao(token)
    if not sessao.valida:
        return render_template("captura/encerrada.html", s=sessao), 410
    processo, alvo = sessao.processo, Vista.query.get_or_404(vid)
    arquivo = request.files.get("foto")
    if not arquivo or not arquivo.filename or not is_imagem(arquivo.filename):
        flash("Não recebi nenhuma imagem. Tente novamente.", "erro")
        return redirect(url_for("captura.vista", token=token, vid=vid))

    caminho, tamanho = salvar_arquivo(arquivo, pasta_processo(processo, "fotos"),
                                      slugify(alvo.codigo))
    absoluto = caminho_absoluto(caminho)
    largura, altura = dimensoes_imagem(caminho)
    # confere ANTES de pendurar a foto no processo: a conferencia percorre as
    # fotos ja existentes (para achar repetida) e a nova nao pode entrar na conta
    analise = conferir_foto(processo, alvo, absoluto)
    foto = Foto(processo=processo, vista=alvo, arquivo=caminho,
                nome_original=arquivo.filename, largura=largura, altura=altura,
                tamanho=tamanho, origem="celular")
    aplicar_analise(foto, analise)
    db.session.add(foto)
    sessao.fotos_enviadas = (sessao.fotos_enviadas or 0) + 1
    if not analise["aprovada"]:
        sessao.fotos_recusadas = (sessao.fotos_recusadas or 0) + 1
    db.session.commit()

    if not analise["aprovada"]:
        # A foto reprovada FICA guardada ate a pessoa decidir: se ela apertar
        # "tirar outra", o arquivo e apagado; se insistir em manter, a foto segue
        # marcada para conferencia na tela do computador. Apagar sozinho seria
        # pior - ja aconteceu de a conferencia errar e a foto boa sumir.
        return render_template("captura/veredito.html", s=sessao, p=processo,
                               v=alvo, foto=foto, analise=analise,
                               progresso=_progresso(processo), desenho=desenho)
    return render_template("captura/veredito.html", s=sessao, p=processo, v=alvo,
                           foto=foto, analise=analise, desenho=desenho,
                           progresso=_progresso(processo),
                           proxima=_proxima_depois(processo, alvo))


def _proxima_depois(processo, vista_atual):
    mapa = roteiro(processo)
    for item in mapa["pendentes"]:
        if item["vista"].id != vista_atual.id:
            return item["vista"]
    return None


@bp.route("/captura/<token>/foto/<int:fid>/refazer", methods=["POST"])
def refazer(token, fid):
    """Descarta a foto reprovada e volta para a mesma vista."""
    sessao = _sessao(token)
    foto = Foto.query.get_or_404(fid)
    if foto.processo_id != sessao.processo_id:
        abort(404)
    vid = foto.vista_id
    remover_arquivo(foto.arquivo)
    db.session.delete(foto)
    db.session.commit()
    if vid:
        return redirect(url_for("captura.vista", token=token, vid=vid))
    return redirect(url_for("captura.entrar", token=token))


@bp.route("/captura/<token>/v/<int:vid>/na", methods=["POST"])
def nao_aplicavel(token, vid):
    """Marca a vista como não aplicável a este produto, com o motivo."""
    sessao = _sessao(token)
    if not sessao.valida:
        return render_template("captura/encerrada.html", s=sessao), 410
    motivo = (request.form.get("motivo") or "").strip()
    if not motivo:
        flash("Diga por que esta vista não se aplica a este produto.", "erro")
        return redirect(url_for("captura.vista", token=token, vid=vid))
    ajuste = VistaProcesso.query.filter_by(processo_id=sessao.processo_id,
                                           vista_id=vid).first()
    if not ajuste:
        ajuste = VistaProcesso(processo_id=sessao.processo_id, vista_id=vid)
        db.session.add(ajuste)
    ajuste.nao_aplicavel = True
    ajuste.motivo = motivo
    db.session.commit()
    return redirect(url_for("captura.entrar", token=token))


@bp.route("/captura/<token>/fim")
def fim(token):
    sessao = _sessao(token)
    mapa = roteiro(sessao.processo)
    return render_template("captura/fim.html", s=sessao, p=sessao.processo,
                           mapa=mapa, progresso=_progresso(sessao.processo),
                           extras=[f for f in sessao.processo.fotos if not f.vista_id])


@bp.route("/captura/<token>/extra", methods=["GET", "POST"])
def extra(token):
    """Foto complementar, fora do roteiro (detalhe, acessório, o que aparecer)."""
    sessao = _sessao(token)
    if not sessao.valida:
        return render_template("captura/encerrada.html", s=sessao), 410
    if request.method == "POST":
        arquivo = request.files.get("foto")
        if arquivo and arquivo.filename and is_imagem(arquivo.filename):
            caminho, tamanho = salvar_arquivo(
                arquivo, pasta_processo(sessao.processo, "fotos"), "extra")
            largura, altura = dimensoes_imagem(caminho)
            analise = conferir_foto(sessao.processo, None, caminho_absoluto(caminho))
            foto = Foto(processo=sessao.processo, arquivo=caminho,
                        nome_original=arquivo.filename, largura=largura,
                        altura=altura, tamanho=tamanho, origem="celular",
                        legenda=(request.form.get("legenda") or "").strip())
            aplicar_analise(foto, analise)
            db.session.add(foto)
            sessao.fotos_enviadas = (sessao.fotos_enviadas or 0) + 1
            db.session.commit()
            flash("Foto complementar guardada.", "ok")
        return redirect(url_for("captura.extra", token=token))
    return render_template("captura/extra.html", s=sessao, p=sessao.processo,
                           extras=[f for f in sessao.processo.fotos if not f.vista_id],
                           progresso=_progresso(sessao.processo))


# --------------------------------------------------- lado do computador

@bp.route("/processos/<int:pid>/captura/abrir", methods=["POST"])
def abrir(pid):
    """Gera (ou renova) o QR code para fotografar pelo celular."""
    processo = Processo.query.get_or_404(pid)
    sessao = abrir_sessao(processo)
    flash(f"QR pronto — vale por {sessao.horas_restantes} h. "
          "Aponte a câmera do celular para ele.", "ok")
    return redirect(url_for("fotos.lista", pid=pid) + "#celular")


@bp.route("/processos/<int:pid>/captura/encerrar", methods=["POST"])
def encerrar(pid):
    """Fecha a sessão: o endereço para de funcionar na hora."""
    processo = Processo.query.get_or_404(pid)
    for sessao in SessaoCaptura.query.filter_by(processo_id=processo.id,
                                                encerrada=False).all():
        sessao.encerrada = True
    db.session.commit()
    flash("Sessão de fotos encerrada. O endereço do celular não abre mais.", "ok")
    return redirect(url_for("fotos.lista", pid=pid) + "#celular")


# ------------------------------------------------------------------ conferencia

def impressoes_do_processo(processo, exceto=None):
    """As impressões digitais das fotos já aceitas, para pegar foto repetida."""
    saida = []
    for foto in processo.fotos:
        if exceto is not None and foto.id == exceto:
            continue
        if foto.impressao:
            saida.append(dict(impressao=foto.impressao,
                              vista=foto.vista.nome if foto.vista else "outra foto"))
    return saida


def conferir_foto(processo, vista_alvo, caminho_absoluto_da_foto):
    """Confere a foto: sempre local, e a IA só se estiver ligada."""
    analise = vistoria.analisar(caminho_absoluto_da_foto,
                                impressoes_do_processo(processo))
    config = config_vistoria()
    if vista_alvo is not None and config.ia_ligada and config.ia_disponivel:
        resultado = vistoria.verificar_com_ia(
            caminho_absoluto_da_foto, vista_alvo, config.chave_efetiva,
            config.ia_modelo)
        vistoria.juntar_ia(analise, resultado, reprova=config.ia_reprova)
        if resultado.get("indisponivel"):
            current_app.logger.warning("vistoria por IA indisponível: %s",
                                       resultado.get("motivo"))
    return analise


def aplicar_analise(foto, analise):
    foto.aprovada = analise["aprovada"]
    foto.veredito = vistoria.resumir(analise)[:250]
    foto.analise_json = vistoria.para_json(analise)
    foto.impressao = (analise.get("medidas") or {}).get("impressao", "")
    foto.conferida_em = datetime.now()
