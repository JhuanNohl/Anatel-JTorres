"""Catalogo dos requisitos de seguranca cibernetica do Ato nº 77/2021 (itens 4, 5 e 6).

Transcricao do formulario que a OCD exige. Cada item e marcado por processo como:
    C  = o equipamento apresenta conformidade ao requisito
    NA = o requisito nao se aplica ao equipamento (exige justificativa)

Os textos ficam GRAVADOS em cada processo quando o questionario e criado. Assim, se o Ato
mudar e este catalogo for atualizado, as declaracoes ja emitidas continuam com o texto
exato que foi assinado.
"""

TITULO_5 = ("5.1. Requisitos para equipamentos terminais que se conectam à Internet e para "
            "equipamentos de infraestrutura de redes de telecomunicações, em suas versões "
            "finais destinadas à comercialização:")
TITULO_6 = ("6.1. Requisitos para fornecedores de equipamentos terminais que se conectam à "
            "Internet e de equipamentos de infraestrutura de redes de telecomunicações:")

# (codigo, titulo, secao, texto)
REQUISITOS = [
    ("4.1.a)", "", "",
     "O produto foi desenvolvido em observância ao princípio de security by design."),

    ("a)", TITULO_5, "5.1.1. Quanto à atualização de software/firmware:",
     "Possuir mecanismos automatizados e seguros para atualização de software/firmware que "
     "empregam métodos adequados de criptografia, autenticação e verificação de integridade."),
    ("b)", TITULO_5, "5.1.1. Quanto à atualização de software/firmware:",
     "Permitir que os usuários verifiquem, de forma manual, a disponibilidade de atualizações "
     "de software/firmware e as implementem facilmente."),
    ("c)", TITULO_5, "5.1.1. Quanto à atualização de software/firmware:",
     "Possuir mecanismos para informar ao usuário as alterações de software/firmware "
     "implementadas devido às atualizações, especialmente aquelas relacionadas à segurança."),
    ("d)", TITULO_5, "5.1.1. Quanto à atualização de software/firmware:",
     "Preservar as configurações existentes no equipamento após finalizado o procedimento de "
     "atualização. Alterações na configuração dos equipamentos podem ser implementadas no "
     "processo de atualização somente se resultarem em melhorias na segurança do dispositivo."),

    ("a)", TITULO_5, "5.1.2. Quanto ao gerenciamento remoto:",
     "Possuir mecanismo para gerenciamento e administração remotos que empreguem métodos "
     "adequados de autenticação e criptografia."),
    ("b)", TITULO_5, "5.1.2. Quanto ao gerenciamento remoto:",
     "Implementar mecanismos de controle de acesso às interfaces de gerenciamento e "
     "administração remotos, de tal forma a limitar o acesso quanto à origem (por exemplo, "
     "segmento de rede específico, URL selecionada, etc.)."),

    ("a)", TITULO_5, "5.1.3. Quanto à instalação e à operação:",
     "Implementar rotinas simplificadas adequadas para sua instalação e configuração, evitando "
     "potenciais falhas de segurança não intencionais."),
    ("b)", TITULO_5, "5.1.3. Quanto à instalação e à operação:",
     "Por padrão de fábrica, o dispositivo deve ser configurado de forma restritiva ao invés de "
     "forma permissiva. A seleção de parâmetros para as configurações iniciais de fábrica deve "
     "primar por opções nativamente seguras, alinhadas aos princípios de segurança e "
     "privacidade."),
    ("c)", TITULO_5, "5.1.3. Quanto à instalação e à operação:",
     "Realizar verificação da integridade do software/firmware durante a inicialização do "
     "sistema, sendo capaz de alertar ao usuário nos casos de comprometimento de sua "
     "integridade."),
    ("d)", TITULO_5, "5.1.3. Quanto à instalação e à operação:",
     "Possuir mecanismo de monitoramento de comportamentos não usuais do software/firmware, "
     "alertando o usuário ou reiniciando-se automaticamente caso um comportamento suspeito "
     "seja detectado. Após reinicialização deverá ser ofertada ao usuário a opção de "
     "restauração do equipamento aos padrões de fábrica."),
    ("e)", TITULO_5, "5.1.3. Quanto à instalação e à operação:",
     "Implementar ferramenta de registro de atividades (logs) relacionadas à, no mínimo, "
     "autenticação de usuários, alteração de configurações do sistema e funcionamento do "
     "sistema."),
    ("f)", TITULO_5, "5.1.3. Quanto à instalação e à operação:",
     "Fornecer documentação que descreva, no mínimo, o nome, a versão e as funcionalidades do "
     "software/firmware e/ou sistema operacional, bem como nome completo e versão de cada "
     "software de código aberto incorporado ao sistema. A documentação pode ser em formato "
     "eletrônico."),

    ("a)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Não utilizar credenciais e senhas iniciais para acesso às suas configurações que sejam "
     "iguais entre todos os dispositivos produzidos."),
    ("b)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Não utilizar senhas iniciais que sejam derivadas de informações de fácil obtenção por "
     "métodos de escaneamento de tráfego de dados em rede, tal com endereços MAC - Media "
     "Access Control."),
    ("c)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Forçar, na primeira utilização, a alteração da senha inicial de acesso à configuração do "
     "equipamento."),
    ("d)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Não permitir o uso de senhas em branco ou senhas fracas."),
    ("e)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Possuir mecanismos de defesa contra tentativas exaustivas de acesso não autorizado "
     "(ataques de autenticação por força bruta)."),
    ("f)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Garantir que os mecanismos de recuperação de senha sejam robustos contra tentativas de "
     "roubo de credenciais."),
    ("g)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Não utilizar credenciais, senhas e chaves criptográficas definidas no próprio código "
     "fonte do software/firmware e que não podem ser alteradas (hard-coded)."),
    ("h)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Proteger senhas, chaves de acesso e credenciais armazenadas ou transmitidas utilizando "
     "métodos adequados de criptografia ou hashing."),
    ("i)", TITULO_5, "5.1.4. Quanto ao acesso para configuração do equipamento:",
     "Implementar rotinas de encerramento de sessões inativas (timeout)."),

    ("a)", TITULO_5, "5.1.5. Quanto aos serviços de comunicação de dados:",
     "Estar desprovido de qualquer ferramenta de teste ou backdoor utilizados nos processos de "
     "desenvolvimento do produto e desnecessários à sua operação usual."),
    ("b)", TITULO_5, "5.1.5. Quanto aos serviços de comunicação de dados:",
     "Estar desprovido de qualquer forma de comunicação não documentada, incluindo aquelas "
     "para envio de informações de perfil de uso do equipamento para fabricantes ou para "
     "terceiros."),
    ("c)", TITULO_5, "5.1.5. Quanto aos serviços de comunicação de dados:",
     "Ser fornecido com serviços de comunicação de dados (serviço associado a uma porta/port) "
     "não usualmente utilizados desabilitados, reduzindo sua superfície de ataque."),
    ("d)", TITULO_5, "5.1.5. Quanto aos serviços de comunicação de dados:",
     "Facultar ao usuário a possibilidade de desabilitar funcionalidades e serviços de "
     "comunicação não essenciais à operação ou ao gerenciamento do equipamento."),

    ("a)", TITULO_5,
     "5.1.6. Quanto aos dados pessoais e dados pessoais sensíveis, observada a legislação "
     "vigente:",
     "Possibilitar a utilização de métodos adequados de criptografia para a transmissão de "
     "dados sensíveis, incluindo informações pessoais."),
    ("b)", TITULO_5,
     "5.1.6. Quanto aos dados pessoais e dados pessoais sensíveis, observada a legislação "
     "vigente:",
     "Possibilitar a utilização de métodos adequados de criptografia para o armazenamento de "
     "dados sensíveis, incluindo informações pessoais."),
    ("c)", TITULO_5,
     "5.1.6. Quanto aos dados pessoais e dados pessoais sensíveis, observada a legislação "
     "vigente:",
     "Permitir que os usuários deletem facilmente seus dados pessoais e sensíveis armazenados, "
     "possibilitando o descarte ou a substituição do equipamento sem riscos de exposição de "
     "informações pessoais."),
    ("d)", TITULO_5,
     "5.1.6. Quanto aos dados pessoais e dados pessoais sensíveis, observada a legislação "
     "vigente:",
     "Conter em sua documentação informações ao usuário sobre quais dados pessoais, sensíveis "
     "ou não, são coletados, utilizados e armazenados."),

    ("a)", TITULO_5, "5.1.7. Quanto à capacidade de mitigar ataques:",
     "Possuir mecanismo para limitação da taxa de transmissão de dados de saída (upload), além "
     "do usualmente necessário, a fim de minimizar sua utilização como vetor em ataques a "
     "outros equipamentos ou sistemas (ataque de negação de serviço)."),
    ("b)", TITULO_5, "5.1.7. Quanto à capacidade de mitigar ataques:",
     "Implementar mecanismos para validação do endereço de origem dos pacotes de dados, "
     "filtrando pacotes com endereço de origem falsificados (filtro antispoofing), em especial "
     "na transmissão de dados de saída (upload)."),
    ("c)", TITULO_5, "5.1.7. Quanto à capacidade de mitigar ataques:",
     "Ser projetado para mitigar os efeitos de ataques de negação de serviço em andamento, "
     "sendo resistentes a um número excessivo de tentativas de autenticação, por meio de, por "
     "exemplo: priorização de sua capacidade de processamento às sessões de comunicação já "
     "estabelecidas e autenticadas; e limitação do número de sessões de autenticação "
     "concorrentes, descartando tentativas de estabelecimento de novas sessões quando superado "
     "limite estabelecido."),

    ("6.1.1.", TITULO_6, "",
     "Possuir uma política clara de suporte ao produto, especialmente em relação à "
     "disponibilização de atualizações de software/firmware para correção de vulnerabilidades "
     "de segurança."),
    ("6.1.2.", TITULO_6, "",
     "Deixar claro para o consumidor até quando e em quais situações serão providas "
     "atualizações de segurança para o equipamento."),
    ("6.1.3.", TITULO_6, "",
     "Quando o equipamento dispuser de processos de atualização automática de "
     "software/firmware, garantir que as atualizações sejam realizadas em fases (em partes da "
     "totalidade de dispositivos) a fim de evitar que erros não intencionais da nova versão de "
     "software/firmware sejam distribuídos simultaneamente a todos os equipamentos passíveis "
     "de atualização."),
    ("6.1.4.", TITULO_6, "",
     "Garantir o provimento de atualizações de segurança por, no mínimo, 2 (dois) anos após o "
     "lançamento do produto ou enquanto o equipamento estiver sendo distribuído ao mercado "
     "consumidor, sendo aplicável a opção que mais se estender."),
    ("6.1.5.", TITULO_6, "",
     "Disponibilizar um canal de comunicação que possibilite aos seus clientes, usuários "
     "finais e terceiros reportarem vulnerabilidades de segurança identificadas nos produtos."),
    ("6.1.6.", TITULO_6, "",
     "Possuir implementados processos de Divulgação Coordenada de Vulnerabilidades baseados em "
     "boas práticas e recomendações reconhecidas internacionalmente."),

    ("a)", TITULO_6,
     "6.1.7. Disponibilizar um canal público de suporte, por meio de página na internet em "
     "língua portuguesa, para:",
     "Informar sobre novas vulnerabilidades identificadas em seus produtos, medidas de "
     "mitigação e correções de segurança associadas."),
    ("b)", TITULO_6,
     "6.1.7. Disponibilizar um canal público de suporte, por meio de página na internet em "
     "língua portuguesa, para:",
     "Manter histórico de: vulnerabilidades identificadas, medidas de mitigação e correções de "
     "segurança."),
    ("c)", TITULO_6,
     "6.1.7. Disponibilizar um canal público de suporte, por meio de página na internet em "
     "língua portuguesa, para:",
     "Permitir acesso a correções de segurança e/ou novas versões de software/firmware para "
     "seus produtos."),
    ("d)", TITULO_6,
     "6.1.7. Disponibilizar um canal público de suporte, por meio de página na internet em "
     "língua portuguesa, para:",
     "Fornecer manuais e outros materiais com orientações relativas à configuração, "
     "atualização e uso seguro dos equipamentos."),
]


def criar_para(processo, db):
    """Cria o questionario do processo, tudo marcado como C. Nao mexe no que ja existe."""
    from .models import RequisitoCiber
    if processo.requisitos_ciber:
        return 0
    for i, (codigo, titulo, secao, texto) in enumerate(REQUISITOS):
        db.session.add(RequisitoCiber(processo=processo, ordem=i * 10, codigo=codigo,
                                      titulo=titulo, secao=secao, texto=texto, situacao="C"))
    return len(REQUISITOS)


def agrupado(itens):
    """Organiza os itens para exibicao/impressao: [(titulo, [(secao, [itens])])]."""
    blocos = []
    for item in sorted(itens, key=lambda r: r.ordem):
        if not blocos or blocos[-1][0] != item.titulo:
            blocos.append((item.titulo, []))
        secoes = blocos[-1][1]
        if not secoes or secoes[-1][0] != item.secao:
            secoes.append((item.secao, []))
        secoes[-1][1].append(item)
    return blocos
