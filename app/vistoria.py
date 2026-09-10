"""Vistoria da foto: mede a imagem e diz, na hora, se ela serve.

A ideia veio da vistoria de seguro pelo celular: uma vista por vez, tira a foto,
o sistema olha e responde "essa serve" ou "essa nao serve porque...". Aqui a
conferencia tem duas camadas:

  LOCAL (sempre ligada, sem internet e sem custo) - Pillow mede a imagem:
    escura, estourada, sem contraste, tremida/desfocada, pequena demais, ou
    repetida (a mesma foto mandada duas vezes em vistas diferentes).

  IA (desligada de fabrica) - manda a foto para a API da Anthropic e pergunta se
    e MESMO aquela vista, se a etiqueta esta legivel, se a regua aparece. So
    funciona depois que alguem liga na tela de configuracao e informa a chave.
    Enquanto estiver desligada, nenhuma foto sai da rede.

Os limiares locais foram calibrados no acervo real de fotos deste sistema (as
185 fotos dos produtos ja homologados), com folga para nao reprovar foto boa:
reprovar foto boa e pior do que deixar passar uma duvidosa, porque quem esta na
bancada perde a confianca na ferramenta e passa a ignorar o aviso.
"""
import json
from pathlib import Path

# ------------------------------------------------------------------ limiares
# Medidos no acervo real; ver o teste teste_vistoria.py, que refaz a conta.
# O acervo real (208 fotos ja aceitas pelas OCDs) mede assim:
#   menor lado  min 134   p5 736    mediana 1200
#   brilho      min 68,2  p5 90,4   mediana 142,2
#   contraste   min 22,2  p5 32,9   mediana 53,4
#   nitidez     min 1,06  p5 3,91   mediana 9,84  (perda ao borrar)
# Os limiares ficam abaixo do MINIMO real, com folga: nenhuma foto que a OCD ja
# aceitou seria barrada hoje. As duas unicas reprovadas na calibragem sao dois
# icones de 134 px que nunca foram foto de produto.
LADO_MINIMO = 640              # px no menor lado - abaixo disso a OCD reclama
LADO_BOM = 800                 # px no menor lado - abaixo disso e so um aviso
BRILHO_ESCURO = 55             # media 0-255 do cinza
BRILHO_ESTOURADO = 225
CONTRASTE_MINIMO = 18          # desvio padrao do cinza; abaixo disso e chapada
CONTRASTE_GRAVE = 10           # abaixo disso nao da para ler nada na foto
# Nitidez: o quanto a foto muda ao ser borrada de leve (ver nitidez_de).
# Acervo real: pior 1,06 · p5 3,91 · mediana 9,84.
# A mesma foto fora de foco cai para 0,1-0,5 - uma queda de umas 9 vezes.
NITIDEZ_MINIMA = 0.8           # abaixo disso e desfoque claro
NITIDEZ_DUVIDOSA = 2.0         # entre 0,8 e 2,0 a foto esta mole: so avisa
# Branco puro (>=250). No acervo real o pior caso tem 8,4%; acima de 10% ja e
# reflexo visivel e acima de 18% a etiqueta costuma sumir no brilho.
FATIA_ESTOURADA = 0.18
FATIA_ESTOURADA_AVISO = 0.10
FATIA_APAGADA = 0.55           # 55% no preto = foto tampada ou sem luz
DISTANCIA_REPETIDA = 6         # bits diferentes no dHash; <= isso e a mesma foto

GRAVE = "grave"                # reprova
AVISO = "aviso"                # passa, mas avisa

# Ordem de causa: uma foto tampada tambem sai "tremida" e "lavada", mas quem
# esta na bancada precisa ouvir UMA coisa - a que explica as outras. A tela
# mostra os dois primeiros desta ordem e resume o resto.
PRIORIDADE = ["ilegivel", "repetida", "tampada", "escura", "clara", "reflexo",
              "tremida", "pequena", "chapada"]


