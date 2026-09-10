"""Fabrica da aplicacao Flask - Sistema de Certificacao ANATEL (ZKTeco Brasil)."""
from datetime import date
from pathlib import Path

from flask import Flask, send_from_directory
from markupsafe import Markup, escape

from . import models
from . import cores
from .config import Config
from .icones import TODOS as ICONES
from . import versao
from .extensions import db
from .utils import data_br, data_hora_br, moeda, tamanho_humano


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    Path(app.config["BASE_DIR"], "instance").mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    # ---- filtros e variaveis globais dos templates
    app.jinja_env.filters["data"] = data_br
    app.jinja_env.filters["datahora"] = data_hora_br
    app.jinja_env.filters["moeda"] = moeda
    app.jinja_env.filters["tamanho"] = tamanho_humano
    app.jinja_env.filters["nl2br"] = lambda t: Markup(
        escape(t or "").replace("\n", Markup("<br>")))

    @app.context_processor
    def globais():
        return dict(
            STATUS_LISTA=models.status_disponiveis(),
            STATUS_ESTILOS=models.estilos_dos_status(),
            PALETA_CORES=cores.PALETA,
            TIPOS_PROCESSO=models.TIPOS_PROCESSO,
            TIPOS_DOCUMENTO=models.TIPOS_DOCUMENTO,
            CATEGORIAS_ANEXO=models.categorias_de_anexo(),
            CATEGORIAS_ANATEL=models.CATEGORIAS_ANATEL,
            SITUACOES_HOMOLOGACAO=models.SITUACOES_HOMOLOGACAO,
            NATUREZAS_PRODUTO=models.NATUREZAS_PRODUTO,
            STATUS_REQUISITO=models.STATUS_REQUISITO,
            CATEGORIAS_DO_PACOTE=models.CATEGORIAS_DO_PACOTE,
            FRASES_OBRIGATORIAS=models.FRASES_OBRIGATORIAS,
            DEFINICAO_CLASSE_I=models.DEFINICAO_CLASSE_I,
            empresa_atual=models.Empresa.query.get(1),
            hoje=date.today(),
            VERSAO=versao.VERSAO,
            VERSAO_ROTULO=versao.rotulo(),
            **ICONES,
        )

    # ---- arquivos enviados (fotos, anexos, documentos gerados)
    @app.route("/arquivo/<path:relativo>")
    def arquivo(relativo):
        return send_from_directory(app.config["UPLOAD_DIR"], relativo)

    @app.route("/download/<path:relativo>")
    def download(relativo):
        return send_from_directory(app.config["UPLOAD_DIR"], relativo, as_attachment=True)

    # ---- blueprints
    from .blueprints.main import bp as bp_main
    from .blueprints.processos import bp as bp_processos
    from .blueprints.documentos import bp as bp_documentos
    from .blueprints.fotos import bp as bp_fotos
    from .blueprints.anexos import bp as bp_anexos
    from .blueprints.cadastros import bp as bp_cadastros
    from .blueprints.homologacoes import bp as bp_homologacoes
    from .blueprints.produtos import bp as bp_produtos
    from .blueprints.pacote import bp as bp_pacote
    from .blueprints.captura import bp as bp_captura

    for bp in (bp_main, bp_processos, bp_documentos, bp_fotos, bp_anexos,
               bp_cadastros, bp_homologacoes, bp_produtos, bp_pacote,
               bp_captura):
        app.register_blueprint(bp)

    # ---- prepara o banco preservando os dados existentes e carrega o que faltar
    with app.app_context():
        from . import manutencao, seed
        mudancas = manutencao.preparar(app, db)
        for mudanca in mudancas:
            app.logger.info("banco: %s", mudanca)
        if mudancas:
            print("[banco] atualizado sem perda de dados:")
            for mudanca in mudancas:
                print("        -", mudanca)
        seed.executar()

    # ---- releitura automatica da base da ANATEL, se estiver ligada
    # Com o recarregador do Flask (modo depuracao) o processo e criado duas
    # vezes; a thread sobe so no processo que atende de fato.
    import os
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if os.environ.get("ANATEL_SEM_AGENDADOR") != "1":
            from . import agendador
            agendador.iniciar(app)

    return app
