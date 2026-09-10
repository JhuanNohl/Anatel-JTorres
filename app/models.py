"""Modelo de dados do sistema de Certificacao ANATEL - ZKTeco Brasil."""
import re
from datetime import date, datetime, timedelta

from . import cores
from .anatel import sem_acento
from .extensions import db

# ---------------------------------------------------------------- constantes

# Situacoes iniciais do processo. A partir daqui a lista vive na tabela status_processo,
# que voce edita na tela (Padroes -> Status do processo). Isto e so a carga inicial.
STATUS_INICIAIS = [
    # nome, cor, ordem, exige_justificativa, encerra
    ("Iniciado", "#3E7D9C", 10, False, False),
    ("Em andamento", "#D9A21B", 20, False, False),
    ("Finalizado", "#7AC143", 30, True, True),
    ("Cancelado", "#8B9296", 40, True, True),
]


class StatusProcesso(db.Model):
    """Situacoes que um processo pode assumir. Voce cria, edita e remove pela tela."""
    __tablename__ = "status_processo"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(60), unique=True, nullable=False)
    cor = db.Column(db.String(20), default=cores.PADRAO)
    ordem = db.Column(db.Integer, default=0)
    # ao mudar para este status, a justificativa passa a ser obrigatoria
    exige_justificativa = db.Column(db.Boolean, default=False)
    # status de encerramento: preenche a data de conclusao do processo
    encerra = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text, default="")

    def __str__(self):
        return self.nome

    @property
    def hex(self):
        """A cor sempre como '#rrggbb', mesmo nos cadastros antigos por nome."""
        return cores.normalizar(self.cor)

    @property
    def estilo(self):
        """CSS do crachá desta situacao (fundo, borda e texto derivados da cor)."""
        return cores.estilo_badge(self.cor)

    @property
    def estilo_indicador(self):
        return cores.estilo_indicador(self.cor)

    @property
    def em_uso(self):
        return Processo.query.filter_by(status=self.nome).count()


def status_disponiveis():
    """Status ativos, na ordem definida por voce."""
    return StatusProcesso.query.filter_by(ativo=True).order_by(
        StatusProcesso.ordem, StatusProcesso.nome).all()


def status_por_nome(nome):
    return StatusProcesso.query.filter_by(nome=nome).first()


def estilos_dos_status():
    """{nome: css do crachá} — usado pelas telas para pintar as etiquetas."""
    return {s.nome: s.estilo for s in StatusProcesso.query.all()}


TIPOS_PROCESSO = [
    "Certificação nova",
    "Certificação por similaridade",
    "Renovação / Manutenção",
    "Ampliação de família",
    "Alteração de projeto",
]

CATEGORIAS_ANATEL = ["Categoria I", "Categoria II", "Categoria III", "Não aplicável"]

SITUACOES_HOMOLOGACAO = [
    "Homologação Emitida",
    "Em análise na Anatel",
    "Homologação Suspensa",
    "Homologação Cancelada",
    "Vencida",
]

NATUREZAS_PRODUTO = ["Produto acabado", "Módulo"]

# tipo -> (titulo padrao, destinatario, quando usar)
TIPOS_DOCUMENTO = {
    "rastreabilidade": (
        "Declaração de Rastreabilidade", "ANATEL",
        "Primeiro documento do processo — precisa ser enviada ANTES da amostra ir ao "
        "laboratório. Sempre obrigatória.",
    ),
    "similaridade": (
        "Declaração de Similaridade", "OCD",
        "Somente quando modelos similares serão cobertos pelo mesmo código de homologação.",
    ),
    "direitos_garantia": (
        "Declaração dos Direitos e Garantias do Consumidor", "OCD",
        "Regra da OCP-Teli: aplicável a todos os produtos sob homologação. Sempre obrigatória.",
    ),
    "seguranca_cibernetica": (
        "Declaração de Segurança Cibernética", "OCD",
        "Regra da OCP-Teli: aplicável a todos os produtos que possuem função de equipamento "
        "terminal com conexão (direta ou indiretamente) à Internet, ou de equipamento de "
        "infraestrutura de redes de telecomunicações.",
    ),
    "manutencao": (
        "Declaração de Manutenção", "OCD",
        "Usada na renovação / manutenção do certificado de conformidade.",
    ),
    "outros": (
        "Declaração / documento complementar", "OCD",
        "Qualquer outro modelo que o OCD solicitar.",
    ),
}

CATEGORIAS_ANEXO = [
    "Requisitos enviados pela OCD",
    "Cartão CNPJ",
    "Contrato Social",
    "Certificado ISO de Qualidade Fabril",
    "Tradução juramentada do ISO",
    "Avaliação fabril (OCD)",
    "Proposta comercial - OCD",
    "Proposta comercial - Laboratório",
    "Nota fiscal - OCD",
    "Nota fiscal - Laboratório",
    "Boleto / comprovante de pagamento",
    "Datasheet",
    "Manual do usuário",
    "Relatório de ensaio",
    "Certificado de conformidade (CCT)",
    "Homologação ANATEL",
    "Layout de etiqueta",
    "Diagrama de blocos",
    "Esquemático / PCB",
    "Lista de materiais (BOM)",
    "E-mail / correspondência",
    "Outros",
]

# ---- status de cada item do checklist (mesmos que a OCD usa na planilha de requisitos)
STATUS_REQUISITO = ["Pendente", "Aguardando", "Recebido", "Não aplicável"]
STATUS_REQUISITO_CORES = {
    "Pendente": "off",
    "Aguardando": "warn",
    "Recebido": "ok",
    "Não aplicável": "neutro",
}
# contam como resolvidos no cálculo do progresso
STATUS_RESOLVIDOS = ("Recebido", "Não aplicável")

# Só estas categorias travam o pacote da OCD — o pacote é DOCUMENTAÇÃO.
# As demais (Comercial, Amostras, Ensaios, Financeiro, Encerramento) são acompanhamento
# interno do processo: aparecem no checklist e no progresso, mas não bloqueiam o envio.
CATEGORIAS_DO_PACOTE = {"Declarações", "Fotos", "Produto e manual"}


# ---- frases que a ANATEL exige no produto ou no manual
FRASES_OBRIGATORIAS = [
    ("classe_i", "Equipamento Classe I",
     "Inserir no produto (em local visível) ou no manual.",
     "Este equipamento deve ser conectado obrigatoriamente em tomada de rede de energia "
     "elétrica que possua aterramento (três pinos), conforme a Norma de instalações elétricas "
     "ABNT NBR 5410, visando a segurança dos usuários contra choques elétricos."),
    ("radiacao_restrita", "Radiação Restrita — Resolução Anatel nº 680/2017",
     "Frase de emissão secundária. No manual ou no selo Anatel.",
     "Este equipamento não tem direito à proteção contra interferência prejudicial e não pode "
     "causar interferência em sistemas devidamente autorizados."),
    ("usuario_final", "Produto aplicável a Usuário Final",
     "Deve constar a frase e o link.",
     "Para informações do produto homologado acesse o site: "
     "https://sistemas.anatel.gov.br/sch"),
]

# Equipamento Classe I, conforme definição da OCD
DEFINICAO_CLASSE_I = ("Equipamento para telecomunicações cuja proteção contra choque elétrico é "
                      "obtida através de isolação básica e da conexão do equipamento ao sistema "
                      "de aterramento da edificação onde ele é utilizado.")


# ---------------------------------------------------------------- checklists
# Transcrição da lista de requisitos da OCP-Teli.
# Formato: (categoria, descrição, detalhe/fine print, obrigatório)

_ISO_FABRICANTE = (
    "Cópia do Certificado de Qualidade Fabril - ISO com escopo de fabricação deste tipo de "
    "produto, válido nesta data. Deve ser enviada TAMBÉM a Tradução Juramentada para o idioma "
    "Português Brasil do certificado ISO.\n"
    "Alternativa: Avaliação Fabril realizada pela própria OCD."
)

