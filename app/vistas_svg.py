"""Desenhos (SVG) de exemplo para cada vista fotografica exigida pelo OCD.

Cada desenho tem duas partes:
  - painel principal: como a foto deve ficar;
  - cubo indicador (canto superior direito): de onde a camera deve apontar.
"""

PRIM = "#7AC143"
SEC = "#474B4F"
ACC = "#649E37"
TXT = "#555555"
LINHA = "#B9BEC3"

W, H = 240, 170

_DEFS = (
    '<defs>'
    '<marker id="pt" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
    f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ACC}"/></marker>'
    '</defs>'
)


def _svg(inner):
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'class="vista-svg" preserveAspectRatio="xMidYMid meet">{_DEFS}{inner}</svg>')


def _txt(x, y, texto, tam=7, cor=TXT, anchor="start", peso="400"):
    return (f'<text x="{x}" y="{y}" font-size="{tam}" fill="{cor}" font-weight="{peso}" '
            f'text-anchor="{anchor}" font-family="Segoe UI, Arial, sans-serif">{texto}</text>')


def _seta(x1, y1, x2, y2):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ACC}" stroke-width="1.6" '
            f'marker-end="url(#pt)"/>')


def _camera(x, y):
    """Icone simplificado de camera."""
    return (f'<g><rect x="{x}" y="{y}" width="16" height="11" rx="2" fill="{SEC}"/>'
            f'<circle cx="{x + 8}" cy="{y + 5.5}" r="3.2" fill="none" stroke="#fff" stroke-width="1.2"/>'
            f'<rect x="{x + 4}" y="{y - 2.5}" width="6" height="3" rx="1" fill="{SEC}"/></g>')


# ------------------------------------------------------------- cubo indicador

def _cubo(face):
    """Cubo isometrico com a face alvo destacada."""
    fr = "170,66 202,66 202,96 170,96"
    tp = "170,66 182,54 214,54 202,66"
    rt = "202,66 214,54 214,84 202,96"
    lf = "170,66 158,54 158,84 170,96"
    bt = "170,96 182,108 214,108 202,96"
    bk = "182,54 214,54 214,84 182,84"

    base = (f'<polygon points="{fr}" fill="#fff" stroke="{SEC}" stroke-width="1.2"/>'
            f'<polygon points="{tp}" fill="#F1F3F4" stroke="{SEC}" stroke-width="1.2"/>'
            f'<polygon points="{rt}" fill="#E4E7E9" stroke="{SEC}" stroke-width="1.2"/>')

    destaque = ""
    seta = ""
    if face == "frontal":
        destaque = f'<polygon points="{fr}" fill="{PRIM}" fill-opacity=".85"/>'
        seta = _seta(186, 140, 186, 100) + _camera(178, 143)
    elif face == "traseira":
        destaque = (f'<polygon points="{bk}" fill="{PRIM}" fill-opacity=".35" '
                    f'stroke="{ACC}" stroke-width="1.4" stroke-dasharray="3 2"/>')
        seta = _seta(222, 30, 206, 48) + _camera(222, 18)
    elif face == "superior":
        destaque = f'<polygon points="{tp}" fill="{PRIM}" fill-opacity=".85"/>'
        seta = _seta(196, 26, 196, 48) + _camera(188, 12)
    elif face == "inferior":
        destaque = (f'<polygon points="{bt}" fill="{PRIM}" fill-opacity=".35" '
                    f'stroke="{ACC}" stroke-width="1.4" stroke-dasharray="3 2"/>')
        seta = _seta(192, 142, 192, 112) + _camera(184, 145)
    elif face == "direita":
        destaque = f'<polygon points="{rt}" fill="{PRIM}" fill-opacity=".85"/>'
        seta = _seta(232, 100, 216, 90) + _camera(222, 104)
    elif face == "esquerda":
        destaque = (f'<polygon points="{lf}" fill="{PRIM}" fill-opacity=".35" '
                    f'stroke="{ACC}" stroke-width="1.4" stroke-dasharray="3 2"/>')
        seta = _seta(140, 100, 160, 88) + _camera(126, 104)
    elif face == "iso":
        destaque = (f'<polygon points="{fr}" fill="{PRIM}" fill-opacity=".7"/>'
                    f'<polygon points="{tp}" fill="{PRIM}" fill-opacity=".4"/>'
                    f'<polygon points="{rt}" fill="{PRIM}" fill-opacity=".55"/>')
        seta = _seta(224, 128, 206, 104) + _camera(224, 132)
    return f'<g>{base}{destaque}{seta}</g>'


