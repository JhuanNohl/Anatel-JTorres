"""Verificacao automatica dos itens do checklist.

Cada item do checklist pode ter uma "chave". Quando tem, o sistema olha o proprio
processo (anexos, documentos, fotos, amostras) e responde sozinho se aquilo ja foi
atendido - em vez de exigir que voce marque de novo o que ja fez.

Quem nao tem chave continua sendo marcado a mao (ex.: "amostras enviadas ao laboratorio",
que o sistema nao tem como saber).
"""


def _anexos(processo, *categorias):
    return [a for a in processo.anexos if a.categoria in categorias]


def _documentos(processo, tipo):
    return [d for d in processo.documentos if d.tipo == tipo]


def _fotos_da_vista(processo, codigo):
    return [f for f in processo.fotos if f.vista and f.vista.codigo == codigo]


def _grupo_de_vistas(processo, grupo):
    """(faltando, total) das vistas obrigatorias de um grupo, ignorando as marcadas N/A."""
    from .models import Vista
    dispensadas = processo.vistas_nao_aplicaveis
    vistas = [v for v in Vista.query.filter_by(grupo=grupo, ativo=True, obrigatoria=True).all()
              if v.id not in dispensadas]
    com_foto = {f.vista_id for f in processo.fotos if f.vista_id}
    faltando = [v for v in vistas if v.id not in com_foto]
    return faltando, vistas


# ----------------------------------------------------------- verificadores

def _por_anexo(rotulo, *categorias):
    def verificar(processo):
        achados = _anexos(processo, *categorias)
        if achados:
            nomes = ", ".join(a.titulo or a.nome_original for a in achados[:2])
            extra = f" (+{len(achados) - 2})" if len(achados) > 2 else ""
            return True, f"{rotulo} anexado: {nomes}{extra}"
        return False, f"nenhum anexo na categoria {rotulo}"
    return verificar


def _por_documento(tipo, rotulo):
    def verificar(processo):
        achados = _documentos(processo, tipo)
        if achados:
            ultimo = max(achados, key=lambda d: d.versao)
            return True, f"{rotulo} emitida (versão {ultimo.versao})"
        return False, f"{rotulo} ainda não emitida"
    return verificar


def _por_grupo_de_fotos(grupo):
    def verificar(processo):
        faltando, vistas = _grupo_de_vistas(processo, grupo)
        total = len(vistas)
        if not total:
            return False, f"nenhuma vista obrigatória no grupo {grupo}"
        if not faltando:
            return True, f"{total} de {total} vistas de {grupo.lower()} com foto"
        return False, (f"faltam {len(faltando)} de {total}: " +
                       ", ".join(v.nome for v in faltando))
    return verificar


def _por_vista(codigo, rotulo):
    def verificar(processo):
        from .models import Vista
        vista = Vista.query.filter_by(codigo=codigo).first()
        if vista and vista.id in processo.vistas_nao_aplicaveis:
            return True, f"{rotulo}: marcada como não aplicável nas fotos"
        fotos = _fotos_da_vista(processo, codigo)
        if fotos:
            return True, f"{len(fotos)} foto(s) em {rotulo}"
        return False, f"sem foto em {rotulo}"
    return verificar


def _duas_amostras(processo):
    total = len(processo.amostras)
    if total >= 2:
        return True, f"{total} amostras cadastradas"
    if total == 1:
        return False, "só 1 amostra cadastrada (o padrão são 2: comercial + radiada)"
    return False, "nenhuma amostra cadastrada"


def _certificado(processo):
    if processo.certificado_numero:
        return True, f"certificado {processo.certificado_numero} registrado no processo"
    if _anexos(processo, "Certificado de conformidade (CCT)"):
        return True, "certificado anexado"
    return False, "sem número de certificado e sem anexo"


def _numero_homologacao(processo):
    if processo.numero_homologacao:
        return True, f"homologação {processo.numero_homologacao} registrada no processo"
    return False, "número de homologação em branco no cadastro do processo"


def _homologacao_na_base(processo):
    if processo.homologacoes:
        numeros = ", ".join(h.numero for h in processo.homologacoes)
        return True, f"cadastrada na base: {numeros}"
    return False, "ainda não registrada na base de homologações"


VERIFICACOES = {
    "anexo_iso": _por_anexo("Certificado ISO / avaliação fabril",
                            "Certificado ISO de Qualidade Fabril",
                            "Tradução juramentada do ISO", "Avaliação fabril (OCD)"),
    "anexo_cnpj": _por_anexo("Cartão CNPJ", "Cartão CNPJ"),
    "anexo_contrato": _por_anexo("Contrato Social", "Contrato Social"),
    "anexo_manual": _por_anexo("Manual / Datasheet", "Manual do usuário", "Datasheet"),
    "anexo_proposta_ocd": _por_anexo("Proposta da OCD", "Proposta comercial - OCD"),
    "anexo_proposta_lab": _por_anexo("Proposta do laboratório",
                                     "Proposta comercial - Laboratório"),
    "anexo_relatorio": _por_anexo("Relatório de ensaio", "Relatório de ensaio"),
    "anexo_nf_ocd": _por_anexo("Nota fiscal da OCD", "Nota fiscal - OCD"),
    "anexo_nf_lab": _por_anexo("Nota fiscal do laboratório", "Nota fiscal - Laboratório"),

    "doc_rastreabilidade": _por_documento("rastreabilidade", "Declaração de Rastreabilidade"),
    "doc_direitos_garantia": _por_documento("direitos_garantia",
                                            "Declaração dos Direitos e Garantias"),
    "doc_seguranca_cibernetica": _por_documento("seguranca_cibernetica",
                                                "Declaração de Segurança Cibernética"),
    "doc_manutencao": _por_documento("manutencao", "Declaração de Manutenção"),

    "fotos_externas": _por_grupo_de_fotos("Externas"),
    "fotos_internas": _por_grupo_de_fotos("Internas"),
    "foto_selo": _por_vista("selo_anatel", "Identificação e Selo Anatel"),
    "foto_acessorios": _por_vista("acessorios", "Acessórios e fonte"),

    "amostras_2": _duas_amostras,
    "cct": _certificado,
    "homologacao_numero": _numero_homologacao,
    "homologacao_base": _homologacao_na_base,
}


def avaliar(processo, chave):
    """Devolve {'ok': bool, 'detalhe': str} ou None quando o item e manual."""
    verificar = VERIFICACOES.get(chave or "")
    if not verificar:
        return None
    ok, detalhe = verificar(processo)
    return {"ok": ok, "detalhe": detalhe}
