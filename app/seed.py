"""Carga inicial do banco: dados da empresa, OCDs, laboratorios, vistas de fotos,
templates das declaracoes e a base de homologacoes vinda da planilha original.

Roda uma unica vez (apenas quando a tabela correspondente esta vazia).
"""
from datetime import date, datetime

from .extensions import db
from .models import (Empresa, Fabricante, Homologacao, HomologacaoModelo, Laboratorio, OCD,
                     Produto, Signatario, TemplateDocumento, Vista)

# --------------------------------------------------------------------- vistas

VISTAS = [
    ("frontal", "Vista frontal", "Externas",
     "Face frontal completa, produto centralizado, fundo neutro e a régua ao lado.",
     "Sem reflexo e sem sombra sobre o display. É desta foto que a OCD tira a Largura x Altura.",
     True, 10),
    ("traseira", "Vista traseira", "Externas",
     "Face traseira completa, mostrando etiqueta, parafusos e furação de fixação, "
     "com a régua ao lado.",
     "Se a etiqueta estiver aqui, ela precisa estar legível nesta foto ou em foto dedicada.",
     True, 20),
    ("superior", "Vista superior", "Externas",
     "Topo do equipamento, câmera perpendicular à face, com a régua ao lado.", "", True, 30),
    ("inferior", "Vista inferior / base", "Externas",
     "Base do equipamento, com a régua ao lado. Normalmente onde fica a etiqueta de "
     "identificação.", "", True, 40),
    ("lateral_esquerda", "Lateral esquerda", "Externas",
     "Lateral esquerda completa, com conectores visíveis e a régua ao lado.", "", True, 50),
    ("lateral_direita", "Lateral direita", "Externas",
     "Lateral direita completa, com conectores visíveis e a régua ao lado.",
     "É desta foto que sai a Profundidade — junto com a frontal, fecha o L x A x P exigido.",
     True, 60),
    ("selo_anatel", "Identificação e Selo Anatel", "Identificação",
     "Identificação no produto contendo: Modelo (não pode ser nome comercial), "
     "Rastreabilidade, País de Origem, Marca do Fabricante ou Fabricante e o Selo Anatel "
     "(opções do Ato nº 4088). Enquadre de forma que dê para ler tudo E dê para ver onde a "
     "etiqueta fica aplicada no produto, com a régua ao lado.",
     "É o item que a OCD mais reprova. Se o módulo tiver marcação FCC ou CE, é MANDATÓRIO "
     "constar também o Selo Anatel. Sem reflexo, sem corte, texto nítido — e a rastreabilidade "
     "precisa bater exatamente com a Declaração de Rastreabilidade.", True, 80),

    ("placas_na_carcaca", "Placas dentro da carcaça", "Internas",
     "Placas completas dentro da carcaça do produto, mostrando a montagem, com a régua ao lado.",
     "Exigência literal da OCP-Teli: “das placas completas dentro da carcaça do produto”.",
     True, 110),
    ("pci_componentes", "Placas - frente (com e sem blindagem)", "Internas",
     "TODAS as placas do produto, lado dos componentes, fora do gabinete, com a régua ao lado. "
     "Envie o par: uma foto COM a blindagem montada e outra SEM a blindagem.",
     "Dois erros clássicos: fotografar só a placa principal e esquecer de retirar a blindagem "
     "DOS MÓDULOS. A régua entra nas duas fotos.", True, 120),
    ("pci_solda", "Placas - verso (com e sem blindagem)", "Internas",
     "Verso de TODAS as placas (trilhas / pontos de solda), com a régua ao lado. Se houver "
     "blindagem neste lado, envie também o par com e sem.",
     "Mesmas placas da foto anterior, viradas.", True, 130),
    ("modulo_rf", "Módulo / circuito de RF", "Internas",
     "Detalhe do circuito de RF: blindagem, cristal e trilha da antena, com a régua ao lado.",
     "Só é necessária quando o produto usa módulo homologado — nesse caso a etiqueta do "
     "módulo precisa aparecer legível (modelo e nº de homologação do módulo).", False, 140),
    ("antena", "Antena e conector", "Internas",
     "Antena(s) do produto e o conector utilizado, com a régua ao lado. Informar tipo e ganho.",
     "Antena removível exige foto separada da antena e do conector.", False, 150),

    ("acessorios", "Acessórios e fonte de alimentação", "Acessórios",
     "Acessórios vendidos junto ao produto, com a régua ao lado: fonte de alimentação, fone de "
     "ouvido, microfone, receptores etc. Na fonte externa, a marcação com os valores nominais "
     "de tensão, corrente e/ou potência e frequência precisa estar legível.",
     "Cada acessório precisa de etiqueta de identificação quando houver variações. Se o "
     "produto for vendido sem nenhum acessório, marque esta vista como N/A.", True, 160),
]

