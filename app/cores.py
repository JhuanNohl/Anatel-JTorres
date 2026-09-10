"""Cores dos status: paleta sugerida e derivacao das cores do crachá.

O usuario escolhe UMA cor (RGB, em hexadecimal). A partir dela o sistema deriva
as tres cores do crachá - fundo, borda e texto - misturando com branco e com o
cinza escuro do tema. Assim qualquer cor escolhida sai legivel: o tom do texto
e escurecido ate garantir contraste WCAG AA (4.5:1) sobre o fundo derivado.

O mesmo calculo esta repetido em app/static/js/cor.js, so para a previa ao vivo
da tela de cadastro. Se mexer na formula aqui, mexa lá também.
"""
import re

BRANCO = (255, 255, 255)
ESCURO = (35, 38, 41)          # o mesmo cinza do texto do tema
CONTRASTE_MINIMO = 4.5         # WCAG AA para texto normal

# Cores antigas, de quando o campo era uma lista fechada de nomes.
# Ficam aqui para que os cadastros ja gravados continuem sendo entendidos.
APELIDOS = {
    "verde": "#7AC143",
    "azul": "#3E7D9C",
    "amarelo": "#D9A21B",
    "cinza": "#8B9296",
    "vermelho": "#D0554B",
}

# Paleta sugerida na tela. A primeira linha e a identidade ZKTeco.
PALETA = [
    ("Verde ZKTeco", "#7AC143"),
    ("Verde escuro", "#649E37"),
    ("Verde musgo", "#4E7D2A"),
    ("Grafite", "#474B4F"),
    ("Cinza", "#8B9296"),
    ("Cinza claro", "#B6BBBE"),

    ("Turquesa", "#2FA98C"),
    ("Ciano", "#2BA3C7"),
    ("Azul", "#3E7D9C"),
    ("Azul escuro", "#2F5D8A"),
    ("Roxo", "#7A5EA8"),
    ("Magenta", "#B0559B"),

    ("Rosa", "#D9587A"),
    ("Vermelho", "#D0554B"),
    ("Laranja", "#E07B39"),
    ("Âmbar", "#D9A21B"),
    ("Oliva", "#8A9A3B"),
    ("Marrom", "#8C6E4A"),
]

PADRAO = "#8B9296"
_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalizar(valor):
    """Devolve sempre '#rrggbb'. Aceita hex com ou sem #, 3 ou 6 digitos,
    e tambem os nomes antigos ('verde', 'azul'...)."""
    texto = (valor or "").strip()
    if not texto:
        return PADRAO
    if texto.lower() in APELIDOS:
        return APELIDOS[texto.lower()]
    achou = _HEX.match(texto)
    if not achou:
        return PADRAO
    digitos = achou.group(1)
    if len(digitos) == 3:
        digitos = "".join(d * 2 for d in digitos)
    return "#" + digitos.lower()


def para_rgb(hexa):
    hexa = normalizar(hexa).lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def para_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def _misturar(cor, alvo, peso):
    """peso 0 = cor original; peso 1 = alvo."""
    return tuple(c * (1 - peso) + a * peso for c, a in zip(cor, alvo))


def _luminancia(rgb):
    def canal(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(rgb_a, rgb_b):
    a, b = _luminancia(rgb_a), _luminancia(rgb_b)
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


def derivar(valor):
    """As tres cores do crachá a partir da cor escolhida."""
    base = para_rgb(valor)
    fundo = _misturar(base, BRANCO, 0.86)
    borda = _misturar(base, BRANCO, 0.60)
    # escurece o texto ate ficar legivel sobre o fundo derivado
    texto = _misturar(base, ESCURO, 0.40)
    peso = 0.40
    while contraste(texto, fundo) < CONTRASTE_MINIMO and peso < 0.95:
        peso += 0.05
        texto = _misturar(base, ESCURO, peso)
    return dict(base=para_hex(base), fundo=para_hex(fundo),
                borda=para_hex(borda), texto=para_hex(texto))


def estilo_badge(valor):
    """CSS pronto para o atributo style de um <span class="badge">."""
    c = derivar(valor)
    return f"background:{c['fundo']};border-color:{c['borda']};color:{c['texto']}"


def estilo_indicador(valor):
    """Os cartoes de contagem do painel usam a cor cheia na barra lateral."""
    return f"border-left-color:{normalizar(valor)}"