# ------------------------------------------------------------- painel

def _painel(x=14, y=26, w=118, h=120, r=6):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="#fff" '
            f'stroke="{SEC}" stroke-width="1.6"/>')


def _parafusos(x, y, w, h):
    p = ""
    for cx, cy in ((x + 8, y + 8), (x + w - 8, y + 8), (x + 8, y + h - 8), (x + w - 8, y + h - 8)):
        p += (f'<circle cx="{cx}" cy="{cy}" r="3" fill="none" stroke="{LINHA}" stroke-width="1.2"/>'
              f'<line x1="{cx - 2}" y1="{cy}" x2="{cx + 2}" y2="{cy}" stroke="{LINHA}" stroke-width="1.2"/>')
    return p


def _codigo_barras(x, y, w=44, h=14):
    barras = ""
    larguras = [1, 2, 1, 3, 1, 1, 2, 1, 2, 3, 1, 1, 2, 1, 1, 3, 1, 2]
    cx = x
    for i, lw in enumerate(larguras):
        if i % 2 == 0:
            barras += f'<rect x="{cx}" y="{y}" width="{lw}" height="{h}" fill="{SEC}"/>'
        cx += lw + 1
        if cx > x + w:
            break
    return barras


def _etiqueta(x, y, w=76, h=46, zoom=False):
    """Etiqueta com os 5 dados exigidos: marca, modelo, pais, rastreabilidade e selo."""
    g = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="#FCFCFA" '
         f'stroke="{SEC}" stroke-width="1.4"/>')
    g += _txt(x + 5, y + 10, "ZKTeco", 6.5, SEC, peso="700")
    g += _txt(x + 5, y + 19, "Modelo: XXXX", 5.6, TXT)
    g += _txt(x + 5, y + 27, "País de origem: China", 5.6, TXT)
    g += _txt(x + 5, y + 35, "Rastreab.: 000000", 5.6, TXT)
    g += _codigo_barras(x + 5, y + 38, w=w - 36, h=6)
    # selo Anatel
    g += (f'<rect x="{x + w - 28}" y="{y + 14}" width="24" height="26" rx="2" fill="none" '
          f'stroke="{ACC}" stroke-width="1.3"/>')
    g += _txt(x + w - 16, y + 23, "Anatel", 4.6, ACC, anchor="middle", peso="700")
    g += _txt(x + w - 16, y + 31, "00000-00", 4, TXT, anchor="middle")
    g += _txt(x + w - 16, y + 38, "-00000", 4, TXT, anchor="middle")
    if zoom:
        g += (f'<circle cx="{x + w - 6}" cy="{y + h + 4}" r="7" fill="none" stroke="{PRIM}" '
              f'stroke-width="1.6"/><line x1="{x + w}" y1="{y + h + 9}" x2="{x + w + 8}" '
              f'y2="{y + h + 16}" stroke="{PRIM}" stroke-width="2"/>')
    return g


def _blindagem(x, y, w, h, aberta=False):
    """Lata de blindagem sobre a placa: fechada ou removida ao lado."""
    if not aberta:
        g = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="#D9DEE1" '
             f'stroke="{SEC}" stroke-width="1.5"/>')
        for i in range(4):
            g += (f'<line x1="{x + 4 + i * (w - 8) / 3}" y1="{y + 3}" '
                  f'x2="{x + 4 + i * (w - 8) / 3}" y2="{y + h - 3}" stroke="#B9BEC3" '
                  f'stroke-width="0.8"/>')
        return g
    # blindagem removida: contorno vazio + componentes a mostra
    g = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="none" '
         f'stroke="{ACC}" stroke-width="1.3" stroke-dasharray="3 2"/>')
    for i in range(3):
        g += (f'<rect x="{x + 5 + i * 11}" y="{y + 6}" width="8" height="7" rx="1" '
              f'fill="{SEC}"/>')
    g += f'<circle cx="{x + 10}" cy="{y + h - 8}" r="3.2" fill="none" stroke="{SEC}" stroke-width="1.2"/>'
    g += f'<rect x="{x + 19}" y="{y + h - 12}" width="12" height="8" rx="1" fill="#B9BEC3"/>'
    return g