# ------------------------------------------------------------------ medicao

def _cinza(caminho, lado=512):
    from PIL import Image, ImageOps
    with Image.open(caminho) as img:
        img = ImageOps.exif_transpose(img)          # iPhone grava a rotacao no EXIF
        largura, altura = img.size
        cinza = img.convert("L")
        cinza.thumbnail((lado, lado))
        return cinza, largura, altura


def medir(caminho):
    """Numeros crus da imagem. Nao julga nada - so mede."""
    from PIL import ImageFilter, ImageStat
    cinza, largura, altura = _cinza(caminho)
    estatistica = ImageStat.Stat(cinza)
    histograma = cinza.histogram()
    pixels = sum(histograma) or 1
    bordas = nitidez_de(caminho)
    return dict(
        largura=largura, altura=altura,
        menor_lado=min(largura, altura),
        brilho=round(estatistica.mean[0], 1),
        contraste=round(estatistica.stddev[0], 1),
        nitidez=round(bordas, 1),
        fatia_estourada=round(sum(histograma[250:]) / pixels, 3),
        fatia_apagada=round(sum(histograma[:12]) / pixels, 3),
        impressao=impressao_digital(caminho),
    )


def nitidez_de(caminho, ladrilho=384, grade=3):
    """Quanto de detalhe fino a foto tem, no MELHOR pedaco dela.

    Mede o quanto a imagem MUDA quando recebe um borrao de leve: foto em foco
    muda muito (tem detalhe para perder), foto ja fora de foco quase nao muda.
    Tres decisoes que so apareceram medindo o acervo real:

    1) EM RESOLUCAO NATIVA. Sobre a miniatura de 512 px o desfoque sumia: numa
       foto de 4000 px, 20 px de borrao viram 2,5 px na miniatura e a conta dava
       "nitida". Foco e propriedade do pixel original.

    2) O MELHOR PEDACO, nao o centro. O centro de uma foto larga costuma ser
       fundo liso, e a medida despencava numa foto perfeitamente nitida. Foto em
       foco tem ao menos UMA regiao com detalhe.

    3) DIFERENCA AO BORRAR, e nao forca de borda. Contar borda com FIND_EDGES
       parecia funcionar, mas o numero era dominado pelo CONTORNO do produto -
       que sobrevive ao desfoque. Numa foto de aparelho preto brilhante em fundo
       branco, a medida quase nao mudava entre nitida e borrada.

    Pega desfoque claro (fora de foco, movimento). Foto levemente mole passa com
    aviso - e para isso que existe a segunda opiniao da IA, que olha se a
    etiqueta continua legivel.
    """
    from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat
    with Image.open(caminho) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        largura, altura = img.size
        lado = min(ladrilho, largura, altura)
        melhor = 0.0
        for coluna in range(grade):
            for linha in range(grade):
                esquerda = int((largura - lado) * coluna / max(1, grade - 1))
                topo = int((altura - lado) * linha / max(1, grade - 1))
                pedaco = img.crop((esquerda, topo, esquerda + lado, topo + lado))
                perdido = ImageChops.difference(
                    pedaco, pedaco.filter(ImageFilter.GaussianBlur(1.5)))
                melhor = max(melhor, ImageStat.Stat(perdido).stddev[0])
    return round(melhor, 2)


def impressao_digital(caminho):
    """dHash de 64 bits: compara cada pixel com o vizinho da direita.

    Serve para pegar a MESMA foto mandada em duas vistas diferentes - erro comum
    de quem esta com pressa e reaproveita a ultima imagem da galeria.
    """
    from PIL import Image, ImageOps
    with Image.open(caminho) as img:
        img = ImageOps.exif_transpose(img).convert("L").resize((9, 8))
        pixels = list(img.getdata())
    bits = 0
    for linha in range(8):
        for coluna in range(8):
            esquerda = pixels[linha * 9 + coluna]
            direita = pixels[linha * 9 + coluna + 1]
            bits = (bits << 1) | (1 if esquerda > direita else 0)
    return f"{bits:016x}"