# ---------------------------------------------------------------- declaracoes

BLOCO_DESTINATARIO_OCD = """À(o)
{{ ocd.razao_social or ocd.nome }}
{{ ocd.endereco }}
{{ ocd.cidade }} - {{ ocd.uf }}"""

T_RASTREABILIDADE = """À(o)
ANATEL – Agência Nacional de Telecomunicações
SAS – Quadra 6 – Bloco H – 4º andar - RFCEC – CEP: 70070-940
Brasília – DF

At. Gerência de Certificação
Assunto: Rastreabilidade de Amostra

Modelo(s): {{ modelos }}

Prezados Senhores,

Declaramos para os devidos fins, que:

• O Solicitante da certificação é:
{{ empresa.razao_social }}
{{ empresa.cnpj }}
{{ empresa.endereco }} - {{ empresa.bairro }}
{{ empresa.cidade }}/{{ empresa.uf }} - CEP: {{ empresa.cep }}

• O detentor da tecnologia e Fabricante do produto, unidade fabril onde a amostra foi \
produzida, é:
{{ fabricante.razao_social or fabricante.nome }}
{{ fabricante.endereco_completo }}
{% if fabricante.pais %}
País de origem: {{ fabricante.pais }}
{% endif %}
Este é o nome que consta na etiqueta de identificação da amostra.

• A rastreabilidade da(s) amostra(s) encaminhada para ensaios pode ser verificada por UM ou \
mais de um dos dados já identificados na(s) amostra(s) abaixo:

{% for nome, marcado, valor in rastreabilidade %}
{{ marcar(marcado) }}  {{ nome }}: {{ valor }}
{% endfor %}"""

# Textos que sairam DE FABRICA em versoes anteriores.
#
# A palavra "Fabricante" ja nomeou dois papeis diferentes aqui, e o OCD perguntou
# qual valia. Pela resposta do OCP-TELI: a ZKTeco do Brasil e SOMENTE a
# solicitante; detentor da tecnologia e fabricante sao a ZKTeco Co., Ltda - que e
# o nome que sai na etiqueta da amostra.
#
# Quem estiver com um destes textos e atualizado sozinho; quem editou o proprio
# modelo fica como esta.
T_RASTREABILIDADE_ANTIGOS = (
    """À(o)
ANATEL – Agência Nacional de Telecomunicações
SAS – Quadra 6 – Bloco H – 4º andar - RFCEC – CEP: 70070-940
Brasília – DF

At. Gerência de Certificação
Assunto: Rastreabilidade de Amostra

Modelo(s): {{ modelos }}

Prezados Senhores,

Declaramos para os devidos fins, que:

• O Fabricante (detentor da tecnologia) do produto é:
{{ empresa.razao_social }}
{{ empresa.cnpj }}
{{ empresa.endereco }} - {{ empresa.bairro }}
{{ empresa.cidade }}/{{ empresa.uf }} - CEP: {{ empresa.cep }}

• A amostra enviada para ensaios foi produzida na unidade fabril:
{{ fabricante.razao_social or fabricante.nome }}
{{ fabricante.endereco_completo }}

• A rastreabilidade da(s) amostra(s) encaminhada para ensaios pode ser verificada por UM ou mais de um dos dados já identificados na(s) amostra(s) abaixo:

{% for nome, marcado, valor in rastreabilidade %}
{{ marcar(marcado) }}  {{ nome }}: {{ valor }}
{% endfor %}""",
    """À(o)
ANATEL – Agência Nacional de Telecomunicações
SAS – Quadra 6 – Bloco H – 4º andar - RFCEC – CEP: 70070-940
Brasília – DF

At. Gerência de Certificação
Assunto: Rastreabilidade de Amostra

Modelo(s): {{ modelos }}

Prezados Senhores,

Declaramos para os devidos fins, que:

• O Solicitante da certificação, detentor da tecnologia do produto, é:
{{ empresa.razao_social }}
{{ empresa.cnpj }}
{{ empresa.endereco }} - {{ empresa.bairro }}
{{ empresa.cidade }}/{{ empresa.uf }} - CEP: {{ empresa.cep }}

• O Fabricante do produto, unidade fabril onde a amostra foi produzida, é:
{{ fabricante.razao_social or fabricante.nome }}
{{ fabricante.endereco_completo }}
{% if fabricante.pais %}
País de origem: {{ fabricante.pais }}
{% endif %}
Este é o nome que consta na etiqueta de identificação da amostra.

• A rastreabilidade da(s) amostra(s) encaminhada para ensaios pode ser verificada por UM ou mais de um dos dados já identificados na(s) amostra(s) abaixo:

{% for nome, marcado, valor in rastreabilidade %}
{{ marcar(marcado) }}  {{ nome }}: {{ valor }}
{% endfor %}""",
)