_RASTREABILIDADE = (
    "Inserir em papel timbrado e assinar.\n"
    "ATENÇÃO: esta declaração deve ser enviada ANTES do envio da amostra ao laboratório.\n"
    "Deve ser inserida na amostra ou na embalagem e conter as seguintes informações "
    "IMPRESSAS (NÃO PODE SER MANUSCRITO): Modelo, Fabricante, País de Origem e "
    "Rastreabilidade."
)

_FOTOS_INTERNAS = (
    "Fotos internas das placas do produto:\n"
    "- de todas as placas, frente e verso;\n"
    "- de todas as placas COM e SEM blindagem (inclusive retirar a blindagem de módulos);\n"
    "- das placas completas dentro da carcaça do produto."
)

_FOTOS_EXTERNAS = (
    "Fotos externas de todos os lados do produto: frontal, traseira, superior, inferior, "
    "lateral esquerda e lateral direita.\n"
    "- Escala métrica, apresentando Largura x Altura x Profundidade.\n"
    "- Se o equipamento for conectado à rede elétrica por fonte de alimentação externa, é "
    "obrigatório constar na fonte a marcação com os valores nominais de tensão, corrente "
    "e/ou potência e frequência.\n"
    "- Equipamento Classe I: inserir a frase de aterramento (ABNT NBR 5410) no produto, em "
    "local visível, ou no manual."
)

_SELO = (
    "Identificação e Selo Anatel no produto, constando:\n"
    "- Modelo (NÃO pode ser nome comercial);\n"
    "- Rastreabilidade;\n"
    "- País de Origem;\n"
    "- Marca do Fabricante ou Fabricante;\n"
    "- Selo Anatel: verificar as opções apresentadas no Ato nº 4088.\n"
    "Se constar no módulo marcação de órgãos internacionais (FCC, CE), é MANDATÓRIO constar "
    "também a marcação do Selo Anatel."
)

_ACESSORIOS = (
    "Fotos dos acessórios comercializados com o produto (fonte de alimentação, fone de "
    "ouvido, microfone, receptores comercializados junto ao produto sob homologação etc.).\n"
    "- É obrigatório constar na fonte de alimentação externa a marcação com os valores "
    "nominais de tensão, corrente e/ou potência e frequência.\n"
    "- O acessório deve conter etiqueta de identificação, quando houver variações."
)

_MANUAL = (
    "Manual ou Datasheet contendo:\n"
    "- o modelo;\n"
    "- a descrição do produto;\n"
    "- as características técnicas mínimas necessárias para conhecimento e uso do produto;\n"
    "- padrões de medição e unidades do sistema métrico (idioma português ou espanhol) ou do "
    "sistema imperial (idioma inglês);\n"
    "- informações de segurança do usuário, instruções de operação e avisos de atenção;\n"
    "- se comercializado sem fonte de alimentação, informar a necessidade de usar apenas "
    "fontes homologadas pela Anatel (somente para telefone móvel celular).\n"
    "- Tamanho do arquivo até 10 MB, no idioma Português Brasil se o produto for para "
    "usuário leigo.\n"
    "Frases obrigatórias, quando aplicável: aterramento (Classe I), radiação restrita "
    "(Resolução nº 680/2017) e o link do SCH para usuário final."
)

# (categoria, descricao, detalhe, obrigatorio, chave)
# A "chave" liga o item a uma verificacao automatica (app/verificacao.py). Vazia = manual.
ESCOPOS_CHECKLIST = [
    ("ambos", "Todos os processos"),
    ("novo", "Só certificação nova"),
    ("renovacao", "Só renovação / manutenção"),
]


class ItemChecklist(db.Model):
    """Item do checklist da OCD, agora editavel por voce.

    Antes a lista vivia no codigo (CHECKLIST_NOVO / CHECKLIST_RENOVACAO). Ela
    continua sendo a carga inicial, mas o que vale na abertura de um processo e
    esta tabela: da para incluir exigencia nova, tirar o que a OCD nao pede mais
    e mudar de obrigatorio para opcional.
    """
    __tablename__ = "item_checklist"
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(60), nullable=False, default="Requisitos da OCD")
    descricao = db.Column(db.String(255), nullable=False)
    detalhe = db.Column(db.Text, default="")
    obrigatorio = db.Column(db.Boolean, default=True)
    escopo = db.Column(db.String(12), default="ambos")     # ambos | novo | renovacao
    # chave da verificacao automatica; em branco = o item e marcado a mao
    chave = db.Column(db.String(40), default="")
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text, default="")

    def __str__(self):
        return self.descricao

    @property
    def vale_para(self):
        return dict(ESCOPOS_CHECKLIST).get(self.escopo, "Todos os processos")

    @property
    def automatico(self):
        return bool(self.chave)


def itens_do_checklist(tipo_processo):
    """Itens ativos que valem para este tipo de processo, na sua ordem."""
    escopo = "renovacao" if "Renova" in (tipo_processo or "") else "novo"
    return (ItemChecklist.query
            .filter(ItemChecklist.ativo.is_(True),
                    ItemChecklist.escopo.in_(("ambos", escopo)))
            .order_by(ItemChecklist.ordem, ItemChecklist.id).all())


class CategoriaAnexo(db.Model):
    """As categorias em que um anexo pode entrar - tambem editaveis.

    Sao os grupos que aparecem no seletor de "Anexar arquivo" e que organizam as
    pastas do pacote da OCD.
    """
    __tablename__ = "categoria_anexo"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text, default="")

    def __str__(self):
        return self.nome

    @property
    def em_uso(self):
        return Anexo.query.filter_by(categoria=self.nome).count()


def categorias_de_anexo():
    """Nomes das categorias ativas, na ordem definida por voce."""
    return [c.nome for c in CategoriaAnexo.query
            .filter_by(ativo=True)
            .order_by(CategoriaAnexo.ordem, CategoriaAnexo.nome).all()]


CHECKLIST_NOVO = [
    ("Declarações", "Declaração de Rastreabilidade da Amostra", _RASTREABILIDADE, True,
     "doc_rastreabilidade"),
    ("Declarações", "Declaração dos Direitos e Garantias do Consumidor",
     "Inserir em papel timbrado e assinar. Aplicável a TODOS os produtos sob homologação.",
     True, "doc_direitos_garantia"),
    ("Declarações", "Declaração de Segurança Cibernética",
     "Inserir em papel timbrado e assinar.\n"
     "Aplicável para todos os produtos que possuem função de equipamento terminal com conexão "
     "(direta ou indiretamente) à Internet, ou de equipamento de infraestrutura de redes de "
     "telecomunicações.", True, "doc_seguranca_cibernetica"),

    ("Fotos", "Fotos internas das placas", _FOTOS_INTERNAS, True, "fotos_internas"),
    ("Fotos", "Fotos externas de todos os lados + escala métrica", _FOTOS_EXTERNAS, True,
     "fotos_externas"),
    ("Fotos", "Identificação e Selo Anatel no produto", _SELO, True, "foto_selo"),
    ("Fotos", "Fotos dos acessórios comercializados com o produto", _ACESSORIOS, True,
     "foto_acessorios"),

    ("Produto e manual", "Manual ou Datasheet", _MANUAL, True, "anexo_manual"),

    ("Comercial", "Proposta comercial da OCD aprovada", "", True, "anexo_proposta_ocd"),
    ("Comercial", "Proposta comercial do laboratório aprovada", "", True,
     "anexo_proposta_lab"),

    ("Amostras", "2 amostras preparadas (01 comercial + 01 radiada)", "", True, "amostras_2"),
    ("Amostras", "Selo de identificação IMPRESSO colado na amostra ou embalagem",
     "Modelo, Fabricante, País de Origem e Rastreabilidade. Não pode ser manuscrito.", True, ""),
    ("Amostras", "Número da proposta do laboratório colado na amostra", "", True, ""),
    ("Amostras", "Amostras enviadas ao laboratório",
     "Só enviar depois que a Declaração de Rastreabilidade já foi entregue.", True, ""),

    ("Ensaios", "Relatório de ensaio recebido", "", True, "anexo_relatorio"),

    ("Financeiro", "Nota fiscal da OCD recebida", "", False, "anexo_nf_ocd"),
    ("Financeiro", "Nota fiscal do laboratório recebida", "", False, "anexo_nf_lab"),
    ("Financeiro", "Pagamentos quitados", "", False, ""),

    ("Encerramento", "Certificado de conformidade (CCT) emitido", "", False, "cct"),
    ("Encerramento", "Número de homologação ANATEL obtido", "", False, "homologacao_numero"),
    ("Encerramento", "Homologação cadastrada na base do sistema", "", False,
     "homologacao_base"),
]

