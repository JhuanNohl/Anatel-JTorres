/* Dropdown de sugestoes da busca do cabecalho.
 *
 * O formulario continua submetendo para /busca normalmente (botao "Buscar"
 * ou Enter sem item marcado) - o dropdown so intercepta o clique (ou Enter
 * com um item marcado por teclado) para ir direto ao registro escolhido.
 */
(function () {
  var form = document.querySelector('form[data-busca-sugestoes]');
  if (!form) return;

  var url = form.dataset.buscaSugestoes;
  var campo = form.querySelector('input[name=q]');
  var caixa = form.querySelector('.busca-sugestoes');
  if (!campo || !caixa) return;

  var espera = null;
  var itens = [];
  var marcado = -1;

  function fechar() {
    caixa.hidden = true;
    caixa.innerHTML = '';
    itens = [];
    marcado = -1;
  }

  function marcarItem(i) {
    var botoes = caixa.querySelectorAll('.busca-item');
    botoes.forEach(function (b, n) { b.classList.toggle('marcado', n === i); });
    if (botoes[i]) botoes[i].scrollIntoView({ block: 'nearest' });
    marcado = i;
  }

  function ir(item) {
    if (item) window.location.href = item.url;
  }

  function renderizar(lista) {
    itens = lista;
    marcado = -1;
    if (!lista.length) { fechar(); return; }
    caixa.innerHTML = lista.map(function (item, i) {
      return '<button type="button" class="busca-item" data-item="' + i + '">' +
        '<span class="busca-item-tipo">' + item.tipo + '</span>' +
        '<span class="busca-item-titulo"></span>' +
        (item.subtitulo ? '<span class="busca-item-sub"></span>' : '') +
        '</button>';
    }).join('');
    // titulo/subtitulo via textContent (nao innerHTML) para nao correr risco
    // de injetar marcacao vinda dos dados
    caixa.querySelectorAll('.busca-item').forEach(function (botao, i) {
      botao.querySelector('.busca-item-titulo').textContent = lista[i].titulo;
      var sub = botao.querySelector('.busca-item-sub');
      if (sub) sub.textContent = lista[i].subtitulo;
      botao.addEventListener('mousedown', function (ev) {
        ev.preventDefault();          // nao tira o foco do campo antes do click
        ir(itens[i]);
      });
    });
    caixa.hidden = false;
  }

  function buscar(termo) {
    fetch(url + '?q=' + encodeURIComponent(termo))
      .then(function (resp) { return resp.ok ? resp.json() : []; })
      .then(renderizar)
      .catch(function () { fechar(); });
  }

  campo.addEventListener('input', function () {
    var termo = campo.value.trim();
    clearTimeout(espera);
    if (termo.length < 2) { fechar(); return; }
    espera = setTimeout(function () { buscar(termo); }, 220);
  });

  campo.addEventListener('keydown', function (e) {
    if (caixa.hidden || !itens.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      marcarItem(marcado < itens.length - 1 ? marcado + 1 : 0);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      marcarItem(marcado > 0 ? marcado - 1 : itens.length - 1);
    } else if (e.key === 'Enter' && marcado > -1) {
      e.preventDefault();           // com item marcado, vai para ele em vez de submeter
      ir(itens[marcado]);
    } else if (e.key === 'Escape') {
      fechar();
    }
  });

  document.addEventListener('click', function (e) {
    if (!form.contains(e.target)) fechar();
  });
})();
