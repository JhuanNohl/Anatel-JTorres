"""Releitura automatica da base publica da ANATEL.

Uma thread discreta acorda de tempo em tempo, pergunta a configuracao se ja
passou do prazo e, se passou, baixa o arquivo e sincroniza. Nada de servico
externo nem tarefa do Windows: o sistema se cuida sozinho enquanto esta aberto.

Se o servidor ficar desligado alem do prazo, a atualizacao acontece pouco depois
de voltar - a verificacao roda tambem na abertura.
"""
import threading
from datetime import datetime

INTERVALO_DA_RONDA = 15 * 60          # de quanto em quanto tempo perguntamos
ESPERA_INICIAL = 60                   # deixa o sistema abrir em paz primeiro
_ja_iniciado = False
_trava = threading.Lock()


def _tentar_atualizar(app):
    """Uma passada: se estiver vencida, le a base. Erro nao derruba a thread."""
    from . import anatel
    from .extensions import db
    from .models import config_anatel

    with app.app_context():
        config = config_anatel()
        if not config.automatico or not config.vencida:
            return False
        config.ultima_tentativa = datetime.now()
        db.session.commit()
        try:
            relatorio = anatel.atualizar(
                db, solicitante=_solicitante(), base_dir=app.config["BASE_DIR"])
        except Exception as erro:                  # rede fora, ANATEL mudou o ZIP
            config = config_anatel()
            config.ultimo_erro = str(erro)[:255]
            db.session.commit()
            app.logger.warning("atualização automática da ANATEL falhou: %s", erro)
            return False
        config = config_anatel()
        config.ultimo_erro = ""
        db.session.commit()
        app.logger.info("base da ANATEL atualizada sozinha: %s homologações",
                        relatorio["homologacoes"])
        return True


def _solicitante():
    from . import anatel
    from .models import Empresa
    empresa = Empresa.query.get(1)
    return (empresa.razao_social if empresa and empresa.razao_social
            else anatel.SOLICITANTE_PADRAO)


def _ronda(app):
    import time
    time.sleep(ESPERA_INICIAL)
    while True:
        try:
            _tentar_atualizar(app)
        except Exception:                          # nunca deixa a thread morrer
            app.logger.exception("erro na ronda da base ANATEL")
        time.sleep(INTERVALO_DA_RONDA)


def iniciar(app):
    """Liga a ronda uma unica vez por processo."""
    global _ja_iniciado
    with _trava:
        if _ja_iniciado:
            return
        _ja_iniciado = True
    thread = threading.Thread(target=_ronda, args=(app,), daemon=True,
                              name="base-anatel")
    thread.start()
    return thread