CHECKLIST_RENOVACAO = [
    ("Declarações", "Declaração de Manutenção",
     "Inserir em papel timbrado e assinar. Informar a referência do certificado "
     "(ex.: OCP 69124).", True, "doc_manutencao"),
    ("Declarações", "Declaração de Rastreabilidade da Amostra", _RASTREABILIDADE, True,
     "doc_rastreabilidade"),

    ("Fotos", "NOVAS fotos internas das placas",
     "Novas fotos internas dos 2 lados das placas, com e sem blindagem, COM RÉGUA ao lado e "
     "detalhando as informações obrigatórias: nome ou marca do fabricante, país de origem, "
     "modelo, rastreabilidade e número de homologação da Anatel.", True, "fotos_internas"),

    ("Comercial", "Proposta comercial da OCD aprovada", "", True, "anexo_proposta_ocd"),

    ("Financeiro", "Nota fiscal da OCD recebida", "", False, "anexo_nf_ocd"),
    ("Financeiro", "Pagamentos quitados", "", False, ""),

    ("Encerramento", "Certificado renovado recebido", "", False, "cct"),
    ("Encerramento", "Nova validade atualizada na base", "", False, ""),
]


# ---------------------------------------------------------------- cadastros

class Empresa(db.Model):
    """Dados do SOLICITANTE da certificacao (ZKTeco do Brasil). Registro unico id=1.

    Nao confundir com o detentor da tecnologia nem com o fabricante: pelo que o
    OCP-TELI esclareceu, esses dois papeis sao da fabrica (cadastrada em
    Fabricantes), e e o nome dela que sai na etiqueta da amostra.
    """
    __tablename__ = "empresa"
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False, default="")
    nome_fantasia = db.Column(db.String(200), default="")
    cnpj = db.Column(db.String(30), default="")
    inscricao_estadual = db.Column(db.String(40), default="")
    endereco = db.Column(db.String(240), default="")
    bairro = db.Column(db.String(120), default="")
    cidade = db.Column(db.String(120), default="")
    uf = db.Column(db.String(2), default="")
    cep = db.Column(db.String(20), default="")
    pais = db.Column(db.String(60), default="Brasil")
    telefone = db.Column(db.String(60), default="")
    email = db.Column(db.String(120), default="")
    site = db.Column(db.String(120), default="")
    sac = db.Column(db.String(120), default="")
    marca = db.Column(db.String(80), default="ZKTECO")   # marca declarada na homologação
    prazo_garantia = db.Column(db.String(60), default="12 (doze) meses")
    logo_arquivo = db.Column(db.String(255), default="")
    selo_anatel_arquivo = db.Column(db.String(255), default="")   # usado na folha de selos
    cidade_assinatura = db.Column(db.String(120), default="")
    observacoes = db.Column(db.Text, default="")

    @property
    def endereco_completo(self):
        partes = [self.endereco, self.bairro,
                  f"{self.cidade}/{self.uf}" if self.cidade else "",
                  f"CEP: {self.cep}" if self.cep else ""]
        return " - ".join([p for p in partes if p])

    @property
    def cabecalho(self):
        """Linhas do cabecalho dos documentos (igual a planilha original)."""
        linhas = [self.endereco,
                  f"{self.bairro} - {self.cidade}/{self.uf}" if self.bairro else
                  f"{self.cidade}/{self.uf}",
                  f"CEP: {self.cep}" + (f" Tel: {self.telefone}" if self.telefone else ""),
                  self.site]
        return [l for l in linhas if l and l.strip(" -/")]


CATEGORIAS_DOCUMENTO_EMPRESA = [
    "Cartão CNPJ",
    "Contrato Social",
    "Certificado ISO de Qualidade Fabril",
    "Tradução juramentada do ISO",
    "Avaliação fabril (OCD)",
    "Procuração",
    "Outros",
]


class DocumentoEmpresa(db.Model):
    """Documentos que valem para TODOS os processos (CNPJ, contrato social, ISO).

    Ficam guardados aqui uma vez so. A OCD nem sempre pede; quando pedir, e so incluir
    no pacote com um clique, sem reanexar em cada processo.
    """
    __tablename__ = "documento_empresa"
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(80), default="Outros", index=True)
    titulo = db.Column(db.String(200), default="")
    arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), default="")
    tamanho = db.Column(db.Integer)
    numero = db.Column(db.String(80), default="")
    emissao = db.Column(db.Date)
    validade = db.Column(db.Date)
    observacao = db.Column(db.Text, default="")
    criado_em = db.Column(db.DateTime, default=datetime.now)

    @property
    def dias_para_vencer(self):
        if not self.validade:
            return None
        return (self.validade - date.today()).days

    @property
    def alerta(self):
        dias = self.dias_para_vencer
        if dias is None:
            return ""
        if dias < 0:
            return "vencido"
        if dias <= 60:
            return "critico"
        return ""


class Signatario(db.Model):
    __tablename__ = "signatario"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    cargo = db.Column(db.String(120), default="")
    cpf = db.Column(db.String(30), default="")
    email = db.Column(db.String(120), default="")
    email_alternativo = db.Column(db.String(120), default="")
    telefone = db.Column(db.String(60), default="")
    assinatura_arquivo = db.Column(db.String(255), default="")
    padrao = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)

    def __str__(self):
        return self.nome


class OCD(db.Model):
    """Organismo de Certificacao Designado (ex.: OCP-TELI)."""
    __tablename__ = "ocd"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    razao_social = db.Column(db.String(250), default="")
    endereco = db.Column(db.String(250), default="")
    cnpj = db.Column(db.String(30), default="")
    designacao = db.Column(db.String(120), default="")
    cidade = db.Column(db.String(120), default="")
    uf = db.Column(db.String(2), default="")
    contato_nome = db.Column(db.String(160), default="")
    email = db.Column(db.String(160), default="")
    telefone = db.Column(db.String(60), default="")
    site = db.Column(db.String(160), default="")
    observacoes = db.Column(db.Text, default="")
    ativo = db.Column(db.Boolean, default=True)

    def __str__(self):
        return self.nome

    @property
    def bloco_endereco(self):
        return [l for l in [self.razao_social or self.nome, self.endereco,
                            f"{self.cidade} - {self.uf}" if self.cidade else ""] if l]


class Laboratorio(db.Model):
    __tablename__ = "laboratorio"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    razao_social = db.Column(db.String(250), default="")
    endereco = db.Column(db.String(250), default="")
    cnpj = db.Column(db.String(30), default="")
    acreditacao = db.Column(db.String(120), default="")
    escopo = db.Column(db.String(255), default="")
    cidade = db.Column(db.String(120), default="")
    uf = db.Column(db.String(2), default="")
    contato_nome = db.Column(db.String(160), default="")
    email = db.Column(db.String(160), default="")
    telefone = db.Column(db.String(60), default="")
    site = db.Column(db.String(160), default="")
    observacoes = db.Column(db.Text, default="")
    ativo = db.Column(db.Boolean, default=True)

    def __str__(self):
        return self.nome