T_SIMILARIDADE = """À(o)
{{ ocd.razao_social or ocd.nome }}
{{ ocd.endereco }}
{{ ocd.cidade }} - {{ ocd.uf }}

Assunto: Declaração de Similaridade

Modelos: {{ modelos }}
Fabricante: {{ fabricante.razao_social or fabricante.nome }}
Endereço: {{ fabricante.endereco_completo }}
Solicitante: {{ empresa.razao_social }}
CNPJ nº: {{ empresa.cnpj }}
Endereço: {{ empresa.endereco }} - {{ empresa.bairro }} - CEP {{ empresa.cep }} - \
{{ empresa.cidade }}/{{ empresa.uf }}

Prezados Senhores,

A empresa “{{ empresa.razao_social }}”, CNPJ nº: {{ empresa.cnpj }}, na qualidade de \
solicitante da certificação, vem através desta declarar que os modelos citados acima, \
fabricados por {{ fabricante.razao_social or fabricante.nome }}, possuem a mesma placa mãe, \
e diferem-se apenas {{ diferenca_pt }}, conforme pode ser visto no arquivo de fotos externas \
e/ou internas, dependendo do tipo de produto.

Declaramos ainda que, as fotos enviadas são as atuais do produto em questão.
---EN---
To
{{ ocd.razao_social or ocd.nome }}

Subject: Similarity Statement

Models: {{ modelos }}
Manufacturer: {{ fabricante.razao_social or fabricante.nome }}
Address: {{ fabricante.endereco_completo }}

Dear Sirs,

The company “{{ empresa.razao_social }}”, as applicant for certification, comes through this \
to declare that the models mentioned above, manufactured by \
{{ fabricante.razao_social or fabricante.nome }}, have the same mainboard, and differ \
{{ diferenca_en }}, as can be seen in the file of external and/or internal photos, depending \
on the product type.

We further declare that the photos sent are the current ones of the product in question."""

T_SIMILARIDADE_ANTIGOS = (
    """À(o)
{{ ocd.razao_social or ocd.nome }}
{{ ocd.endereco }}
{{ ocd.cidade }} - {{ ocd.uf }}

Assunto: Declaração de Similaridade

Modelos: {{ modelos }}
Fabricante: {{ empresa.razao_social }}
CNPJ nº: {{ empresa.cnpj }}
Endereço: {{ empresa.endereco }} - {{ empresa.bairro }} - CEP {{ empresa.cep }} - {{ empresa.cidade }}/{{ empresa.uf }}

Prezados Senhores,

A empresa “{{ empresa.razao_social }}”, CNPJ nº: {{ empresa.cnpj }}, na qualidade de fabricante dos produtos, modelos citados acima, vem através desta, declarar que os modelos possuem a mesma placa mãe, e diferem-se apenas {{ diferenca_pt }}, conforme pode ser visto no arquivo de fotos externas e/ou internas, dependendo do tipo de produto.

Declaramos ainda que, as fotos enviadas são as atuais do produto em questão.
---EN---
To
{{ ocd.razao_social or ocd.nome }}

Subject: Similarity Statement

Models: {{ modelos }}
Manufacturer: {{ fabricante.razao_social or fabricante.nome }}
Address: {{ fabricante.endereco_completo }}

Dear Sirs,

The company “{{ empresa.razao_social }}”, as manufacturer of the products, models mentioned above, comes through this, declare that the models have the same mainboard, and differ {{ diferenca_en }}, as can be seen in the file of external and/or internal photos, depending on the product type.

We further declare that the photos sent are the current ones of the product in question.""",
)