def distancia(uma, outra):
    """Quantos bits diferem entre duas impressoes digitais."""
    if not uma or not outra:
        return 64
    return bin(int(uma, 16) ^ int(outra, 16)).count("1")


# ------------------------------------------------------------------ julgamento

def _problema(codigo, gravidade, mensagem, comofazer):
    return dict(codigo=codigo, gravidade=gravidade, mensagem=mensagem,
                comofazer=comofazer)


def conferir(medidas, impressoes_anteriores=()):
    """Le as medidas e devolve a lista de problemas, do pior para o menor."""
    problemas = []

    if medidas["menor_lado"] < LADO_MINIMO:
        problemas.append(_problema(
            "pequena", GRAVE,
            f"Imagem pequena demais ({medidas['largura']}x{medidas['altura']} px).",
            "Fotografe de novo com a câmera do celular, sem recortar depois."))
    elif medidas["menor_lado"] < LADO_BOM:
        problemas.append(_problema(
            "pequena", AVISO,
            f"Imagem no limite ({medidas['largura']}x{medidas['altura']} px).",
            "Serve, mas se puder refaça mais perto e sem recorte."))

    if medidas["fatia_apagada"] > FATIA_APAGADA:
        problemas.append(_problema(
            "tampada", GRAVE, "A maior parte da foto está preta.",
            "Verifique se o dedo cobriu a lente e refaça com mais luz."))
    elif medidas["brilho"] < BRILHO_ESCURO:
        problemas.append(_problema(
            "escura", GRAVE, f"Foto escura (brilho {medidas['brilho']} de 255).",
            "Acenda a luz da bancada ou aproxime-se da janela. Evite fotografar "
            "contra a luz."))

    if medidas["fatia_estourada"] > FATIA_ESTOURADA:
        problemas.append(_problema(
            "reflexo", GRAVE, "Muita área branca estourada — reflexo ou flash.",
            "Desligue o flash e mude o ângulo até o brilho sair de cima do "
            "produto."))
    elif medidas["fatia_estourada"] > FATIA_ESTOURADA_AVISO:
        problemas.append(_problema(
            "reflexo", AVISO, "Há brilho estourado em parte da foto.",
            "Confira se a etiqueta e as marcações continuam legíveis; se o "
            "brilho cobriu alguma delas, mude o ângulo e refaça."))
    elif medidas["brilho"] > BRILHO_ESTOURADO:
        problemas.append(_problema(
            "clara", GRAVE, f"Foto estourada (brilho {medidas['brilho']} de 255).",
            "Afaste a luz direta ou toque na tela do celular sobre o produto "
            "para ele medir a luz certa."))

    if medidas["nitidez"] < NITIDEZ_MINIMA:
        problemas.append(_problema(
            "tremida", GRAVE, "Foto desfocada ou tremida.",
            "Apoie o cotovelo na bancada, toque no produto na tela para focar e "
            "só então dispare."))
    elif medidas["nitidez"] < NITIDEZ_DUVIDOSA:
        problemas.append(_problema(
            "tremida", AVISO, "O foco ficou no limite.",
            "Confira na foto se a etiqueta está legível; se não estiver, refaça."))

    if medidas["contraste"] < CONTRASTE_GRAVE:
        problemas.append(_problema(
            "chapada", GRAVE, "Imagem lavada, sem contraste nenhum.",
            "Provavelmente há luz batendo direto na lente ou o produto se "
            "confunde com o fundo. Troque o fundo e refaça."))
    elif medidas["contraste"] < CONTRASTE_MINIMO:
        problemas.append(_problema(
            "chapada", AVISO, "Imagem sem contraste.",
            "Use fundo neutro que contraste com o produto (produto escuro pede "
            "fundo claro)."))

    for anterior in impressoes_anteriores:
        if distancia(medidas["impressao"], anterior.get("impressao")) <= DISTANCIA_REPETIDA:
            problemas.append(_problema(
                "repetida", GRAVE,
                f"Esta é a mesma foto já usada em “{anterior.get('vista', 'outra vista')}”.",
                "Cada vista precisa da sua própria foto. Vire o produto e "
                "fotografe esta vista."))
            break

    return ordenar(problemas)