class Fabricante(db.Model):
    """Unidade fabril onde a amostra e produzida (ex.: ZKTECO CO., LTDA. - China)."""
    __tablename__ = "fabricante"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    razao_social = db.Column(db.String(200), default="")
    endereco = db.Column(db.String(255), default="")
    cidade = db.Column(db.String(120), default="")
    pais = db.Column(db.String(80), default="China")
    contato_nome = db.Column(db.String(160), default="")
    email = db.Column(db.String(160), default="")
    telefone = db.Column(db.String(60), default="")
    iso9001 = db.Column(db.String(120), default="")
    iso9001_validade = db.Column(db.Date)
    observacoes = db.Column(db.Text, default="")
    ativo = db.Column(db.Boolean, default=True)

    produtos = db.relationship("Produto", back_populates="fabricante")

    def __str__(self):
        return self.nome

    @property
    def endereco_completo(self):
        return " ".join([p for p in [self.endereco] if p]) or \
            " - ".join([p for p in [self.cidade, self.pais] if p])


class Produto(db.Model):
    __tablename__ = "produto"
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(db.String(120), nullable=False, index=True)
    nome_comercial = db.Column(db.String(160), default="")
    familia = db.Column(db.String(120), default="")
    tipo_equipamento = db.Column(db.String(160), default="")
    natureza = db.Column(db.String(40), default="Produto acabado")  # Modulo | Produto acabado
    categoria_anatel = db.Column(db.String(40), default="Categoria II")
    fabricante_id = db.Column(db.Integer, db.ForeignKey("fabricante.id"))
    descricao = db.Column(db.Text, default="")
    tecnologias = db.Column(db.String(255), default="")
    faixas_frequencia = db.Column(db.String(255), default="")
    potencia = db.Column(db.String(120), default="")
    alimentacao = db.Column(db.String(160), default="")
    bateria = db.Column(db.String(160), default="")
    dimensoes = db.Column(db.String(120), default="")
    peso = db.Column(db.String(60), default="")
    ncm = db.Column(db.String(30), default="")
    gtin = db.Column(db.String(30), default="")
    codigo_interno = db.Column(db.String(60), default="")
    possui_radio = db.Column(db.Boolean, default=True)
    conecta_internet = db.Column(db.Boolean, default=False)
    # caracteristicas que definem frases obrigatorias e fotos extras (requisitos da OCD)
    classe_i = db.Column(db.Boolean, default=False)
    radiacao_restrita = db.Column(db.Boolean, default=False)
    usuario_final = db.Column(db.Boolean, default=True)
    fonte_externa = db.Column(db.Boolean, default=False)
    acessorios = db.Column(db.String(255), default="")
    observacoes = db.Column(db.Text, default="")
    ativo = db.Column(db.Boolean, default=True)

    fabricante = db.relationship("Fabricante", back_populates="produtos")
    processos = db.relationship("Processo", back_populates="produto")
    aplicacoes = db.relationship("AplicacaoHomologacao", back_populates="produto")
    homologacoes_modelo = db.relationship("HomologacaoModelo", back_populates="produto")
    fotos = db.relationship("FotoProduto", back_populates="produto",
                            cascade="all, delete-orphan", order_by="FotoProduto.ordem")
    # Qual das fotos e a capa. A foto pode vir de tres lugares (do modelo, da
    # homologacao ou do processo), por isso guardo a origem junto com o id -
    # assim marcar a capa nao move nem esconde nenhuma foto.
    capa_origem = db.Column(db.String(20), default="")     # produto|homologacao|processo
    capa_ref_id = db.Column(db.Integer)

    def __str__(self):
        return f"{self.modelo}" + (f" - {self.nome_comercial}" if self.nome_comercial else "")


# ------------------------------------------------------- base de homologacoes

class Homologacao(db.Model):
    """Homologacao ANATEL vigente (base historica + resultado dos processos)."""
    __tablename__ = "homologacao"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(40), index=True)          # 01034-22-12720
    certificado = db.Column(db.String(60), default="")     # OCP 07622
    validade = db.Column(db.Date, index=True)
    situacao = db.Column(db.String(60), default="Homologação Emitida")
    natureza = db.Column(db.String(40), default="Produto acabado")
    tipo = db.Column(db.String(200), default="")           # ex.: Modulo Wi-Fi
    aplicacoes = db.Column(db.Text, default="")            # produtos que usam o modulo
    ocd_id = db.Column(db.Integer, db.ForeignKey("ocd.id"))
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"))
    renovar = db.Column(db.Boolean, default=False)
    aviso_enviado_em = db.Column(db.DateTime)
    # Decisao sobre renovar quando a validade chega perto. "nao" tem de vir com
    # motivo: e a justificativa que responde por que um produto saiu de linha.
    renovacao_decisao = db.Column(db.String(10), default="")   # "" | renovar | nao
    renovacao_motivo = db.Column(db.Text, default="")
    renovacao_decidida_em = db.Column(db.DateTime)
    renovacao_decidida_por = db.Column(db.String(120), default="")
    observacoes = db.Column(db.Text, default="")
    criado_em = db.Column(db.DateTime, default=datetime.now)

    # --- vindos da base publica da ANATEL (preenchidos pela sincronizacao)
    situacao_certificado = db.Column(db.String(60), default="")   # Homologado, Suspenso...
    data_homologacao = db.Column(db.Date)
    tipo_produto_anatel = db.Column(db.String(200), default="")
    # Uma homologacao pode ter mais de um ensaio (ex.: leitor de cartao E Wi-Fi).
    # A base publica traz uma linha por ensaio, com o MESMO numero; aqui elas
    # viram um registro so, com os tipos reunidos - um por linha.
    ensaios_anatel = db.Column(db.Text, default="")
    marca = db.Column(db.String(120), default="")
    fabricante_nome = db.Column(db.String(160), default="")
    solicitante = db.Column(db.String(160), default="")
    cnpj = db.Column(db.String(20), default="")
    origem = db.Column(db.String(20), default="Manual")           # ANATEL | Manual
    sincronizado_em = db.Column(db.DateTime)
    versao_placa = db.Column(db.String(120), default="")

    ocd = db.relationship("OCD")
    processo = db.relationship("Processo", back_populates="homologacoes")
    modelos = db.relationship("HomologacaoModelo", back_populates="homologacao",
                              cascade="all, delete-orphan")
    aplicacoes_produtos = db.relationship(
        "AplicacaoHomologacao", back_populates="homologacao",
        cascade="all, delete-orphan", order_by="AplicacaoHomologacao.modelo")
    fotos = db.relationship("FotoHomologacao", back_populates="homologacao",
                            cascade="all, delete-orphan",
                            order_by="FotoHomologacao.ordem")

    @property
    def lista_modelos(self):
        return ", ".join(m.modelo for m in self.modelos)

    @property
    def ensaios(self):
        """Tipos de produto que a ANATEL ensaiou neste mesmo certificado."""
        return [linha.strip() for linha in (self.ensaios_anatel or "").splitlines()
                if linha.strip()]

    @property
    def ensaios_por_extenso(self):
        return " · ".join(self.ensaios)

    @property
    def nao_vai_renovar(self):
        return self.renovacao_decisao == "nao"

    @property
    def decisao_por_extenso(self):
        if self.renovacao_decisao == "nao":
            return "não renovar"
        if self.renovacao_decisao == "renovar":
            return "renovar"
        return ""

    @property
    def da_anatel(self):
        return self.origem == "ANATEL"

    @property
    def capa(self):
        """Primeira foto - as fotos sao da homologacao, valem para todos os modelos."""
        return self.fotos[0] if self.fotos else None

    @property
    def vigente(self):
        """A ANATEL considera valido? Olha a situacao do certificado e a validade."""
        ruins = ("suspens", "cancel", "revog", "indefer", "vencid", "expirad")
        texto = sem_acento(f"{self.situacao_certificado} {self.situacao}")
        if any(r in texto for r in ruins):
            return False
        dias = self.dias_para_vencer
        return True if dias is None else dias >= 0

    @property
    def selo_situacao(self):
        """Cor do crachá da situacao, no padrao das telas."""
        if not self.vigente:
            return "erro"
        dias = self.dias_para_vencer
        if dias is not None and dias <= 90:
            return "warn"
        return "ok"

    @property
    def dias_para_vencer(self):
        if not self.validade:
            return None
        return (self.validade - date.today()).days

    @property
    def alerta(self):
        d = self.dias_para_vencer
        if d is None:
            return ""
        if d < 0:
            return "vencida"
        if d <= 90:
            return "critico"
        if d <= 180:
            return "atencao"
        return ""


