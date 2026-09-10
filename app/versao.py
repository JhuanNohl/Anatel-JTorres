"""Versao do sistema, para controle de qual copia esta rodando onde.

Aparece no alto da tela e na tela "Como funciona". Ao publicar uma versao nova,
mude as duas linhas abaixo - e so o que precisa ser mexido.
"""
VERSAO = "2.13"
DATA_VERSAO = "28/08/2026"
RESUMO = ("ZKTeco do Brasil e apenas solicitante; detentor da tecnologia e "
          "fabricante sao a fabrica, em todos os documentos")


def rotulo():
    return f"v{VERSAO} · {DATA_VERSAO}"