def ordenar(problemas):
    """Primeiro o que reprova, e dentro disso a causa antes da consequencia."""
    ordem = {GRAVE: 0, AVISO: 1}
    def peso(p):
        codigo = p["codigo"].replace("ia_", "")
        posicao = PRIORIDADE.index(codigo) if codigo in PRIORIDADE else len(PRIORIDADE)
        return (ordem[p["gravidade"]], posicao)
    return sorted(problemas, key=peso)


def analisar(caminho, impressoes_anteriores=()):
    """Mede e julga. E o que a tela de captura chama a cada foto enviada."""
    try:
        medidas = medir(caminho)
    except Exception as erro:                        # arquivo corrompido, formato exotico
        return dict(aprovada=False, medidas={}, problemas=[_problema(
            "ilegivel", GRAVE, f"Não consegui abrir esta imagem ({erro}).",
            "Tire a foto novamente pela câmera do celular.")], ia=None)
    problemas = conferir(medidas, impressoes_anteriores)
    return dict(aprovada=not any(p["gravidade"] == GRAVE for p in problemas),
                medidas=medidas, problemas=problemas, ia=None)


# ------------------------------------------------------------------ camada de IA
# Tudo daqui para baixo so roda se alguem ligar a verificacao por IA na tela de
# configuracao. Enquanto estiver desligada, nenhuma foto sai da rede.