class HomologacaoModelo(db.Model):
    """Modelo certificado NA homologacao - vem da base da ANATEL."""
    __tablename__ = "homologacao_modelo"
    id = db.Column(db.Integer, primary_key=True)
    homologacao_id = db.Column(db.Integer, db.ForeignKey("homologacao.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"))
    modelo = db.Column(db.String(120), nullable=False, index=True)

    homologacao = db.relationship("Homologacao", back_populates="modelos")
    produto = db.relationship("Produto", back_populates="homologacoes_modelo")


class AplicacaoHomologacao(db.Model):
    """Produto acabado que USA um modulo homologado.

    Um modulo homologado (ex.: EM05) e embarcado em dezenas de produtos
    (ZK8500R, P160, MB10...). Esses produtos nao estao no certificado, mas
    dependem dele - e essa a correlacao que a OCD e o comercial precisam ver.
    """
    __tablename__ = "aplicacao_homologacao"
    id = db.Column(db.Integer, primary_key=True)
    homologacao_id = db.Column(db.Integer, db.ForeignKey("homologacao.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"))
    modelo = db.Column(db.String(160), nullable=False, index=True)
    observacoes = db.Column(db.String(255), default="")

    homologacao = db.relationship("Homologacao", back_populates="aplicacoes_produtos")
    produto = db.relationship("Produto", back_populates="aplicacoes")


class FotoProduto(db.Model):
    """Foto do modelo no catalogo, escolhida por voce.

    Diferente das fotos do processo (que seguem o roteiro de vistas da OCD) e das
    fotos da homologacao (compartilhadas pelo certificado): estas sao as fotos que
    voce quer ver no catalogo. A primeira e a capa, e e ela que aparece na lista.
    """
    __tablename__ = "foto_produto"
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), default="")
    legenda = db.Column(db.String(255), default="")
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.now)

    produto = db.relationship("Produto", back_populates="fotos")


class FotoHomologacao(db.Model):
    """Foto do produto, vinculada a HOMOLOGACAO.

    Fica na homologacao (e nao no modelo) porque todos os modelos do mesmo
    certificado sao o mesmo produto fisico. A primeira foto e a capa.
    """
    __tablename__ = "foto_homologacao"
    id = db.Column(db.Integer, primary_key=True)
    homologacao_id = db.Column(db.Integer, db.ForeignKey("homologacao.id"), nullable=False)
    arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), default="")
    legenda = db.Column(db.String(255), default="")
    ordem = db.Column(db.Integer, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.now)

    homologacao = db.relationship("Homologacao", back_populates="fotos")


UNIDADES_DE_PRAZO = [("horas", "horas"), ("dias", "dias"), ("meses", "meses")]
HORAS_POR_UNIDADE = {"horas": 1, "dias": 24, "meses": 24 * 30}


class ConfigAnatel(db.Model):
    """Como e quando a base publica da ANATEL e relida.

    Registro unico (id=1). O agendador olha isto para decidir se ja passou da
    hora de baixar o arquivo de novo.
    """
    __tablename__ = "config_anatel"
    id = db.Column(db.Integer, primary_key=True)
    automatico = db.Column(db.Boolean, default=True)
    intervalo_valor = db.Column(db.Integer, default=7)
    intervalo_unidade = db.Column(db.String(10), default="dias")
    ultima_tentativa = db.Column(db.DateTime)
    ultimo_erro = db.Column(db.String(255), default="")
    # Com quantos dias de antecedencia uma homologacao entra em "vence em breve".
    # 90 dias e o padrao porque renovar exige ensaio de laboratorio e leva tempo.
    dias_aviso_vencimento = db.Column(db.Integer, default=90)

    @property
    def dias_de_aviso(self):
        return max(1, self.dias_aviso_vencimento or 90)

    @property
    def horas_do_intervalo(self):
        valor = max(1, self.intervalo_valor or 1)
        return valor * HORAS_POR_UNIDADE.get(self.intervalo_unidade, 24)

    @property
    def intervalo_por_extenso(self):
        valor = max(1, self.intervalo_valor or 1)
        unidade = self.intervalo_unidade or "dias"
        if valor == 1:
            unidade = {"horas": "hora", "dias": "dia", "meses": "mês"}[unidade]
        return f"{valor} {unidade}"

    @property
    def ultima_leitura(self):
        registro = (SincronizacaoAnatel.query
                    .order_by(SincronizacaoAnatel.id.desc()).first())
        return registro.criado_em if registro else None

    @property
    def idade_em_horas(self):
        """Vida atual da base, em horas. None se nunca foi lida."""
        quando = self.ultima_leitura
        if not quando:
            return None
        return (datetime.now() - quando).total_seconds() / 3600

    @property
    def proxima_em(self):
        """Quando vence o prazo. None se nunca foi lida."""
        quando = self.ultima_leitura
        if not quando:
            return None
        return quando + timedelta(hours=self.horas_do_intervalo)

    @property
    def horas_restantes(self):
        """Quanto falta para reler. Negativo = atrasada. None = nunca foi lida."""
        proxima = self.proxima_em
        if proxima is None:
            return None
        return (proxima - datetime.now()).total_seconds() / 3600

    @property
    def vencida(self):
        restantes = self.horas_restantes
        return True if restantes is None else restantes <= 0


class SessaoCaptura(db.Model):
    """Uma sessao de fotos pelo celular, aberta pelo QR code da tela do processo.

    O celular nao faz login (o sistema nao tem login - vive dentro da rede da
    empresa); quem autoriza e o token do endereco, que so existe enquanto a
    sessao esta aberta. Retomar e so abrir o mesmo endereco: a proxima vista sai
    do banco, nao do celular, entao dá para parar no meio e continuar depois -
    ou até trocar de aparelho.
    """
    __tablename__ = "sessao_captura"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False, index=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    ultimo_acesso = db.Column(db.DateTime)
    expira_em = db.Column(db.DateTime)
    encerrada = db.Column(db.Boolean, default=False)
    fotos_enviadas = db.Column(db.Integer, default=0)
    fotos_recusadas = db.Column(db.Integer, default=0)
    aparelho = db.Column(db.String(255), default="")

    processo = db.relationship("Processo")

    @property
    def vencida(self):
        return bool(self.expira_em and datetime.now() > self.expira_em)

    @property
    def valida(self):
        return not self.encerrada and not self.vencida

    @property
    def horas_restantes(self):
        if not self.expira_em:
            return None
        return max(0, round((self.expira_em - datetime.now()).total_seconds() / 3600))