T_DIREITOS = """À(o)
{{ ocd.razao_social or ocd.nome }}
{{ ocd.endereco }}
{{ ocd.cidade }} - {{ ocd.uf }}

Assunto: Declaração dos Direitos e Garantias do Consumidor

Modelo(s): {{ modelos }}

Prezados Senhores,

Declaramos que nos comprometemos a cumprir as obrigações de observar os direitos e garantias \
do consumidor previstos na legislação brasileira, em especial quanto ao fornecimento de \
informações sobre as características do produto, a garantia contra defeitos e a assistência \
técnica em todo o território nacional, conforme abaixo:

1) Garantir o fornecimento de peças de reposição durante {{ meses_garantia }} meses após o \
fornecimento do produto;
2) Garantir o produto durante {{ meses_garantia }} meses após o fornecimento do produto; e
3) Prestar serviço de manutenção e assistência técnica no país durante {{ meses_garantia }} \
meses após o fornecimento do produto.

Dados Gerais da Assistência Técnica:
Razão Social: {{ empresa.razao_social }}
CNPJ: {{ empresa.cnpj }}
Endereço: {{ empresa.endereco }} - {{ empresa.bairro }} - CEP {{ empresa.cep }} - \
{{ empresa.cidade }}/{{ empresa.uf }}
Telefone: {{ empresa.telefone }}"""

T_MANUTENCAO = """À(o)
{{ ocd.razao_social or ocd.nome }}
{{ ocd.endereco }}
{{ ocd.cidade }} - {{ ocd.uf }}

Referência: {{ processo.referencia_ocd }}
Modelo(s) do(s) produto(s): {{ modelos }}

Vimos pelo presente informar, para efeito de Manutenção do Certificado de Conformidade, que \
o(s) produto(s) informado(s) no referido certificado:

·  Continua(m) sendo comercializado(s) no Brasil;
·  Continua(m) sendo fabricado(s) na(s) mesma(s) unidade(s) fabri(l/s) prevista(s) na certificação;
·  Não sofre(u/ram) alteração no(s) processo(s) fabri(l/s);
·  Não sofre(u/ram) alteração no(s) projeto(s) do(s) equipamento(s).

A rastreabilidade do modelo referenciado acima pode ser verificada por um ou mais dados, \
identificado(s) no(s) produto(s):

{% for nome, marcado, valor in rastreabilidade %}
{{ marcar(marcado) }}  {{ nome }}: {{ valor }}
{% endfor %}

Nome do Fabricante: {{ fabricante.razao_social or fabricante.nome }}"""

T_CIBER = """A {{ empresa.razao_social }}, requerente à homologação do equipamento para \
telecomunicações de marca {{ empresa.marca }} e modelos {{ modelos }} declara que o referido \
equipamento está em conformidade com os seguintes requisitos de segurança cibernética \
relacionados nos itens 4 e 5 do anexo ao Ato nº 77, de 05 de janeiro de 2021.

Instruções de preenchimento:

1. O requerente à homologação do produto para telecomunicação deve preencher as tabelas desta \
declaração conforme a seguinte codificação:

C — O equipamento apresenta conformidade ao requisito.
NA — O requisito não se aplica ao equipamento, devido as suas características. Justificativa \
deverá ser apresentada.

2. Em atendimento ao item 4.1.2 dos requisitos, caso o equipamento sob homologação se \
enquadrar na definição de Customer Premise Equipment (CPE), a tabela do Anexo 1 ao documento \
referenciado no item 2.5 dos requisitos (LAC-BCOP-1 (May/2019) – Best Current Operational \
Practices on Minimum Security Requirements for Customer Premises Equipment (CPE) Acquisition) \
deverá ser preenchida, assinada e anexada a esta declaração.

---REQUISITOS---

A requerente está ciente de que o produto sob homologação poderá estar sujeito ao programa de \
Supervisão de Mercado da Anatel, a qualquer tempo, para fins de comprovação de que o produto \
homologado e seu fornecedor estão em conformidade com os itens assinalados nesta declaração. \
Adicionalmente, tem conhecimento que quaisquer falhas de segurança cibernética identificadas \
em equipamentos homologados que afetem a segurança de seus usuários, prestadoras ou das redes \
de telecomunicações do país podem ser objeto de avaliação pela Anatel, ainda que a \
característica afetada não tenha sido objeto da presente declaração.

Por fim, declara ter conhecimento integral dos termos do anexo ao Ato nº 77, de 05 de janeiro \
de 2021 e de que os requisitos de segurança cibernética publicados pela Agência Nacional de \
Telecomunicações estão sujeitos a atualizações, inclusive normativas e administrativas, em \
compasso com o desenvolvimento tecnológico e com o surgimento de novas ameaças ou \
vulnerabilidades.

Razão social: {{ empresa.razao_social }}
CNPJ: {{ empresa.cnpj }}
Nome do representante legalmente habilitado: {{ signatario.nome|upper }}
Cargo: {{ signatario.cargo }}"""