LADO_PARA_IA = 1024            # reduz antes de enviar: menos token, menos custo
INSTRUCAO = """Você confere fotos de produtos para o processo de certificação da ANATEL, antes de irem para o Organismo de Certificação (OCD).

Sua tarefa é olhar UMA foto e dizer se ela serve para a vista pedida. Reprove apenas o que a OCD reprovaria de fato:
- a foto mostra outra face/parte do produto, e não a vista pedida;
- a etiqueta de identificação está ilegível quando a vista exige que ela apareça;
- o produto aparece cortado, ou tão longe que não dá para conferir nada;
- falta a régua ao lado do produto, quando a vista pede medida;
- há reflexo, sombra ou dedo cobrindo a informação que importa.

Não reprove por gosto pessoal: enquadramento levemente torto, fundo não perfeito ou sombra que não atrapalha a leitura estão aprovados. Na dúvida, aprove e registre a ressalva.

Escreva as mensagens em português do Brasil, curtas, ditas para quem está com o produto na bancada: o que está errado e o que fazer para corrigir."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "corresponde": {"type": "boolean"},
        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
        "resumo": {"type": "string"},
        "problemas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string",
                               "enum": ["vista_errada", "etiqueta_ilegivel",
                                        "sem_regua", "produto_cortado",
                                        "reflexo", "outro"]},
                    "gravidade": {"type": "string", "enum": ["grave", "aviso"]},
                    "mensagem": {"type": "string"},
                    "comofazer": {"type": "string"},
                },
                "required": ["codigo", "gravidade", "mensagem", "comofazer"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["corresponde", "confianca", "resumo", "problemas"],
    "additionalProperties": False,
}


def _imagem_para_envio(caminho):
    """Reduz e recomprime: 1024 px de lado chega e sai bem mais barato."""
    import base64
    from io import BytesIO
    from PIL import Image, ImageOps
    with Image.open(caminho) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((LADO_PARA_IA, LADO_PARA_IA))
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=82)
    return base64.standard_b64encode(buffer.getvalue()).decode("ascii")


def _pedido(vista):
    partes = [f"Vista pedida: {vista.nome}."]
    if vista.descricao:
        partes.append(f"O que ela precisa mostrar: {vista.descricao}")
    if vista.dica:
        partes.append(f"Atenção da OCD nesta vista: {vista.dica}")
    partes.append("Esta foto serve para essa vista?")
    return "\n".join(partes)


def verificar_com_ia(caminho, vista, chave, modelo="claude-opus-5"):
    """Pergunta ao modelo de visao se a foto e mesmo aquela vista.

    Nunca levanta excecao: se a chamada falhar (sem internet, chave errada,
    limite atingido), devolve indisponivel=True com o motivo, e a captura segue
    valendo pela conferencia local. Travar a bancada por causa da API seria pior
    do que ficar sem a segunda opiniao.
    """
    try:
        import anthropic
    except ImportError:
        return dict(indisponivel=True, motivo=(
            "A biblioteca da Anthropic não está instalada neste servidor. "
            r"Instale com: .venv\Scripts\pip install anthropic"))
    if not chave:
        return dict(indisponivel=True,
                    motivo="Nenhuma chave de API configurada.")
    try:
        cliente = anthropic.Anthropic(api_key=chave, timeout=45.0, max_retries=1)
        resposta = cliente.messages.create(
            model=modelo or "claude-opus-5",
            max_tokens=1200,
            system=INSTRUCAO,
            output_config={"format": {"type": "json_schema", "schema": ESQUEMA},
                           "effort": "low"},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": _imagem_para_envio(caminho)}},
                {"type": "text", "text": _pedido(vista)},
            ]}],
        )
    except Exception as erro:                    # rede, chave, limite, timeout
        return dict(indisponivel=True, motivo=f"{type(erro).__name__}: {erro}")

    texto = next((b.text for b in resposta.content if b.type == "text"), "")
    try:
        dados = json.loads(texto)
    except ValueError:
        return dict(indisponivel=True, motivo="Resposta da IA veio ilegível.")
    dados["indisponivel"] = False
    dados["modelo"] = resposta.model
    uso = getattr(resposta, "usage", None)
    if uso:
        dados["tokens"] = dict(entrada=uso.input_tokens, saida=uso.output_tokens)
    return dados


def juntar_ia(analise, resultado_ia, reprova=True):
    """Soma o parecer da IA ao veredito local.

    `reprova=False` deixa a IA so avisar: util no comeco, para calibrar a
    confianca sem travar ninguem.
    """
    analise["ia"] = resultado_ia
    if not resultado_ia or resultado_ia.get("indisponivel"):
        return analise
    for bruto in resultado_ia.get("problemas", []):
        gravidade = bruto.get("gravidade", AVISO)
        if not reprova:
            gravidade = AVISO
        analise["problemas"].append(_problema(
            "ia_" + bruto.get("codigo", "outro"), gravidade,
            bruto.get("mensagem", ""), bruto.get("comofazer", "")))
    if reprova and not resultado_ia.get("corresponde", True):
        analise["aprovada"] = False
    if any(p["gravidade"] == GRAVE for p in analise["problemas"]):
        analise["aprovada"] = False
    analise["problemas"] = ordenar(analise["problemas"])
    return analise


# ------------------------------------------------------------------ registro

def resumir(analise):
    """Uma linha para guardar no banco e mostrar na listagem."""
    if analise.get("aprovada"):
        avisos = [p for p in analise.get("problemas", []) if p["gravidade"] == AVISO]
        return "aprovada" + (f" com {len(avisos)} aviso(s)" if avisos else "")
    graves = [p["mensagem"] for p in analise.get("problemas", [])
              if p["gravidade"] == GRAVE]
    return "; ".join(graves) or "reprovada"


def para_json(analise):
    return json.dumps(analise, ensure_ascii=False)


def de_json(texto):
    try:
        return json.loads(texto or "") or {}
    except (ValueError, TypeError):
        return {}
