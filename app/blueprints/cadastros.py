"""Cadastros de apoio (OCDs, laboratorios, fabricantes, produtos e vistas de fotos).

Todos usam o mesmo par de telas, descrito pela estrutura CADASTROS.
Cada campo e (nome, rotulo, tipo, extra):
    tipo: texto | area | numero | inteiro | data | bool | select | fk
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..cores import normalizar as normalizar_cor
from ..models import (CATEGORIAS_ANATEL, CategoriaAnexo, ESCOPOS_CHECKLIST,
                      Fabricante, ItemChecklist, Laboratorio,
                      NATUREZAS_PRODUTO, OCD, Processo, Produto, StatusProcesso, Vista)
from ..utils import parse_bool, parse_data, parse_float
from ..verificacao import VERIFICACOES

bp = Blueprint("cadastros", __name__, url_prefix="/cadastros")

# Categorias que o checklist usa. As tres primeiras travam o pacote da OCD.
CATEGORIAS_CHECKLIST = ["Declarações", "Fotos", "Produto e manual",
                        "Requisitos da OCD", "Amostras",
                        "Laboratório", "Financeiro", "Documentos da empresa"]


# O que o sistema sabe conferir sozinho, de app/verificacao.py: com uma destas
# chaves, o item do checklist se resolve quando o anexo, o documento ou a foto
# entra; em branco, voce marca a mao.
CHAVES_VERIFICACAO = sorted(VERIFICACOES)


UF = ["", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
      "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]


def _fabricantes():
    return [(f.id, f.nome) for f in Fabricante.query.order_by(Fabricante.nome).all()]


CAMPOS_ORGANISMO = [
    ("nome", "Nome curto", "texto", dict(obrigatorio=True, dica="Como você chama no dia a dia")),
    ("razao_social", "Razão social", "texto", {}),
    ("endereco", "Endereço (como sai nos documentos)", "texto", {}),
    ("cidade", "Cidade", "texto", {}),
    ("uf", "UF", "select", dict(opcoes=UF)),
    ("cnpj", "CNPJ", "texto", {}),
    ("contato_nome", "Contato", "texto", {}),
    ("email", "E-mail", "texto", {}),
    ("telefone", "Telefone", "texto", {}),
    ("site", "Site", "texto", {}),
    ("observacoes", "Observações", "area", {}),
    ("ativo", "Ativo", "bool", dict(padrao=True)),
]

CADASTROS = {
    "ocds": dict(
        model=OCD, titulo="OCDs", singular="OCD",
        descricao="Organismos de Certificação Designados. Aparecem na seleção do processo e "
                  "no endereçamento das declarações.",
        colunas=[("nome", "Nome"), ("razao_social", "Razão social"), ("cidade", "Cidade"),
                 ("uf", "UF"), ("ativo", "Ativo")],
        campos=CAMPOS_ORGANISMO + [("designacao", "Portaria de designação", "texto", {})],
    ),
    "laboratorios": dict(
        model=Laboratorio, titulo="Laboratórios", singular="Laboratório",
        descricao="Laboratórios de ensaio. Aparecem na seleção do processo.",
        colunas=[("nome", "Nome"), ("razao_social", "Razão social"), ("cidade", "Cidade"),
                 ("uf", "UF"), ("ativo", "Ativo")],
        campos=CAMPOS_ORGANISMO + [
            ("acreditacao", "Acreditação (CGCRE / designação)", "texto", {}),
            ("escopo", "Escopo de ensaios", "texto", {}),
        ],
    ),
    "fabricantes": dict(
        model=Fabricante, titulo="Fabricantes / unidades fabris", singular="Fabricante",
        descricao="Unidade fabril onde a amostra é produzida. Sai na Declaração de "
                  "Rastreabilidade.",
        colunas=[("nome", "Nome"), ("cidade", "Cidade"), ("pais", "País"),
                 ("iso9001", "ISO 9001"), ("ativo", "Ativo")],
        campos=[
            ("nome", "Nome", "texto", dict(obrigatorio=True)),
            ("razao_social", "Razão social", "texto", {}),
            ("endereco", "Endereço completo (como sai nos documentos)", "area", {}),
            ("cidade", "Cidade", "texto", {}),
            ("pais", "País", "texto", dict(padrao="China")),
            ("contato_nome", "Contato", "texto", {}),
            ("email", "E-mail", "texto", {}),
            ("telefone", "Telefone", "texto", {}),
            ("iso9001", "Certificado ISO 9001", "texto", {}),
            ("iso9001_validade", "Validade do ISO 9001", "data", {}),
            ("observacoes", "Observações", "area", {}),
            ("ativo", "Ativo", "bool", dict(padrao=True)),
        ],
    ),
    "produtos": dict(
        model=Produto, titulo="Produtos / modelos", singular="Produto",
        descricao="Base de modelos. É aqui que fica a ficha técnica reaproveitada nos "
                  "processos e nas declarações.",
        colunas=[("modelo", "Modelo"), ("nome_comercial", "Nome comercial"),
                 ("natureza", "Natureza"), ("tipo_equipamento", "Tipo"), ("ativo", "Ativo")],
        campos=[
            ("modelo", "Modelo", "texto", dict(obrigatorio=True)),
            ("nome_comercial", "Nome comercial", "texto", {}),
            ("familia", "Família / linha", "texto", {}),
            ("natureza", "Natureza", "select", dict(opcoes=NATUREZAS_PRODUTO)),
            ("tipo_equipamento", "Tipo de equipamento", "texto",
             dict(dica="Ex.: Módulo Wi-Fi, Leitor de cartão 13,56MHz, Controle de acesso")),
            ("categoria_anatel", "Categoria ANATEL", "select", dict(opcoes=CATEGORIAS_ANATEL)),
            ("fabricante_id", "Fabricante / unidade fabril", "fk", dict(opcoes=_fabricantes)),
            ("descricao", "Descrição", "area", {}),
            ("tecnologias", "Tecnologias de rádio", "texto",
             dict(dica="Ex.: Wi-Fi 2,4 GHz, BLE 5.0, RFID 125 kHz")),
            ("faixas_frequencia", "Faixas de frequência", "texto", {}),
            ("potencia", "Potência máxima", "texto", {}),
            ("alimentacao", "Alimentação", "texto", {}),
            ("bateria", "Bateria", "texto", {}),
            ("dimensoes", "Dimensões", "texto", {}),
            ("peso", "Peso", "texto", {}),
            ("ncm", "NCM", "texto", {}),
            ("gtin", "GTIN / EAN", "texto", {}),
            ("codigo_interno", "Código interno", "texto", {}),
            ("acessorios", "Acessórios comercializados com o produto", "texto",
             dict(dica="Ex.: fonte 12V, cabo USB, suporte. Cada um precisa de foto.")),
            ("possui_radio", "Possui rádio (RF)", "bool", dict(padrao=True)),
            ("conecta_internet",
             "Equipamento terminal com conexão (direta ou indireta) à Internet, ou de "
             "infraestrutura de redes → exige Declaração de Segurança Cibernética", "bool", {}),
            ("fonte_externa", "Alimentado por fonte externa → exige foto da fonte com os "
             "valores nominais", "bool", {}),
            ("classe_i", "Equipamento Classe I → exige a frase de aterramento (ABNT NBR 5410)",
             "bool", {}),
            ("radiacao_restrita", "Radiação restrita → exige a frase da Resolução nº 680/2017",
             "bool", {}),
            ("usuario_final", "Produto para usuário final → exige a frase com o link do SCH",
             "bool", dict(padrao=True)),
            ("observacoes", "Observações", "area", {}),
            ("ativo", "Ativo", "bool", dict(padrao=True)),
        ],
    ),
    "checklist": dict(
        model=ItemChecklist, titulo="Checklist da OCD", singular="Item do checklist",
        descricao="As exigências que a OCD pede em cada processo. É esta lista que o sistema "
                  "copia para o checklist de um processo novo — inclua o que a OCD passar a "
                  "pedir, desative o que ela deixou de exigir e escolha o que é obrigatório.",
        colunas=[("ordem", "Ordem"), ("categoria", "Categoria"), ("descricao", "Exigência"),
                 ("vale_para", "Vale para"), ("obrigatorio", "Obrigatório"),
                 ("automatico", "Automático"), ("ativo", "Ativo")],
        campos=[
            ("descricao", "Exigência", "texto",
             dict(obrigatorio=True,
                  dica="Como a OCD chama o item. Ex.: “Fotos internas das placas”.")),
            ("categoria", "Categoria", "select",
             dict(opcoes=CATEGORIAS_CHECKLIST,
                  dica="Declarações, Fotos e Produto e manual travam o pacote da OCD; "
                       "as outras são acompanhamento interno.")),
            ("detalhe", "Exigência completa, como a OCD escreveu", "area",
             dict(dica="Aparece ao clicar no item, dentro do processo.")),
            ("obrigatorio", "Obrigatório (conta no progresso e trava o pacote)", "bool",
             dict(padrao=True)),
            ("escopo", "Vale para", "select", dict(opcoes=ESCOPOS_CHECKLIST)),
            ("chave", "Verificação automática", "select",
             dict(opcoes=[""] + CHAVES_VERIFICACAO,
                  dica="Em branco, você marca o item à mão. Com uma chave, o sistema resolve "
                       "sozinho quando o anexo, o documento ou a foto entra.")),
            ("ordem", "Ordem", "inteiro",
             dict(dica="Define a posição no checklist. Use 10, 20, 30… para facilitar encaixes.")),
            ("observacoes", "Anotação interna", "area", dict()),
            ("ativo", "Ativo", "bool", dict(padrao=True)),
        ],
    ),
    "categorias-anexo": dict(
        model=CategoriaAnexo, titulo="Categorias de anexo", singular="Categoria de anexo",
        descricao="Os grupos do seletor “Anexar arquivo” e das pastas do pacote da OCD. "
                  "Desative o que não usa; a ordem aqui é a ordem que aparece lá.",
        colunas=[("ordem", "Ordem"), ("nome", "Categoria"), ("em_uso", "Anexos"),
                 ("ativo", "Ativo")],
        campos=[
            ("nome", "Categoria", "texto",
             dict(obrigatorio=True,
                  dica="É este texto que aparece no seletor e no nome da pasta do pacote.")),
            ("ordem", "Ordem", "inteiro",
             dict(dica="Define a posição no seletor. Use 10, 20, 30…")),
            ("observacoes", "Para que serve", "area", dict()),
            ("ativo", "Ativo", "bool", dict(padrao=True)),
        ],
    ),
    "status": dict(
        model=StatusProcesso, titulo="Status do processo", singular="Status",
        descricao="As situações que um processo pode assumir. Aparecem na seleção de status "
                  "do processo, no filtro da lista e no painel.",
        colunas=[("ordem", "Ordem"), ("nome", "Nome"), ("cor", "Cor"),
                 ("exige_justificativa", "Exige justificativa"), ("encerra", "Encerra"),
                 ("ativo", "Ativo")],
        campos=[
            ("nome", "Nome", "texto",
             dict(obrigatorio=True, dica="É este texto que aparece no processo.")),
            ("cor", "Cor da etiqueta", "cor",
             dict(dica="Escolha na paleta ou clique em “Outra cor” para um RGB qualquer. O sistema deriva o fundo, a borda e o tom do texto do crachá.")),
            ("ordem", "Ordem", "inteiro",
             dict(dica="Define a posição na lista. Use 10, 20, 30… para facilitar encaixes.")),
            ("exige_justificativa", "Exigir justificativa ao mudar para este status", "bool",
             dict()),
            ("encerra", "É um status de encerramento (preenche a data de conclusão)", "bool",
             dict()),
            ("observacoes", "Quando usar", "area", dict()),
            ("ativo", "Ativo", "bool", dict(padrao=True)),
        ],
    ),
    "vistas": dict(
        model=Vista, titulo="Vistas de fotos", singular="Vista",
        descricao="Define o roteiro de fotos exigido. Marque como obrigatória o que a OCD "
                  "sempre pede.",
        colunas=[("ordem", "Ordem"), ("nome", "Nome"), ("grupo", "Grupo"),
                 ("obrigatoria", "Obrigatória"), ("ativo", "Ativo"),
                 ("personalizada", "Texto editado")],
        campos=[
            ("codigo", "Código", "texto",
             dict(obrigatorio=True, dica="Sem espaços. Define o desenho de exemplo usado.")),
            ("nome", "Nome", "texto", dict(obrigatorio=True)),
            ("grupo", "Grupo", "texto", dict(padrao="Externas")),
            ("descricao", "O que a foto deve mostrar", "area", {}),
            ("dica", "Dica / erro comum", "area", {}),
            ("obrigatoria", "Obrigatória", "bool", dict(padrao=True)),
            ("ordem", "Ordem", "inteiro", {}),
            ("ativo", "Ativo", "bool", dict(padrao=True)),
        ],
    ),
}


def _config(slug):
    if slug not in CADASTROS:
        from flask import abort
        abort(404)
    return CADASTROS[slug]


def _opcoes(extra):
    opcoes = extra.get("opcoes")
    return opcoes() if callable(opcoes) else (opcoes or [])


def _aplicar(reg, campos, form):
    for nome, _rotulo, tipo, extra in campos:
        if tipo == "bool":
            setattr(reg, nome, parse_bool(form.get(nome)))
        elif tipo == "data":
            setattr(reg, nome, parse_data(form.get(nome)))
        elif tipo == "numero":
            setattr(reg, nome, parse_float(form.get(nome)))
        elif tipo == "inteiro":
            valor = (form.get(nome) or "").strip()
            setattr(reg, nome, int(valor) if valor.lstrip("-").isdigit() else 0)
        elif tipo == "fk":
            valor = form.get(nome)
            setattr(reg, nome, int(valor) if valor else None)
        elif tipo == "cor":
            # normaliza aqui para o banco nunca guardar '#GGG' ou texto solto
            setattr(reg, nome, normalizar_cor(form.get(nome)))
        else:
            setattr(reg, nome, (form.get(nome) or "").strip())


@bp.route("/<slug>")
def lista(slug):
    # Produtos tem area propria (com foto e situacao na ANATEL) - nao duplico a lista.
    if slug == "produtos":
        return redirect(url_for("produtos.lista", q=request.args.get("q") or None))
    cfg = _config(slug)
    model = cfg["model"]
    ordem = getattr(model, "ordem", None)
    consulta = model.query
    q = (request.args.get("q") or "").strip()
    if q:
        campo = "modelo" if slug == "produtos" else "nome"
        consulta = consulta.filter(getattr(model, campo).ilike(f"%{q}%"))
    itens = consulta.order_by(ordem if ordem is not None else
                              getattr(model, "modelo" if slug == "produtos" else "nome")).all()
    return render_template("cadastros/lista.html", cfg=cfg, slug=slug, itens=itens, q=q)


@bp.route("/<slug>/novo", methods=["GET", "POST"])
@bp.route("/<slug>/<int:rid>", methods=["GET", "POST"])
def form(slug, rid=None):
    cfg = _config(slug)
    model = cfg["model"]
    reg = model.query.get_or_404(rid) if rid else None
    if request.method == "POST":
        nome_anterior = reg.nome if (reg and slug == "status") else None
        if not reg:
            reg = model()
            db.session.add(reg)
        _aplicar(reg, cfg["campos"], request.form)
        if slug == "status" and nome_anterior and nome_anterior != reg.nome:
            # o status e gravado no processo pelo nome: renomear leva os processos junto
            afetados = Processo.query.filter_by(status=nome_anterior).update(
                {"status": reg.nome})
            if afetados:
                flash(f"{afetados} processo(s) passaram de “{nome_anterior}” para "
                      f"“{reg.nome}”.", "ok")
        if slug == "vistas":
            # o texto passa a ser seu: a carga inicial nao mexe mais nesta vista
            reg.personalizada = True
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            flash(f"Não foi possível salvar: {exc.orig}", "erro")
            return redirect(url_for("cadastros.lista", slug=slug))
        flash(f"{cfg['singular']} salvo.", "ok")
        return redirect(url_for("cadastros.lista", slug=slug))
    return render_template("cadastros/form.html", cfg=cfg, slug=slug, reg=reg,
                           opcoes=_opcoes)


@bp.route("/vistas/<int:rid>/restaurar", methods=["POST"])
def restaurar_vista(rid):
    """Devolve a vista ao texto padrao do sistema (aplicado na proxima abertura)."""
    reg = Vista.query.get_or_404(rid)
    reg.personalizada = False
    db.session.commit()
    flash("Vista voltará a receber o texto padrão do sistema ao reiniciar. "
          "Seu texto atual continua valendo até lá.", "ok")
    return redirect(url_for("cadastros.form", slug="vistas", rid=rid))


@bp.route("/<slug>/<int:rid>/excluir", methods=["POST"])
def excluir(slug, rid):
    cfg = _config(slug)
    reg = cfg["model"].query.get_or_404(rid)
    if slug == "status":
        em_uso = Processo.query.filter_by(status=reg.nome).count()
        if em_uso:
            flash(f"“{reg.nome}” está em uso por {em_uso} processo(s) e não pode ser "
                  "excluído. Mude o status desses processos primeiro, ou desmarque "
                  "“Ativo” para tirá-lo das novas seleções.", "erro")
            return redirect(url_for("cadastros.lista", slug=slug))
        if StatusProcesso.query.count() <= 1:
            flash("É preciso manter ao menos um status cadastrado.", "erro")
            return redirect(url_for("cadastros.lista", slug=slug))
    try:
        db.session.delete(reg)
        db.session.commit()
        flash(f"{cfg['singular']} excluído.", "ok")
    except IntegrityError:
        db.session.rollback()
        flash(f"Este registro está em uso e não pode ser excluído. "
              f"Desmarque “Ativo” para tirá-lo das listas.", "erro")
    return redirect(url_for("cadastros.lista", slug=slug))
