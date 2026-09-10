/* Menu lateral em modo drawer (tablet/mobile) - o botao so aparece nesses
 * tamanhos via CSS; em desktop a sidebar fica fixa e este script fica
 * sem efeito, ja que o botao esta escondido.
 */
(function () {
  var botao = document.querySelector('.menu-alternar');
  var lateral = document.getElementById('menu-lateral');
  var fundo = document.querySelector('.menu-fundo');
  if (!botao || !lateral || !fundo) return;

  function fechar() {
    lateral.classList.remove('aberta');
    fundo.hidden = true;
    botao.setAttribute('aria-expanded', 'false');
  }

  function abrir() {
    lateral.classList.add('aberta');
    fundo.hidden = false;
    botao.setAttribute('aria-expanded', 'true');
  }

  botao.addEventListener('click', function () {
    if (lateral.classList.contains('aberta')) fechar(); else abrir();
  });
  fundo.addEventListener('click', fechar);
  lateral.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', fechar);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') fechar();
  });
})();