def _regua(x, y, w, h=9):
    """Regua horizontal (escala metrica)."""
    g = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#FBF7E8" stroke="{SEC}" '
         f'stroke-width="0.9"/>')
    i = 0
    while i * 8 <= w:
        alto = 6 if i % 5 == 0 else 3
        g += (f'<line x1="{x + i * 8}" y1="{y}" x2="{x + i * 8}" y2="{y + alto}" '
              f'stroke="{SEC}" stroke-width="0.8"/>')
        i += 1
    return g


def _pci(x, y, w, h, solda=False):
    g = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{PRIM}" fill-opacity=".18" '
         f'stroke="{ACC}" stroke-width="1.4"/>')
    if solda:
        for i in range(6):
            for j in range(4):
                g += (f'<circle cx="{x + 12 + i * 15}" cy="{y + 14 + j * 18}" r="2.2" fill="none" '
                      f'stroke="{ACC}" stroke-width="1"/>')
        g += f'<path d="M{x + 8},{y + h - 8} H{x + w - 8}" stroke="{ACC}" stroke-width="1" stroke-dasharray="2 3"/>'
    else:
        g += f'<rect x="{x + 10}" y="{y + 12}" width="26" height="20" rx="2" fill="{SEC}"/>'
        g += _txt(x + 23, y + 25, "MCU", 5, "#fff", anchor="middle", peso="700")
        g += (f'<rect x="{x + 44}" y="{y + 10}" width="34" height="26" rx="2" fill="#D9DEE1" '
              f'stroke="{SEC}" stroke-width="1.2"/>')
        g += _txt(x + 61, y + 26, "RF", 6, SEC, anchor="middle", peso="700")
        for i in range(5):
            g += f'<rect x="{x + 12 + i * 12}" y="{y + h - 22}" width="7" height="5" rx="1" fill="{SEC}"/>'
        g += (f'<path d="M{x + 82},{y + 22} h12 v-10 h8" stroke="{ACC}" stroke-width="1.4" fill="none"/>')
        g += _txt(x + 84, y + 40, "antena", 5, TXT)
    return g


# ------------------------------------------------------------- vistas
# Regra: UMA regua por foto, sempre ao lado do produto. Todo desenho termina com
# _rodape_regua(), na mesma faixa vertical, para o padrao ficar obvio.


def _rodape_regua(x, largura, y=126, texto="uma régua ao lado do produto"):
    g = _regua(x, y, largura)
    g += _txt(x + largura / 2, y + 21, texto, 5.4, ACC, anchor="middle", peso="700")
    return g


def _v_frontal():
    g = _painel(22, 30, 108, 84)
    g += f'<rect x="32" y="40" width="88" height="40" rx="3" fill="#EDF1F3" stroke="{LINHA}"/>'
    g += _txt(76, 64, "face frontal", 6, TXT, anchor="middle")
    g += f'<circle cx="40" cy="96" r="6" fill="none" stroke="{SEC}" stroke-width="1.4"/>'
    for i in range(3):
        g += (f'<rect x="{62 + i * 14}" y="90" width="11" height="10" rx="2" '
              f'fill="none" stroke="{LINHA}" stroke-width="1.1"/>')
    g += _txt(76, 20, "VISTA FRONTAL", 8, SEC, anchor="middle", peso="700")
    g += _rodape_regua(22, 108, 124)
    return _svg(g + _cubo("frontal"))


def _v_traseira():
    g = _painel(18, 28, 114, 92)
    g += _parafusos(18, 28, 114, 92)
    g += _etiqueta(34, 42, 82, 46)
    g += f'<rect x="54" y="98" width="42" height="8" rx="4" fill="none" stroke="{LINHA}"/>'
    g += _txt(75, 20, "VISTA TRASEIRA", 8, SEC, anchor="middle", peso="700")
    g += _rodape_regua(18, 114, 128)
    return _svg(g + _cubo("traseira"))