class ConfigVistoria(db.Model):
    """Como a foto e conferida quando chega (registro unico, id=1).

    A conferencia local (Pillow) esta sempre ligada: nao custa nada e nao sai da
    rede. A conferencia por IA nasce DESLIGADA - ligar significa mandar a foto
    para a API da Anthropic, o que tem custo e tira a imagem de dentro da
    empresa. Por isso e uma decisao consciente, feita nesta tela.
    """
    __tablename__ = "config_vistoria"
    id = db.Column(db.Integer, primary_key=True)
    ia_ligada = db.Column(db.Boolean, default=False)
    ia_chave = db.Column(db.String(255), default="")     # vazio = usa ANTHROPIC_API_KEY
    ia_modelo = db.Column(db.String(60), default="claude-opus-5")
    # Reprovar a foto quando a IA disser que esta errada, ou so avisar?
    ia_reprova = db.Column(db.Boolean, default=True)
    horas_da_sessao = db.Column(db.Integer, default=12)

    @property
    def chave_efetiva(self):
        """A chave digitada aqui ou, se vazia, a do ambiente."""
        import os
        return (self.ia_chave or "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def chave_mascarada(self):
        chave = self.chave_efetiva
        if not chave:
            return ""
        return f"{chave[:7]}…{chave[-4:]}" if len(chave) > 14 else "definida"

    @property
    def ia_disponivel(self):
        return bool(self.chave_efetiva)


def config_vistoria():
    config = ConfigVistoria.query.get(1)
    if config is None:
        config = ConfigVistoria(id=1)
        db.session.add(config)
        db.session.commit()
    return config


def config_anatel():
    """O registro unico de configuracao, criando-o na primeira vez."""
    config = ConfigAnatel.query.get(1)
    if config is None:
        config = ConfigAnatel(id=1)
        db.session.add(config)
        db.session.commit()
    return config


class SincronizacaoAnatel(db.Model):
    """Historico das atualizacoes da base publica - o que mudou e quando."""
    __tablename__ = "sincronizacao_anatel"
    id = db.Column(db.Integer, primary_key=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, index=True)
    solicitante = db.Column(db.String(160), default="")
    linhas_no_arquivo = db.Column(db.Integer, default=0)
    encontradas = db.Column(db.Integer, default=0)
    homologacoes = db.Column(db.Integer, default=0)
    criadas = db.Column(db.Integer, default=0)
    atualizadas = db.Column(db.Integer, default=0)
    modelos_novos = db.Column(db.Integer, default=0)
    produtos_novos = db.Column(db.Integer, default=0)
    mudancas = db.Column(db.Text, default="")

    @property
    def lista_mudancas(self):
        return [linha for linha in (self.mudancas or "").splitlines() if linha.strip()]


# ---------------------------------------------------------------- processo

class Processo(db.Model):
    __tablename__ = "processo"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(40), unique=True, nullable=False, index=True)
    ano = db.Column(db.Integer, default=lambda: date.today().year)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    ocd_id = db.Column(db.Integer, db.ForeignKey("ocd.id"))
    laboratorio_id = db.Column(db.Integer, db.ForeignKey("laboratorio.id"))
    signatario_id = db.Column(db.Integer, db.ForeignKey("signatario.id"))
    tipo_processo = db.Column(db.String(60), default="Certificação nova")
    categoria_anatel = db.Column(db.String(40), default="Categoria II")
    status = db.Column(db.String(30), default="Iniciado", index=True)

    # Tamanho da etiqueta impressa, em milimetros. Fica no processo porque
    # depende do produto: um leitor de cartao pequeno nao aceita a mesma etiqueta
    # de uma catraca. Vazio = usa o padrao.
    etiqueta_largura_mm = db.Column(db.Integer)
    etiqueta_altura_mm = db.Column(db.Integer)
    # Deixar o texto quebrar em mais de uma linha, coluna por coluna. O rotulo
    # ("Nome do fabricante:") normalmente fica em uma linha so; o valor quebra,
    # porque rastreabilidade longa nao pode ser cortada.
    etiqueta_quebra_rotulo = db.Column(db.Boolean, default=False)
    etiqueta_quebra_valor = db.Column(db.Boolean, default=True)
    # O selo ANATEL tem tamanho proprio: e outra etiqueta, com outro conteudo
    # (logo + numero) e quase sempre menor que a de identificacao.
    selo_largura_mm = db.Column(db.Integer)
    selo_altura_mm = db.Column(db.Integer)

    requer_similaridade = db.Column(db.Boolean, default=False)
    requer_ciberseguranca = db.Column(db.Boolean, default=False)

    data_abertura = db.Column(db.Date, default=date.today)
    data_previsao = db.Column(db.Date)
    data_conclusao = db.Column(db.Date)

    # referencias comerciais / de processo
    referencia_ocd = db.Column(db.String(60), default="")      # ex.: OCP 69124
    proposta_ocd = db.Column(db.String(60), default="")
    proposta_laboratorio = db.Column(db.String(60), default="")
    numero_homologacao = db.Column(db.String(60), default="")
    certificado_numero = db.Column(db.String(60), default="")
    certificado_validade = db.Column(db.Date)
    relatorio_ensaio = db.Column(db.String(120), default="")

    # rastreabilidade declarada (alimenta a Declaracao de Rastreabilidade)
    rast_serie = db.Column(db.Boolean, default=False)
    rast_serie_valor = db.Column(db.String(160), default="")
    rast_lote = db.Column(db.Boolean, default=False)
    rast_lote_valor = db.Column(db.String(160), default="")
    rast_data_fab = db.Column(db.Boolean, default=False)
    rast_data_fab_valor = db.Column(db.String(160), default="")
    rast_mac = db.Column(db.Boolean, default=False)
    rast_mac_valor = db.Column(db.String(160), default="")
    rast_outros = db.Column(db.Boolean, default=False)
    rast_outros_valor = db.Column(db.String(255), default="")

    responsavel = db.Column(db.String(160), default="")
    valor_ocd = db.Column(db.Float)
    valor_laboratorio = db.Column(db.Float)
    valor_outros = db.Column(db.Float)
    observacoes = db.Column(db.Text, default="")

    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    produto = db.relationship("Produto", back_populates="processos")
    ocd = db.relationship("OCD")
    laboratorio = db.relationship("Laboratorio")
    signatario = db.relationship("Signatario")

    documentos = db.relationship("Documento", back_populates="processo",
                                 cascade="all, delete-orphan", order_by="Documento.criado_em")
    fotos = db.relationship("Foto", back_populates="processo",
                            cascade="all, delete-orphan", order_by="Foto.id")
    anexos = db.relationship("Anexo", back_populates="processo",
                             cascade="all, delete-orphan",
                             order_by="Anexo.criado_em.desc()")
    similares = db.relationship("ProdutoSimilar", back_populates="processo",
                                cascade="all, delete-orphan", order_by="ProdutoSimilar.id")
    amostras = db.relationship("Amostra", back_populates="processo",
                               cascade="all, delete-orphan", order_by="Amostra.id")
    historico = db.relationship("StatusLog", back_populates="processo",
                                cascade="all, delete-orphan",
                                order_by="StatusLog.criado_em.desc()")
    requisitos = db.relationship("Requisito", back_populates="processo",
                                 cascade="all, delete-orphan", order_by="Requisito.ordem")
    ajustes_vista = db.relationship("VistaProcesso", back_populates="processo",
                                    cascade="all, delete-orphan")
    requisitos_ciber = db.relationship("RequisitoCiber", back_populates="processo",
                                       cascade="all, delete-orphan",
                                       order_by="RequisitoCiber.ordem")
    homologacoes = db.relationship("Homologacao", back_populates="processo")

    # ---- helpers de tela

    @property
    def titulo(self):
        return f"{self.numero} - {self.produto.modelo if self.produto else '?'}"

    @property
    def custo_total(self):
        return sum(v for v in (self.valor_ocd, self.valor_laboratorio, self.valor_outros) if v)

    def tem_documento(self, tipo):
        return any(d.tipo == tipo for d in self.documentos)

    @property
    def modelos_declarados(self):
        """Modelo principal + similares, como aparece nas declaracoes."""
        modelos = [self.produto.modelo] if self.produto else []
        modelos += [s.modelo for s in self.similares]
        return modelos

    @property
    def progresso_checklist(self):
        itens = [r for r in self.requisitos if r.obrigatorio]
        if not itens:
            return 0
        return round(100 * sum(1 for r in itens if r.resolvido) / len(itens))

    @property
    def vistas_nao_aplicaveis(self):
        """ids das vistas que este processo marcou como N/A."""
        return {a.vista_id for a in self.ajustes_vista if a.nao_aplicavel}

    @property
    def motivos_vista(self):
        return {a.vista_id: a.motivo for a in self.ajustes_vista if a.nao_aplicavel}

    @property
    def ciber_nao_aplicaveis(self):
        return [r for r in self.requisitos_ciber if r.situacao == "NA"]

    @property
    def ciber_sem_justificativa(self):
        return [r for r in self.requisitos_ciber if r.falta_justificar]

    @property
    def frases_aplicaveis(self):
        """Frases obrigatorias que o produto precisa exibir, conforme os flags do produto."""
        if not self.produto:
            return []
        return [f for f in FRASES_OBRIGATORIAS if getattr(self.produto, f[0], False)]

    @property
    def rastreabilidade_itens(self):
        return [
            ("Número(s) de Série", self.rast_serie, self.rast_serie_valor),
            ("Número do Lote", self.rast_lote, self.rast_lote_valor),
            ("Data de Fabricação", self.rast_data_fab, self.rast_data_fab_valor),
            ("Número IMEI/MAC", self.rast_mac, self.rast_mac_valor),
            ("Outros", self.rast_outros, self.rast_outros_valor),
        ]

    # 50 x 30 mm e o tamanho de etiqueta mais comum em impressora termica e
    # cabe bem nos produtos que passam por aqui.
    ETIQUETA_PADRAO = (50, 30)
    SELO_PADRAO = (40, 20)
    ETIQUETA_MIN = (20, 10)
    ETIQUETA_MAX = (200, 150)

    @property
    def fabricante_na_etiqueta(self):
        """O nome que a etiqueta da amostra imprime como fabricante.

        E o mesmo que a Declaracao de Rastreabilidade chama de unidade fabril.
        Sem fabricante cadastrado a etiqueta cai no nome da empresa - e ai os
        dois documentos passam a dizer coisas diferentes, que foi exatamente o
        que o OCD questionou uma vez.
        """
        fab = self.produto.fabricante if self.produto else None
        if fab:
            return fab.razao_social or fab.nome
        empresa = Empresa.query.get(1)             # o mesmo recuo da etiqueta
        return empresa.razao_social if empresa else ""

    @property
    def fabricante_coerente(self):
        """True quando a etiqueta e a declaracao vao dizer o mesmo fabricante."""
        return bool(self.produto and self.produto.fabricante)

    @property
    def etiqueta_quebras(self):
        """(rotulo, valor) - True = pode quebrar em varias linhas."""
        rotulo = self.etiqueta_quebra_rotulo
        valor = self.etiqueta_quebra_valor
        return (bool(rotulo),
                True if valor is None else bool(valor))   # padrao antigo: valor quebra

    def _dentro_dos_limites(self, largura, altura):
        return (max(self.ETIQUETA_MIN[0], min(self.ETIQUETA_MAX[0], largura)),
                max(self.ETIQUETA_MIN[1], min(self.ETIQUETA_MAX[1], altura)))

    @property
    def etiqueta_mm(self):
        """(largura, altura) da etiqueta de identificacao, dentro dos limites."""
        return self._dentro_dos_limites(
            self.etiqueta_largura_mm or self.ETIQUETA_PADRAO[0],
            self.etiqueta_altura_mm or self.ETIQUETA_PADRAO[1])

    @property
    def selo_mm(self):
        """(largura, altura) do selo ANATEL - medida separada da etiqueta."""
        return self._dentro_dos_limites(
            self.selo_largura_mm or self.SELO_PADRAO[0],
            self.selo_altura_mm or self.SELO_PADRAO[1])

    def medida_da_folha(self, modo):
        return self.selo_mm if modo == "selo" else self.etiqueta_mm

    @property
    def rastreabilidade_declarada(self):
        """Valores marcados na Declaracao de Rastreabilidade.

        A OCD exige que a rastreabilidade da etiqueta da amostra e a da declaracao
        sejam IDENTICAS, entao esta lista serve de referencia na folha de etiquetas.
        """
        return [(v or "").strip() for _, marcado, v in self.rastreabilidade_itens
                if marcado and (v or "").strip()]


