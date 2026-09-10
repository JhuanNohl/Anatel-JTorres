/* Fecha os paineis <details class="decisao"> ao clicar fora.
 *
 * O <details> do HTML so fecha clicando de novo no proprio botao, o que e
 * incomodo quando ele abre por cima da tabela. Aqui: clicar em qualquer lugar
 * fora fecha, Esc fecha, e abrir um fecha os outros.
 */
(function () {
  var SELETOR = 'details.decisao';

  function abertos() {
    return Array.prototype.slice.call(document.querySelectorAll(SELETOR + '[open]'));
  }

  function fechar(exceto) {
    abertos().forEach(function (d) {
      if (d !== exceto) d.open = false;
    });
  }

  // clique em qualquer lugar: se foi fora do painel aberto, fecha
  document.addEventListener('click', function (e) {
    var dentro = e.target.closest ? e.target.closest(SELETOR) : null;
    fechar(dentro);
  });

  // abrir um fecha os demais (o evento toggle nao borbulha, dai o captura)
  document.addEventListener('toggle', function (e) {
    if (e.target.matches && e.target.matches(SELETOR) && e.target.open) {
      fechar(e.target);
    }
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') fechar(null);
  });
})();
