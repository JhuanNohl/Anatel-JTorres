"""Icones em SVG usados nos botoes de acao das listas.

Ficam num lugar so para que editar/excluir tenham sempre o mesmo desenho em
todas as telas. Sao SVG inline (nao dependem de fonte de emoji, que muda de
maquina para maquina) e herdam a cor do botao por causa do currentColor.

No template basta usar {{ ICO_EDITAR }} - o context_processor de app/__init__.py
publica todos eles, ja como Markup, entao nao sao escapados.
"""
from markupsafe import Markup

_ABRE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">')


def _svg(*partes):
    return Markup(_ABRE + "".join(partes) + "</svg>")


ICO_EDITAR = _svg('<path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>')

ICO_EXCLUIR = _svg(
    '<path d="M3 6h18"/>',
    '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
    '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    '<path d="M10 11v6"/><path d="M14 11v6"/>')

ICO_VER = _svg(
    '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/>',
    '<circle cx="12" cy="12" r="3"/>')

ICO_CAPA = _svg(
    '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 '
    '2 9.27l6.91-1.01L12 2z"/>')

ICO_BAIXAR = _svg(
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>',
    '<path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>')

TODOS = dict(ICO_EDITAR=ICO_EDITAR, ICO_EXCLUIR=ICO_EXCLUIR,
             ICO_VER=ICO_VER, ICO_BAIXAR=ICO_BAIXAR, ICO_CAPA=ICO_CAPA)