class StatusLog(db.Model):
    __tablename__ = "status_log"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    de_status = db.Column(db.String(30), default="")
    para_status = db.Column(db.String(30), default="")
    observacao = db.Column(db.Text, default="")
    autor = db.Column(db.String(120), default="")
    criado_em = db.Column(db.DateTime, default=datetime.now)

    processo = db.relationship("Processo", back_populates="historico")


class ProdutoSimilar(db.Model):
    """Modelos cobertos pelo mesmo codigo de homologacao (declaracao de similaridade)."""
    __tablename__ = "produto_similar"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    modelo = db.Column(db.String(120), nullable=False)
    nome_comercial = db.Column(db.String(160), default="")
    diferencas = db.Column(db.Text, default="")
    diferencas_en = db.Column(db.Text, default="")
    observacoes = db.Column(db.Text, default="")

    processo = db.relationship("Processo", back_populates="similares")


class Amostra(db.Model):
    """Amostra enviada ao laboratorio e o selo de identificacao correspondente."""
    __tablename__ = "amostra"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    identificacao = db.Column(db.String(120), default="Amostra comercial")
    rastreabilidade = db.Column(db.String(160), default="")   # MAC, lote, DTM WiFi Test...
    numero_homologacao = db.Column(db.String(60), default="")
    numero_serie = db.Column(db.String(120), default="")
    observacoes = db.Column(db.Text, default="")

    processo = db.relationship("Processo", back_populates="amostras")

    @property
    def rastreabilidade_etiqueta(self):
        return (self.rastreabilidade or self.numero_serie or "").strip()

    @property
    def rastreabilidade_confere(self):
        """True/False comparando com a declaracao; None quando nao ha o que comparar.

        Cada etiqueta leva UM valor. Se a amostra tiver dois ("...001 e ...002"),
        nao confere: sao duas amostras, cada uma com a sua etiqueta.
        """
        declarada = self.processo.rastreabilidade_declarada if self.processo else []
        if not declarada or not self.rastreabilidade_etiqueta:
            return None
        meus = separar_valores(self.rastreabilidade_etiqueta)
        if len(meus) != 1:
            return False
        permitidos = {v.lower() for d in declarada for v in separar_valores(d)}
        return meus[0].lower() in permitidos


def separar_valores(texto):
    """Quebra "A e B", "A, B", "A; B", "A / B" ou uma lista por linhas em valores soltos.

    Nao quebra em espaco simples: "MAC E10000042574" e um valor unico.
    """
    partes = re.split(r"\s*(?:,|;|/|\n|\be\b)\s*", texto or "",
                      flags=re.IGNORECASE)
    return [x.strip() for x in partes if x.strip()]


SITUACOES_CIBER = ["C", "NA"]
LEGENDA_CIBER = {
    "C": "O equipamento apresenta conformidade ao requisito.",
    "NA": "O requisito não se aplica ao equipamento, devido as suas características. "
          "Justificativa deverá ser apresentada.",
}