def _v_superior():
    g = f'<rect x="18" y="48" width="114" height="50" rx="5" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += f'<line x1="18" y1="62" x2="132" y2="62" stroke="{LINHA}" stroke-dasharray="3 3"/>'
    g += _txt(75, 80, "topo do equipamento", 6, TXT, anchor="middle")
    g += _txt(75, 26, "VISTA SUPERIOR", 8, SEC, anchor="middle", peso="700")
    g += _txt(75, 112, "câmera perpendicular ao topo", 5.2, TXT, anchor="middle")
    g += _rodape_regua(18, 114, 122)
    return _svg(g + _cubo("superior"))


def _v_inferior():
    g = f'<rect x="18" y="44" width="114" height="56" rx="5" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += _etiqueta(26, 48, 84, 44)
    g += _txt(75, 26, "VISTA INFERIOR / BASE", 8, SEC, anchor="middle", peso="700")
    g += _txt(75, 112, "normalmente onde fica a etiqueta", 5.2, TXT, anchor="middle")
    g += _rodape_regua(18, 114, 122)
    return _svg(g + _cubo("inferior"))


def _v_lateral(lado, escala=False):
    g = f'<rect x="52" y="28" width="48" height="86" rx="5" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += f'<rect x="60" y="44" width="32" height="10" rx="2" fill="none" stroke="{LINHA}"/>'
    g += _txt(76, 66, "USB", 5.5, TXT, anchor="middle")
    g += f'<rect x="62" y="76" width="28" height="12" rx="2" fill="none" stroke="{LINHA}"/>'
    g += _txt(76, 102, "conectores", 5.5, TXT, anchor="middle")
    if escala:
        g += _txt(76, 20, "LATERAL DIREITA", 8, SEC, anchor="middle", peso="700")
        g += _rodape_regua(38, 76, 126, "régua: dá a Profundidade")
    else:
        g += _txt(76, 20, f"LATERAL {lado.upper()}", 8, SEC, anchor="middle", peso="700")
        g += _rodape_regua(38, 76, 126)
    return _svg(g + _cubo("esquerda" if lado == "esquerda" else "direita"))


def _v_etiqueta():
    """Uma unica vista: os dados legiveis E a posicao da etiqueta no produto."""
    g = _txt(120, 18, "IDENTIFICAÇÃO E SELO ANATEL", 8, SEC, anchor="middle", peso="700")
    # etiqueta em close, com os campos exigidos
    g += _etiqueta(8, 34, 104, 58)
    g += (f'<circle cx="100" cy="98" r="8" fill="none" stroke="{PRIM}" stroke-width="1.6"/>'
          f'<line x1="106" y1="104" x2="114" y2="112" stroke="{PRIM}" stroke-width="2"/>')
    g += _txt(56, 114, "todos os dados legíveis", 5.4, ACC, anchor="middle", peso="700")
    # o mesmo produto, mostrando onde a etiqueta fica
    g += f'<rect x="132" y="32" width="92" height="62" rx="5" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += _parafusos(132, 32, 92, 62)
    g += _etiqueta(146, 42, 64, 40)
    g += (f'<rect x="143" y="39" width="70" height="46" rx="3" fill="none" stroke="{PRIM}" '
          f'stroke-width="1.8" stroke-dasharray="4 3"/>')
    g += _txt(178, 114, "e onde ela fica aplicada", 5.4, ACC, anchor="middle", peso="700")
    g += _rodape_regua(60, 120, 126)
    return _svg(g)


def _v_placas_carcaca():
    g = f'<rect x="16" y="32" width="118" height="84" rx="6" fill="#fff" stroke="{SEC}" stroke-width="2"/>'
    g += _txt(75, 26, "PLACAS DENTRO DA CARCAÇA", 7.5, SEC, anchor="middle", peso="700")
    g += _pci(24, 40, 72, 42)
    g += (f'<rect x="24" y="88" width="44" height="22" rx="2" fill="{PRIM}" fill-opacity=".18" '
          f'stroke="{ACC}" stroke-width="1.3"/>')
    g += _txt(46, 102, "placa 2", 5, TXT, anchor="middle")
    g += (f'<rect x="76" y="88" width="48" height="22" rx="2" fill="{PRIM}" fill-opacity=".18" '
          f'stroke="{ACC}" stroke-width="1.3"/>')
    g += _txt(100, 102, "placa 3", 5, TXT, anchor="middle")
    g += _rodape_regua(16, 118, 124)
    return _svg(g + _camera(196, 54) + _seta(198, 66, 150, 80))