T_OUTROS = """{}

Assunto: {{ assunto }}

Modelo(s): {{ modelos }}

Prezados Senhores,

[escreva aqui o conteúdo da declaração]""".format(BLOCO_DESTINATARIO_OCD)

TEMPLATES = [
    dict(tipo="rastreabilidade", nome="Declaração de Rastreabilidade - padrão ZKTeco",
         titulo="Declaração de Rastreabilidade", corpo=T_RASTREABILIDADE,
         observacoes="Endereçada à ANATEL. Marque os dados de rastreabilidade na aba "
                     "Rastreabilidade do processo antes de gerar."),
    dict(tipo="similaridade", nome="Declaração de Similaridade - bilíngue PT/EN",
         titulo="Declaração de Similaridade / Similarity Statement", corpo=T_SIMILARIDADE,
         observacoes="Documento bilíngue: o separador ---EN--- divide as colunas português "
                     "e inglês no .docx. Cadastre os modelos similares antes de gerar."),
    dict(tipo="direitos_garantia",
         nome="Declaração dos Direitos e Garantias do Consumidor",
         titulo="Declaração dos Direitos e Garantias do Consumidor", corpo=T_DIREITOS,
         observacoes="Prazo de garantia vem do cadastro da empresa (padrão 12 meses)."),
    dict(tipo="seguranca_cibernetica",
         nome="Declaração de Segurança Cibernética (Ato 77/2021) - formulário oficial",
         titulo="DECLARAÇÃO DE ATENDIMENTO AOS REQUISITOS DE SEGURANÇA CIBERNÉTICA PARA "
                "EQUIPAMENTOS PARA TELECOMUNICAÇÕES",
         corpo=T_CIBER, bloco_responsavel=False,
         observacoes="Formulário do Ato nº 77/2021 com os 43 requisitos. O marcador "
                     "---REQUISITOS--- é substituído pela tabela C / NA preenchida na aba "
                     "Segurança cibernética do processo."),
    dict(tipo="manutencao", nome="Declaração de Manutenção - padrão ZKTeco",
         titulo="Declaração de Manutenção", corpo=T_MANUTENCAO,
         observacoes="Usada na renovação. Preencha a Referência OCD (ex.: OCP 69124) no "
                     "processo."),
    dict(tipo="outros", nome="Modelo em branco", titulo="Declaração", corpo=T_OUTROS,
         observacoes="Base para qualquer documento novo que a OCD solicitar."),
]


# ------------------------------------------------------------------- execucao

def _empresa():
    if Empresa.query.get(1):
        return
    db.session.add(Empresa(
        id=1,
        razao_social="ZKTECO DO BRASIL S.A.",
        nome_fantasia="ZKTeco do Brasil",
        cnpj="08.057.340/0001-60",
        endereco="Rua Maria Martins, 11 - Galpão 01 – Área 01",
        bairro="Bairro Juliana",
        cidade="Belo Horizonte",
        uf="MG",
        cep="31.744-590",
        telefone="+55 (31) 3055-3530",
        email="produtos.brasil@zkteco.com",
        site="www.zkteco.com.br",
        prazo_garantia="12 (doze) meses",
        cidade_assinatura="Belo Horizonte",
    ))


def _signatario():
    if Signatario.query.count():
        return
    db.session.add(Signatario(
        nome="Juliano Torres Rezende",
        cargo="Gerente Técnico",
        email="produtos.brasil@zkteco.com",
        email_alternativo="juliano.torres@zkteco.com",
        telefone="(31) 99655-9489 / (31) 3055-3530",
        padrao=True,
    ))


def _ocds():
    if OCD.query.count():
        return
    db.session.add_all([
        OCD(nome="OCP-Teli",
            razao_social="OCP-TELI – Organização Certificadora de Produtos de "
                         "Telecomunicações e Informática",
            endereco="Av. Afonso Pena, nº 3924 – cnpj. 608 – Cruzeiro – 30.130-009",
            cidade="Belo Horizonte", uf="MG",
            observacoes="OCD utilizada na maioria dos processos. Código nas homologações: 12720."),
        OCD(nome="Eldorado",
            razao_social="Instituto de Pesquisas Eldorado",
            endereco="Av. Alan Turing, 275 - Cidade Universitária - CEP 13083-898",
            cidade="Campinas", uf="SP",
            observacoes="Certificados no padrão ELDxxxxx/aa."),
        OCD(nome="ICC", razao_social="ICC",
            observacoes="Completar razão social e endereço. Certificados no padrão "
                        "ICC nn.nnn/aaaa."),
    ])