class RequisitoCiber(db.Model):
    """Um item do formulário de segurança cibernética (Ato nº 77/2021), por processo.

    O texto e gravado junto: a declaracao assinada nao muda se o catalogo for atualizado.
    """
    __tablename__ = "requisito_ciber"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    ordem = db.Column(db.Integer, default=0)
    codigo = db.Column(db.String(20), default="")
    titulo = db.Column(db.Text, default="")     # 5.1. / 6.1.
    secao = db.Column(db.Text, default="")      # 5.1.1., 5.1.2., ...
    texto = db.Column(db.Text, default="")
    situacao = db.Column(db.String(4), default="C")     # C ou NA
    justificativa = db.Column(db.Text, default="")

    processo = db.relationship("Processo", back_populates="requisitos_ciber")

    @property
    def falta_justificar(self):
        return self.situacao == "NA" and not (self.justificativa or "").strip()


class Requisito(db.Model):
    """Item do checklist de requisitos da OCD."""
    __tablename__ = "requisito"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    categoria = db.Column(db.String(60), default="")
    descricao = db.Column(db.String(255), nullable=False)
    detalhe = db.Column(db.Text, default="")        # a letra miuda enviada pela OCD
    obrigatorio = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(30), default="Pendente")
    observacao = db.Column(db.Text, default="")
    ordem = db.Column(db.Integer, default=0)
    # liga o item a uma verificacao automatica (ver app/verificacao.py); vazia = manual
    chave = db.Column(db.String(40), default="")

    processo = db.relationship("Processo", back_populates="requisitos")

    @property
    def avaliacao(self):
        """O que o sistema consegue apurar sozinho. None quando o item e manual."""
        from . import verificacao
        return verificacao.avaliar(self.processo, self.chave)

    @property
    def automatico(self):
        return bool(self.chave)

    @property
    def bloqueia_pacote(self):
        """Só documentação trava o envio à OCD; o resto é acompanhamento interno."""
        return self.obrigatorio and self.categoria in CATEGORIAS_DO_PACOTE

    @property
    def resolvido(self):
        """Marcado a mao OU comprovado pelo proprio sistema."""
        if self.status in STATUS_RESOLVIDOS:
            return True
        aval = self.avaliacao
        return bool(aval and aval["ok"])

    @property
    def status_exibido(self):
        if self.status in STATUS_RESOLVIDOS:
            return self.status
        aval = self.avaliacao
        if aval and aval["ok"]:
            return "Recebido"
        return self.status

    @property
    def cor(self):
        return STATUS_REQUISITO_CORES.get(self.status_exibido, "off")


# ---------------------------------------------------------------- documentos

class TemplateDocumento(db.Model):
    """Texto padrao das declaracoes. Aceita placeholders Jinja: {{ produto.modelo }}."""
    __tablename__ = "template_documento"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(40), nullable=False, index=True)
    nome = db.Column(db.String(160), nullable=False)
    titulo = db.Column(db.String(200), default="")
    corpo = db.Column(db.Text, default="")
    ativo = db.Column(db.Boolean, default=True)
    versao = db.Column(db.String(20), default="1.0")
    observacoes = db.Column(db.Text, default="")
    # alguns formulários (ex.: segurança cibernética) já trazem os dados do representante
    # no próprio texto; nesses casos o bloco automático é dispensado
    bloco_responsavel = db.Column(db.Boolean, default=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __str__(self):
        return self.nome


class Documento(db.Model):
    __tablename__ = "documento"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("template_documento.id"))
    signatario_id = db.Column(db.Integer, db.ForeignKey("signatario.id"))
    tipo = db.Column(db.String(40), nullable=False)
    titulo = db.Column(db.String(200), default="")
    corpo = db.Column(db.Text, default="")          # texto final ja renderizado
    cidade = db.Column(db.String(120), default="")
    data_documento = db.Column(db.Date, default=date.today)
    versao = db.Column(db.Integer, default=1)
    arquivo_docx = db.Column(db.String(255), default="")
    arquivo_pdf = db.Column(db.String(255), default="")     # e o que vai para a OCD
    criado_em = db.Column(db.DateTime, default=datetime.now)

    processo = db.relationship("Processo", back_populates="documentos")
    template = db.relationship("TemplateDocumento")
    signatario = db.relationship("Signatario")

    @property
    def paragrafos(self):
        return [p.rstrip() for p in (self.corpo or "").split("\n\n") if p.strip()]


# ---------------------------------------------------------------- fotos

class Vista(db.Model):
    """Catalogo de vistas fotograficas exigidas pelo OCD."""
    __tablename__ = "vista"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(40), unique=True, nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    grupo = db.Column(db.String(60), default="Externas")
    descricao = db.Column(db.Text, default="")
    dica = db.Column(db.Text, default="")
    obrigatoria = db.Column(db.Boolean, default=True)
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    # marcada ao editar pela tela: impede que a carga inicial sobrescreva o seu texto
    personalizada = db.Column(db.Boolean, default=False)

    def __str__(self):
        return self.nome


class VistaProcesso(db.Model):
    """Ajuste do roteiro de fotos para UM processo especifico.

    Serve para marcar uma vista como nao aplicavel (ex.: produto sem acessorios, placa sem
    blindagem). A vista deixa de ser cobrada nas pendencias e no pacote da OCD.
    """
    __tablename__ = "vista_processo"
    __table_args__ = (db.UniqueConstraint("processo_id", "vista_id", name="uq_vista_processo"),)
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    vista_id = db.Column(db.Integer, db.ForeignKey("vista.id"), nullable=False)
    nao_aplicavel = db.Column(db.Boolean, default=False)
    motivo = db.Column(db.String(255), default="")
    criado_em = db.Column(db.DateTime, default=datetime.now)

    processo = db.relationship("Processo", back_populates="ajustes_vista")
    vista = db.relationship("Vista")


class Foto(db.Model):
    __tablename__ = "foto"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    vista_id = db.Column(db.Integer, db.ForeignKey("vista.id"))
    arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), default="")
    legenda = db.Column(db.String(255), default="")
    largura = db.Column(db.Integer)
    altura = db.Column(db.Integer)
    tamanho = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    # --- vistoria da foto (app/vistoria.py). Fica guardado para a ficha poder
    # mostrar depois por que uma foto passou ou o que ela tinha de ressalva.
    conferida_em = db.Column(db.DateTime)
    aprovada = db.Column(db.Boolean)              # None = nunca conferida
    veredito = db.Column(db.String(255), default="")
    analise_json = db.Column(db.Text, default="")
    impressao = db.Column(db.String(32), default="")   # dHash, pega foto repetida
    origem = db.Column(db.String(20), default="tela")  # tela | celular

    processo = db.relationship("Processo", back_populates="fotos")
    vista = db.relationship("Vista")

    @property
    def analise(self):
        from .vistoria import de_json
        return de_json(self.analise_json)

    @property
    def avisos(self):
        return [p for p in self.analise.get("problemas", [])
                if p.get("gravidade") == "aviso"]


class Anexo(db.Model):
    __tablename__ = "anexo"
    id = db.Column(db.Integer, primary_key=True)
    processo_id = db.Column(db.Integer, db.ForeignKey("processo.id"), nullable=False)
    categoria = db.Column(db.String(80), default="Outros", index=True)
    titulo = db.Column(db.String(200), default="")
    arquivo = db.Column(db.String(255), nullable=False)
    nome_original = db.Column(db.String(255), default="")
    tamanho = db.Column(db.Integer)
    numero_documento = db.Column(db.String(80), default="")
    valor = db.Column(db.Float)
    emissao = db.Column(db.Date)
    vencimento = db.Column(db.Date)
    observacao = db.Column(db.Text, default="")
    criado_em = db.Column(db.DateTime, default=datetime.now)

    processo = db.relationship("Processo", back_populates="anexos")