def _v_pci_componentes():
    """Par obrigatorio: a mesma placa COM e SEM a blindagem, em uma unica vista."""
    g = _txt(120, 18, "PLACAS - FRENTE", 8, SEC, anchor="middle", peso="700")
    g += _pci(8, 28, 100, 58, solda=True)
    g += _blindagem(30, 40, 50, 28)
    g += _txt(55, 58, "BLINDAGEM", 5.2, SEC, anchor="middle", peso="700")
    g += _txt(58, 98, "COM blindagem", 6, ACC, anchor="middle", peso="700")
    g += _pci(130, 28, 100, 58, solda=True)
    g += _blindagem(148, 38, 52, 30, aberta=True)
    g += _txt(180, 98, "SEM blindagem", 6, ACC, anchor="middle", peso="700")
    g += _blindagem(206, 74, 20, 12)
    g += _seta(112, 58, 126, 58)
    g += _rodape_regua(60, 120, 112, "a mesma régua nas duas fotos")
    g += _txt(120, 148, "de TODAS as placas, inclusive retirando", 5.2, TXT, anchor="middle")
    g += _txt(120, 158, "a blindagem dos módulos", 5.2, TXT, anchor="middle")
    return _svg(g)


def _v_pci_solda():
    g = _txt(74, 20, "PLACAS - VERSO", 8, SEC, anchor="middle", peso="700")
    g += _pci(16, 30, 112, 70, solda=True)
    g += _txt(185, 56, "mesma placa", 5.5, TXT, anchor="middle")
    g += _txt(185, 66, "da foto anterior,", 5.5, TXT, anchor="middle")
    g += _txt(185, 76, "virada", 5.5, TXT, anchor="middle")
    g += _rodape_regua(16, 112, 110)
    g += _txt(74, 148, "se houver blindagem neste lado,", 5.2, TXT, anchor="middle")
    g += _txt(74, 158, "envie também o par com e sem", 5.2, TXT, anchor="middle")
    return _svg(g)


def _v_modulo_rf():
    g = _txt(120, 18, "MÓDULO / CIRCUITO DE RF", 8, SEC, anchor="middle", peso="700")
    g += _pci(10, 30, 120, 72)
    g += (f'<rect x="46" y="40" width="42" height="32" rx="2" fill="#D9DEE1" stroke="{SEC}" '
          f'stroke-width="1.4"/>')
    g += _txt(67, 60, "RF", 8, SEC, anchor="middle", peso="700")
    g += (f'<rect x="40" y="34" width="54" height="44" rx="3" fill="none" stroke="{PRIM}" '
          f'stroke-width="1.8" stroke-dasharray="4 3"/>')
    g += (f'<circle cx="160" cy="60" r="11" fill="none" stroke="{PRIM}" stroke-width="1.6"/>'
          f'<line x1="168" y1="68" x2="180" y2="80" stroke="{PRIM}" stroke-width="2"/>')
    g += _txt(190, 100, "etiqueta do módulo", 5.2, TXT, anchor="middle")
    g += _txt(190, 110, "legível", 5.2, TXT, anchor="middle")
    g += _rodape_regua(10, 120, 118)
    g += _txt(120, 158, "blindagem, cristal e trilha da antena", 5.2, TXT, anchor="middle")
    return _svg(g)


def _v_antena():
    g = _txt(73, 20, "ANTENA E CONECTOR", 8, SEC, anchor="middle", peso="700")
    g += f'<rect x="60" y="30" width="10" height="46" rx="5" fill="{SEC}"/>'
    g += _painel(20, 76, 104, 42)
    g += f'<circle cx="65" cy="78" r="7" fill="none" stroke="{SEC}" stroke-width="1.6"/>'
    g += _txt(140, 52, "antena / conector", 6, TXT)
    g += _txt(140, 64, "informar tipo e ganho", 5.4, TXT)
    g += _txt(140, 84, "antena removível:", 5.4, TXT)
    g += _txt(140, 94, "foto separada + conector", 5.4, TXT)
    g += _rodape_regua(20, 104, 126)
    return _svg(g)