def _laboratorios():
    if Laboratorio.query.count():
        return
    db.session.add_all([
        Laboratorio(nome="Eldorado", razao_social="Instituto de Pesquisas Eldorado",
                    endereco="Av. Alan Turing, 275 - Cidade Universitária - CEP 13083-898",
                    cidade="Campinas", uf="SP",
                    escopo="Ensaios de RF, EMC e segurança elétrica",
                    observacoes="Enviar a amostra com o número da proposta colado. "
                                "Necessárias 2 amostras: 01 comercial + 01 radiada."),
        Laboratorio(nome="ICC", razao_social="ICC",
                    observacoes="Completar dados de cadastro."),
    ])


def _fabricante():
    if Fabricante.query.count():
        return
    db.session.add(Fabricante(
        nome="ZKTECO CO., LTDA.",
        razao_social="ZKTECO CO., LTDA.",
        endereco="No. 32, Pingshan Industry Zone, Tangxia Town, Dongguan City, "
                 "Guangdong Province, China.",
        cidade="Dongguan",
        pais="China",
        observacoes="Unidade fabril declarada na Declaração de Rastreabilidade.",
    ))


def _checklist():
    """Carga inicial do checklist da OCD. Nao mexe no que voce ja ajustou.

    As listas do codigo (CHECKLIST_NOVO / CHECKLIST_RENOVACAO) sao a semente; a
    partir daqui quem manda e a tabela, editavel pela tela.
    """
    from .models import CHECKLIST_NOVO, CHECKLIST_RENOVACAO, ItemChecklist
    if ItemChecklist.query.count():
        return
    novos = {(c, d): (det, obr, ch)
             for c, d, det, obr, ch in CHECKLIST_NOVO}
    renovacao = {(c, d): (det, obr, ch)
                 for c, d, det, obr, ch in CHECKLIST_RENOVACAO}
    ordem = 0
    vistos = set()
    for chave_item in list(novos) + [k for k in renovacao if k not in novos]:
        detalhe, obrigatorio, chave = novos.get(chave_item) or renovacao[chave_item]
        if chave_item in novos and chave_item in renovacao:
            escopo = "ambos"
        elif chave_item in novos:
            escopo = "novo"
        else:
            escopo = "renovacao"
        if chave_item in vistos:
            continue
        vistos.add(chave_item)
        ordem += 10
        db.session.add(ItemChecklist(
            categoria=chave_item[0], descricao=chave_item[1], detalhe=detalhe or "",
            obrigatorio=obrigatorio, chave=chave or "", escopo=escopo, ordem=ordem))


def _categorias_de_anexo():
    """Carga inicial das categorias de anexo, na ordem que estava no codigo."""
    from .models import CATEGORIAS_ANEXO, CategoriaAnexo
    existentes = {c.nome for c in CategoriaAnexo.query.all()}
    ordem = (max([c.ordem or 0 for c in CategoriaAnexo.query.all()] or [0]))
    for nome in CATEGORIAS_ANEXO:
        if nome in existentes:
            continue
        ordem += 10
        db.session.add(CategoriaAnexo(nome=nome, ordem=ordem))


def _status():
    """Carga inicial das situacoes do processo. Nao mexe no que voce ja ajustou."""
    from . import cores
    from .models import STATUS_INICIAIS, StatusProcesso
    gravados = StatusProcesso.query.all()
    existentes = {s.nome for s in gravados}
    for nome, cor, ordem, exige, encerra in STATUS_INICIAIS:
        if nome not in existentes:
            db.session.add(StatusProcesso(nome=nome, cor=cor, ordem=ordem,
                                          exige_justificativa=exige, encerra=encerra))
    # O campo de cor era uma lista de nomes ("azul", "verde"...) e virou RGB.
    # Converte os cadastros antigos uma unica vez, mantendo a mesma aparencia.
    for s in gravados:
        if (s.cor or "").strip().lower() in cores.APELIDOS:
            s.cor = cores.APELIDOS[s.cor.strip().lower()]


