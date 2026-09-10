"""QR code em SVG, sem dependencia nova.

O reportlab (ja usado para gerar PDF) traz um codificador de QR. Aqui so
pegamos a matriz de modulos dele e desenhamos os quadradinhos em SVG - assim o
codigo aparece na tela e imprime bem, sem precisar de biblioteca de imagem nem
de arquivo temporario.
"""

MARGEM = 4          # "zona quieta" exigida pela norma: 4 modulos de folga


def matriz(texto):
    """Lista de listas de booleanos: True = quadrado preto."""
    from reportlab.graphics.barcode import qr
    codigo = qr.QrCodeWidget(texto).qr
    codigo.make()
    lado = codigo.getModuleCount()
    return [[bool(codigo.isDark(linha, coluna)) for coluna in range(lado)]
            for linha in range(lado)]


def svg(texto, tamanho=220, titulo="QR code"):
    """QR pronto para embutir na pagina."""
    pontos = matriz(texto)
    lado = len(pontos) + MARGEM * 2
    quadrados = []
    for linha, colunas in enumerate(pontos):
        inicio = None
        for coluna, escuro in enumerate(colunas + [False]):
            # junta modulos vizinhos numa barra so: menos elementos no SVG
            if escuro and inicio is None:
                inicio = coluna
            elif not escuro and inicio is not None:
                quadrados.append(
                    f'<rect x="{inicio + MARGEM}" y="{linha + MARGEM}" '
                    f'width="{coluna - inicio}" height="1"/>')
                inicio = None
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" '
            f'height="{tamanho}" viewBox="0 0 {lado} {lado}" role="img" '
            f'aria-label="{titulo}" class="qr">'
            f'<rect width="{lado}" height="{lado}" fill="#fff"/>'
            f'<g fill="#111" shape-rendering="crispEdges">{"".join(quadrados)}</g>'
            f'</svg>')