def _v_acessorios():
    """Acessorios + fonte externa com a marcacao dos valores nominais."""
    g = _txt(120, 18, "ACESSÓRIOS E FONTE", 8, SEC, anchor="middle", peso="700")
    g += f'<rect x="10" y="30" width="76" height="56" rx="6" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += f'<rect x="28" y="22" width="6" height="10" rx="2" fill="{SEC}"/>'
    g += f'<rect x="50" y="22" width="6" height="10" rx="2" fill="{SEC}"/>'
    g += f'<rect x="16" y="36" width="64" height="42" rx="2" fill="#FCFCFA" stroke="{LINHA}"/>'
    g += _txt(20, 46, "INPUT: 100-240V~", 5.2, TXT)
    g += _txt(20, 55, "50/60Hz  0,5A", 5.2, TXT)
    g += _txt(20, 66, "OUTPUT: 12V  2A", 5.2, TXT, peso="700")
    g += _txt(20, 75, "24W", 5.2, TXT)
    g += (f'<circle cx="48" cy="98" r="9" fill="none" stroke="{PRIM}" stroke-width="1.6"/>'
          f'<line x1="54" y1="104" x2="63" y2="113" stroke="{PRIM}" stroke-width="2"/>')
    g += _txt(48, 116, "valores nominais legíveis", 5.2, ACC, anchor="middle", peso="700")
    g += f'<path d="M86,60 C106,60 106,84 126,84" stroke="{SEC}" stroke-width="2" fill="none"/>'
    g += f'<rect x="126" y="77" width="16" height="12" rx="2" fill="{SEC}"/>'
    g += f'<rect x="152" y="30" width="78" height="34" rx="4" fill="#fff" stroke="{SEC}" stroke-width="1.5"/>'
    g += _txt(191, 44, "cabos, suportes,", 5.4, TXT, anchor="middle")
    g += _txt(191, 54, "fone, microfone", 5.4, TXT, anchor="middle")
    g += f'<rect x="152" y="72" width="78" height="30" rx="4" fill="#FCFCFA" stroke="{LINHA}"/>'
    g += _txt(191, 86, "etiqueta de identificação", 5, TXT, anchor="middle")
    g += _txt(191, 96, "quando houver variações", 5, TXT, anchor="middle")
    g += _rodape_regua(60, 120, 126, "uma régua ao lado do conjunto")
    return _svg(g)


def _v_perspectiva():
    fr = "34,58 96,58 96,110 34,110"
    tp = "34,58 56,38 118,38 96,58"
    rt = "96,58 118,38 118,90 96,110"
    g = (f'<polygon points="{fr}" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
         f'<polygon points="{tp}" fill="#F4F6F7" stroke="{SEC}" stroke-width="1.6"/>'
         f'<polygon points="{rt}" fill="#E7EAEC" stroke="{SEC}" stroke-width="1.6"/>')
    g += f'<rect x="42" y="66" width="46" height="24" rx="2" fill="#EDF1F3" stroke="{LINHA}"/>'
    g += _txt(76, 22, "PERSPECTIVA (3/4)", 8, SEC, anchor="middle", peso="700")
    g += _txt(76, 158, "mostra 3 faces em uma única foto", 5.2, TXT, anchor="middle")
    g += _rodape_regua(30, 108, 122)
    return _svg(g + _cubo("iso"))


def _v_etiqueta_aplicada():
    g = _painel(16, 30, 116, 84)
    g += _parafusos(16, 30, 116, 84)
    g += _etiqueta(38, 46, 70, 44)
    g += (f'<rect x="34" y="42" width="78" height="52" rx="4" fill="none" stroke="{PRIM}" '
          f'stroke-width="1.8" stroke-dasharray="4 3"/>')
    g += _txt(74, 22, "ETIQUETA APLICADA", 8, SEC, anchor="middle", peso="700")
    g += _rodape_regua(16, 116, 124)
    g += _camera(196, 60) + _seta(198, 72, 140, 80)
    return _svg(g)


def _v_numero_serie():
    g = (f'<rect x="20" y="42" width="116" height="52" rx="3" fill="#FCFCFA" stroke="{SEC}" '
         f'stroke-width="1.4"/>')
    g += _txt(28, 60, "S/N", 9, SEC, peso="700")
    g += _txt(52, 60, "ZK2600A0001234", 9, TXT, peso="700")
    g += _codigo_barras(28, 68, w=96, h=18)
    g += _txt(78, 24, "NÚMERO DE SÉRIE", 8, SEC, anchor="middle", peso="700")
    g += _txt(78, 158, "tem que bater com a Declaração de Rastreabilidade", 5.2, TXT,
              anchor="middle")
    g += _rodape_regua(20, 116, 122)
    return _svg(g)