def _vistas():
    """Insere as vistas que faltam e atualiza o texto das que voce nao editou.

    Uma vista salva pela tela fica marcada como personalizada e nunca mais e sobrescrita.
    """
    existentes = {v.codigo: v for v in Vista.query.all()}
    for codigo, nome, grupo, descricao, dica, obrigatoria, ordem in VISTAS:
        atual = existentes.get(codigo)
        if atual is None:
            db.session.add(Vista(codigo=codigo, nome=nome, grupo=grupo, descricao=descricao,
                                 dica=dica, obrigatoria=obrigatoria, ordem=ordem))
        elif not atual.personalizada:
            atual.nome = nome
            atual.grupo = grupo
            atual.descricao = descricao
            atual.dica = dica
            atual.obrigatoria = obrigatoria
            atual.ordem = ordem


def _corrigir_papeis():
    """Poe cada empresa no seu papel nos modelos de documento.

    O OCP-TELI esclareceu: a ZKTeco do Brasil e apenas a SOLICITANTE; detentor
    da tecnologia e fabricante sao a fabrica (ZKTeco Co., Ltda), que e o nome
    impresso na etiqueta da amostra. Os textos de fabrica antigos diziam outra
    coisa e geraram pergunta do OCD.

    So troca quem esta com um texto DE FABRICA. Modelo editado a mao fica como
    esta - mexer nele seria apagar o trabalho de alguem.
    """
    trocas = ((("rastreabilidade",), T_RASTREABILIDADE_ANTIGOS, T_RASTREABILIDADE),
              (("similaridade",), T_SIMILARIDADE_ANTIGOS, T_SIMILARIDADE))
    for tipos, antigos, novo in trocas:
        conhecidos = {texto.strip() for texto in antigos}
        for modelo in TemplateDocumento.query.filter(
                TemplateDocumento.tipo.in_(tipos)).all():
            if (modelo.corpo or "").strip() in conhecidos:
                modelo.corpo = novo


def _templates():
    """Insere os modelos que faltam. Nao sobrescreve o que voce editou."""
    existentes = {(t.tipo, t.nome) for t in TemplateDocumento.query.all()}
    tipos_existentes = {t.tipo for t in TemplateDocumento.query.all()}
    for dados in TEMPLATES:
        if (dados["tipo"], dados["nome"]) in existentes:
            continue
        # tipo ainda sem nenhum modelo, ou modelo novo do sistema: entra
        if dados["tipo"] not in tipos_existentes or "formulário oficial" in dados["nome"]:
            db.session.add(TemplateDocumento(**dados))


def _homologacoes():
    """Importa a base historica da aba ANATEL da planilha original."""
    if Homologacao.query.count():
        return
    try:
        from .dados_iniciais import HOMOLOGACOES
    except ImportError:
        return

    fabricante = Fabricante.query.first()
    ocds = {o.nome: o for o in OCD.query.all()}

    def ocd_do_certificado(cct):
        if cct.upper().startswith("ELD"):
            return ocds.get("Eldorado")
        if cct.upper().startswith("ICC"):
            return ocds.get("ICC")
        return ocds.get("OCP-Teli")

    for item in HOMOLOGACOES:
        validade = None
        if item.get("validade"):
            validade = datetime.strptime(item["validade"], "%Y-%m-%d").date()
        situacao = (item.get("situacao") or "").strip() or "Homologação Emitida"
        homologacao = Homologacao(
            numero=item["numero"],
            certificado=item["cct"],
            validade=validade,
            situacao=situacao,
            natureza=item.get("cat1") or "Produto acabado",
            tipo=item.get("cat2") or "",
            aplicacoes=item.get("aplicacoes") or "",
            renovar=bool(item.get("renovar")),
            ocd=ocd_do_certificado(item["cct"]),
            observacoes="Importado da planilha original.",
        )
        db.session.add(homologacao)
        for modelo in item["modelos"]:
            produto = Produto.query.filter_by(modelo=modelo).first()
            if not produto:
                produto = Produto(
                    modelo=modelo,
                    natureza=item.get("cat1") or "Produto acabado",
                    tipo_equipamento=item.get("cat2") or "",
                    fabricante=fabricante,
                    observacoes=("Aplicações: " + item["aplicacoes"])
                                if item.get("aplicacoes") else "",
                )
                db.session.add(produto)
            db.session.add(HomologacaoModelo(homologacao=homologacao, produto=produto,
                                             modelo=modelo))


