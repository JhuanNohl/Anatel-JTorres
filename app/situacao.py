"""Uma so taxonomia de situacao, para as duas telas contarem a mesma coisa.

Homologacoes conta CERTIFICADOS (uma linha por certificado) e Produtos conta
MODELOS (uma linha por modelo). Um certificado cobre varios modelos, entao os
totais nunca sao iguais - mas precisam FECHAR: cada grupo de certificado leva a
um grupo de modelo, e as duas telas mostram os dois numeros lado a lado.

Antes, cada tela classificava por conta propria; qualquer ajuste em uma fazia a
outra divergir sem ninguem perceber. Agora a regra mora aqui.
"""
from collections import Counter

from .anatel import sem_acento

# --------------------------------------------------------- grupos de certificado
# ordem em que aparecem na tela de Homologacoes
GRUPOS_CERTIFICADO = [
    ("emitida", "Emitidas", "ok"),
    ("vencendo", "A vencer", "warn"),
    ("suspensa", "Suspensas", "erro"),
    ("cancelada", "Canceladas", "erro"),
    ("outra", "Outras situações", "neutro"),
]
PESO_CERTIFICADO = {chave: i for i, (chave, _r, _c) in enumerate(GRUPOS_CERTIFICADO, 1)}

# um certificado deste grupo deixa o modelo neste grupo, na tela de Produtos
GRUPO_DE_MODELO = {
    "emitida": "vigentes",
    "vencendo": "vencendo",
    "suspensa": "problema",
    "cancelada": "problema",
    "outra": "problema",
}
# como o grupo se le quando o que se conta e certificado, no singular e no
# plural ("38 certificados: 37 suspensos, 1 cancelado"). O rotulo do cartao
# esta no feminino porque la se conta homologacao.
ADJETIVO_CERTIFICADO = {
    "emitida": ("emitido", "emitidos"),
    "vencendo": ("a vencer", "a vencer"),
    "suspensa": ("suspenso", "suspensos"),
    "cancelada": ("cancelado", "cancelados"),
    "outra": ("em outra situação", "em outra situação"),
}
# o caminho inverso: quais grupos de certificado sustentam cada grupo de modelo.
# "processo" e "sem" nao tem certificado nenhum - e justamente o que os define.
CERTIFICADOS_DO_GRUPO_DE_MODELO = {
    "vigentes": ["emitida"],
    "vencendo": ["vencendo"],
    "problema": ["suspensa", "cancelada", "outra"],
    "processo": [],
    "sem": [],
}


def grupo_do_certificado(homologacao, limite):
    """Em qual dos grupos este certificado cai. `limite` = dias de aviso."""
    texto = sem_acento(homologacao.situacao or "").lower()
    if "suspens" in texto:
        return "suspensa"
    if "cancel" in texto:
        return "cancelada"
    if "emitida" in texto or "concluid" in texto or "vigente" in texto:
        dias = homologacao.dias_para_vencer
        # vencida entra aqui tambem: e o que mais pede acao
        if dias is not None and dias <= limite:
            return "vencendo"
        return "emitida"
    return "outra"


def _chave_de_modelo(nome):
    return sem_acento((nome or "").strip()).upper()


def resumo(limite=None):
    """Quantos certificados e quantos modelos em cada grupo.

    Devolve {grupo: {"certificados": n, "modelos": n}} para os grupos de
    certificado, mais os totais. E o que as duas telas usam para se explicar.
    """
    from .models import Homologacao, config_anatel
    if limite is None:
        limite = config_anatel().dias_de_aviso

    certificados = Counter()
    modelos = {}
    for h in Homologacao.query.all():
        chave = grupo_do_certificado(h, limite)
        certificados[chave] += 1
        alvo = modelos.setdefault(chave, set())
        for vinculo in h.modelos:
            if vinculo.modelo:
                alvo.add(_chave_de_modelo(vinculo.modelo))

    saida = {chave: {"certificados": certificados.get(chave, 0),
                     "modelos": len(modelos.get(chave, ()))}
             for chave, _r, _c in GRUPOS_CERTIFICADO}
    todos = set().union(*modelos.values()) if modelos else set()
    saida["_total"] = {"certificados": sum(certificados.values()),
                       "modelos": len(todos)}
    return saida


def por_grupo_de_modelo(limite=None):
    """O mesmo resumo, visto pelo lado de Produtos.

    {grupo de modelo: {"certificados": n, "modelos": n, "detalhe": [...]}}
    O detalhe abre o grupo em partes (ex.: "sem vigencia" = suspensas +
    canceladas), que e o que faz a conta fechar na tela.
    """
    bruto = resumo(limite)
    rotulos = ADJETIVO_CERTIFICADO
    saida = {}
    for grupo, origens in CERTIFICADOS_DO_GRUPO_DE_MODELO.items():
        certs = sum(bruto[o]["certificados"] for o in origens)
        mods = sum(bruto[o]["modelos"] for o in origens)
        detalhe = [(rotulos[o][0 if bruto[o]["certificados"] == 1 else 1],
                    bruto[o]["certificados"])
                   for o in origens if bruto[o]["certificados"]]
        saida[grupo] = {"certificados": certs, "modelos": mods,
                        "detalhe": detalhe if len(detalhe) > 1 else []}
    saida["_total"] = bruto["_total"]
    return saida