def _v_interna():
    tp = "24,46 44,32 128,32 108,46"
    g = (f'<polygon points="{tp}" fill="#F4F6F7" stroke="{SEC}" stroke-width="1.4" '
         f'stroke-dasharray="4 3"/>')
    g += _txt(76, 28, "tampa removida", 5, TXT, anchor="middle")
    g += f'<rect x="24" y="46" width="84" height="66" rx="4" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += _pci(30, 52, 72, 54)
    g += _txt(66, 20, "VISTA INTERNA", 8, SEC, anchor="middle", peso="700")
    g += _rodape_regua(24, 116, 122)
    g += _camera(196, 54) + _seta(198, 66, 150, 80)
    return _svg(g)


def _v_embalagem():
    fr = "30,58 100,58 100,112 30,112"
    tp = "30,58 52,38 122,38 100,58"
    rt = "100,58 122,38 122,92 100,112"
    g = (f'<polygon points="{fr}" fill="#F7F3EA" stroke="{SEC}" stroke-width="1.6"/>'
         f'<polygon points="{tp}" fill="#EFE9DC" stroke="{SEC}" stroke-width="1.6"/>'
         f'<polygon points="{rt}" fill="#E6DFCE" stroke="{SEC}" stroke-width="1.6"/>')
    g += _txt(65, 84, "ZKTeco", 9, SEC, anchor="middle", peso="700")
    g += f'<rect x="40" y="92" width="46" height="14" rx="2" fill="#fff" stroke="{LINHA}"/>'
    g += _txt(63, 102, "modelo / selo", 5, TXT, anchor="middle")
    g += _txt(76, 24, "EMBALAGEM", 8, SEC, anchor="middle", peso="700")
    g += _txt(76, 158, "caixa fechada com marcações e selo ANATEL", 5.2, TXT, anchor="middle")
    g += _rodape_regua(30, 108, 122)
    return _svg(g)


def _v_conjunto():
    g = f'<rect x="16" y="46" width="52" height="56" rx="4" fill="#fff" stroke="{SEC}" stroke-width="1.5"/>'
    g += _txt(42, 78, "produto", 6, TXT, anchor="middle")
    g += f'<rect x="78" y="52" width="44" height="44" rx="4" fill="#F7F3EA" stroke="{SEC}" stroke-width="1.5"/>'
    g += _txt(100, 78, "caixa", 6, TXT, anchor="middle")
    g += f'<rect x="132" y="58" width="36" height="30" rx="4" fill="#fff" stroke="{SEC}" stroke-width="1.5"/>'
    g += _txt(150, 77, "manual", 5.5, TXT, anchor="middle")
    g += _txt(96, 26, "CONJUNTO COMPLETO", 8, SEC, anchor="middle", peso="700")
    g += _txt(96, 158, "tudo que o cliente recebe, em uma foto", 5.2, TXT, anchor="middle")
    g += _rodape_regua(40, 120, 122)
    return _svg(g)


def _v_escala_metrica():
    g = f'<rect x="40" y="38" width="86" height="58" rx="4" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += _seta(40, 106, 126, 106) + _seta(126, 106, 40, 106)
    g += _txt(83, 118, "Largura", 6, ACC, anchor="middle", peso="700")
    g += f'<polygon points="126,38 146,26 146,84 126,96" fill="#EDF1F3" stroke="{SEC}" stroke-width="1.3"/>'
    g += _seta(130, 34, 152, 22)
    g += _txt(180, 28, "Profundidade", 6, ACC, anchor="middle", peso="700")
    g += _txt(83, 22, "ESCALA MÉTRICA", 8, SEC, anchor="middle", peso="700")
    g += _rodape_regua(40, 120, 126)
    return _svg(g)


def _v_pci_com_blindagem():
    g = _pci(14, 34, 116, 68, solda=True)
    g += _blindagem(44, 46, 58, 32)
    g += _txt(73, 66, "BLINDAGEM", 6, SEC, anchor="middle", peso="700")
    g += _txt(73, 22, "PLACAS COM BLINDAGEM", 8, SEC, anchor="middle", peso="700")
    g += _txt(73, 158, "como sai de fábrica, blindagem montada", 5.2, TXT, anchor="middle")
    g += _rodape_regua(14, 116, 122)
    return _svg(g)