# Itens que sairam do checklist do processo. CNPJ, contrato social e ISO passaram a ser
# documentos da empresa (valem para todos os processos, nao se reanexam a cada um).
ITENS_REMOVIDOS = [
    "Certificado ISO de Qualidade Fabril + Tradução Juramentada",
    "Certificado ISO 9001 válido + Tradução Juramentada",
    "Cartão CNPJ atual, emitido no site da Receita Federal",
    "Cópia do Contrato Social com a última alteração",
    "Frases obrigatórias inseridas no produto ou no manual",
]


def _limpar_itens_removidos():
    """Tira dos checklists ja criados os itens que nao fazem mais parte do roteiro."""
    from .models import Requisito
    antigos = Requisito.query.filter(Requisito.descricao.in_(ITENS_REMOVIDOS)).all()
    for requisito in antigos:
        db.session.delete(requisito)
    return len(antigos)


def _vai_apagar_algo():
    """Quantos registros as limpezas abaixo removeriam. Serve para decidir o backup."""
    from .models import Requisito
    itens = Requisito.query.filter(Requisito.descricao.in_(ITENS_REMOVIDOS)).count()
    oficial = TemplateDocumento.query.filter(
        TemplateDocumento.tipo == "seguranca_cibernetica",
        TemplateDocumento.corpo.like("%---REQUISITOS---%")).first()
    modelos = 0
    if oficial:
        modelos = TemplateDocumento.query.filter(
            TemplateDocumento.tipo == "seguranca_cibernetica",
            TemplateDocumento.id != oficial.id,
            ~TemplateDocumento.corpo.like("%---REQUISITOS---%")).count()
    return itens + modelos


def _remover_ciber_antigo():
    """Apaga o modelo de segurança cibernética anterior ao formulário oficial.

    O texto antigo era um resumo do Ato 77 e foi substituido pelo formulario oficial (com
    os 43 requisitos C / NA). Os documentos ja emitidos com ele nao se perdem: guardam o
    proprio texto; so deixam de apontar para um modelo.
    """
    from .models import Documento
    oficial = TemplateDocumento.query.filter(
        TemplateDocumento.tipo == "seguranca_cibernetica",
        TemplateDocumento.corpo.like("%---REQUISITOS---%")).first()
    if not oficial:
        return
    antigos = TemplateDocumento.query.filter(
        TemplateDocumento.tipo == "seguranca_cibernetica",
        TemplateDocumento.id != oficial.id,
        ~TemplateDocumento.corpo.like("%---REQUISITOS---%")).all()
    for t in antigos:
        Documento.query.filter_by(template_id=t.id).update({"template_id": None})
        db.session.delete(t)


def _chaves_do_checklist():
    """Liga os itens de checklist ja existentes a sua verificacao automatica.

    Processos criados antes desta funcionalidade tinham checklist 100% manual: os itens
    ficavam "Pendente" mesmo com o anexo/documento no lugar. Aqui a ligacao e feita pela
    descricao, uma unica vez por item.
    """
    from .models import ItemChecklist, Requisito
    # o cadastro e a fonte: ele nasce das listas do codigo e pode ter suas edicoes
    mapa = {i.descricao: i.chave for i in ItemChecklist.query.all() if i.chave}
    if not mapa:
        return
    pendentes = Requisito.query.filter(
        (Requisito.chave.is_(None)) | (Requisito.chave == "")).all()
    for requisito in pendentes:
        chave = mapa.get(requisito.descricao)
        if chave:
            requisito.chave = chave


def executar():
    """Popula apenas o que ainda estiver vazio. Nunca sobrescreve dados existentes.

    As tabelas ja foram criadas/atualizadas por manutencao.preparar().
    """
    _empresa()
    _signatario()
    _ocds()
    _laboratorios()
    _fabricante()
    _status()
    _checklist()
    _categorias_de_anexo()
    _vistas()
    _templates()
    _corrigir_papeis()
    db.session.flush()
    _homologacoes()
    # As limpezas abaixo APAGAM registros de processos que ja existem. Se houver algo a
    # apagar, uma copia de seguranca e feita antes — a atualizacao de esquema ja faz a dela,
    # mas uma limpeza pode acontecer sem nenhuma mudanca de estrutura.
    if _vai_apagar_algo():
        from flask import current_app
        from . import manutencao
        copia = manutencao.fazer_backup(current_app, "antes-de-limpar")
        if copia:
            print(f"[banco] cópia de segurança antes da limpeza: {copia.name}")
    _limpar_itens_removidos()
    _remover_ciber_antigo()
    _chaves_do_checklist()
    db.session.commit()