def _v_pci_sem_blindagem():
    g = _pci(14, 34, 116, 68, solda=True)
    g += _blindagem(40, 44, 54, 30, aberta=True)
    g += _blindagem(102, 84, 26, 15)
    g += _txt(115, 108, "lata removida", 4.8, TXT, anchor="middle")
    g += _txt(73, 22, "PLACAS SEM BLINDAGEM", 8, SEC, anchor="middle", peso="700")
    g += _txt(73, 158, "inclusive retirando a blindagem dos módulos", 5.2, TXT, anchor="middle")
    g += _rodape_regua(14, 116, 122)
    return _svg(g)


def _v_fonte():
    g = f'<rect x="24" y="34" width="80" height="56" rx="6" fill="#fff" stroke="{SEC}" stroke-width="1.6"/>'
    g += f'<rect x="48" y="24" width="7" height="12" rx="2" fill="{SEC}"/>'
    g += f'<rect x="72" y="24" width="7" height="12" rx="2" fill="{SEC}"/>'
    g += f'<rect x="32" y="42" width="64" height="40" rx="2" fill="#FCFCFA" stroke="{LINHA}"/>'
    g += _txt(36, 52, "INPUT: 100-240V~", 5.4, TXT)
    g += _txt(36, 61, "50/60Hz  0,5A", 5.4, TXT)
    g += _txt(36, 71, "OUTPUT: 12V  2A", 5.4, TXT, peso="700")
    g += _txt(36, 80, "24W", 5.4, TXT)
    g += f'<path d="M104,74 C130,74 130,100 152,100" stroke="{SEC}" stroke-width="2" fill="none"/>'
    g += (f'<circle cx="64" cy="104" r="10" fill="none" stroke="{PRIM}" stroke-width="1.6"/>'
          f'<line x1="71" y1="111" x2="82" y2="122" stroke="{PRIM}" stroke-width="2"/>')
    g += _txt(64, 22, "FONTE DE ALIMENTAÇÃO", 8, SEC, anchor="middle", peso="700")
    g += _txt(150, 130, "tensão, corrente, potência", 5.2, TXT, anchor="middle")
    g += _txt(150, 140, "e frequência legíveis", 5.2, TXT, anchor="middle")
    g += _rodape_regua(24, 96, 122)
    return _svg(g)


def _v_generico():
    g = _painel(40, 36, 100, 74)
    g += _txt(90, 82, "?", 26, LINHA, anchor="middle", peso="700")
    g += _txt(90, 24, "VISTA COMPLEMENTAR", 8, SEC, anchor="middle", peso="700")
    g += _txt(90, 158, "siga a orientação enviada pela OCD", 5.2, TXT, anchor="middle")
    g += _rodape_regua(40, 100, 122)
    return _svg(g)


DESENHOS = {
    "frontal": _v_frontal,
    "traseira": _v_traseira,
    "superior": _v_superior,
    "inferior": _v_inferior,
    "lateral_esquerda": lambda: _v_lateral("esquerda"),
    "lateral_direita": lambda: _v_lateral("direita", escala=True),
    "perspectiva": _v_perspectiva,
    "escala_metrica": _v_escala_metrica,
    "etiqueta": _v_etiqueta,
    "selo_anatel": _v_etiqueta,
    "etiqueta_aplicada": _v_etiqueta_aplicada,
    "numero_serie": _v_numero_serie,
    "interna": _v_interna,
    "placas_na_carcaca": _v_placas_carcaca,
    "pci_componentes": _v_pci_componentes,
    "pci_solda": _v_pci_solda,
    "pci_com_blindagem": _v_pci_com_blindagem,
    "pci_sem_blindagem": _v_pci_sem_blindagem,
    "modulo_rf": _v_modulo_rf,
    "antena": _v_antena,
    "fonte_alimentacao": _v_fonte,
    "embalagem": _v_embalagem,
    "acessorios": _v_acessorios,
    "conjunto": _v_conjunto,
}


def desenho(codigo):
    return DESENHOS.get(codigo, _v_generico)()
