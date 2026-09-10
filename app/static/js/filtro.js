/* Filtro ao vivo da lista de produtos.
 *
 * Filtra as linhas conforme se digita, sem recarregar a pagina. O termo pode ser
 * FIXADO (Enter ou botao +): vira uma etiqueta e passa a valer junto com os
 * proximos, permitindo somar filtros ("modulo" + "wi-fi" + "2027").
 *
 * A comparacao ignora acento e maiuscula. Cada linha carrega em data-busca tudo
 * o que ela mostra, montado no servidor.
 */
(function () {
  var caixa = document.querySelector('[data-filtro-vivo]');
  if (!caixa) return;

  var campo = caixa.querySelector('[data-filtro-campo]');
  var etiquetas = caixa.querySelector('[data-filtro-etiquetas]');
  var contador = document.querySelector('[data-filtro-contador]');
  var tabela = document.querySelector('[data-filtro-alvo]');
  var vazio = document.querySelector('[data-filtro-vazio]');
  if (!campo || !tabela) return;

  var linhas = Array.prototype.slice.call(tabela.querySelectorAll('tbody tr'));
  var fixados = [];

  function limpar(texto) {
    // NFD separa a letra do acento; a faixa 0300-036F sao os acentos soltos
    return (texto || '').toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function termos() {
    var atual = limpar(campo.value).trim();
    return fixados.concat(atual ? [atual] : []);
  }

  function aplicar() {
    var alvos = termos();
    var visiveis = 0;
    linhas.forEach(function (linha) {
      var texto = linha.dataset.busca || '';
      var passa = alvos.every(function (t) { return texto.indexOf(t) !== -1; });
      linha.hidden = !passa;
      if (passa) visiveis++;
    });
    if (contador) {
      contador.textContent = visiveis;
      contador.parentElement.classList.toggle('filtrando', alvos.length > 0);
    }
    if (vazio) vazio.hidden = visiveis !== 0;
    desenharEtiquetas();
  }

  function desenharEtiquetas() {
    if (!etiquetas) return;
    etiquetas.innerHTML = '';
    etiquetas.hidden = fixados.length === 0;
    fixados.forEach(function (termo, i) {
      var chip = document.createElement('span');
      chip.className = 'chip chip-filtro';
      chip.appendChild(document.createTextNode(termo));
      var x = document.createElement('button');
      x.type = 'button';
      x.title = 'Remover este filtro';
      x.setAttribute('aria-label', 'Remover filtro ' + termo);
      x.textContent = '×';
      x.addEventListener('click', function () {
        fixados.splice(i, 1);
        aplicar();
      });
      chip.appendChild(x);
      etiquetas.appendChild(chip);
    });
    if (fixados.length > 1) {
      var todos = document.createElement('button');
      todos.type = 'button';
      todos.className = 'btn btn-mini';
      todos.textContent = 'limpar filtros';
      todos.addEventListener('click', function () {
        fixados = [];
        campo.value = '';
        aplicar();
      });
      etiquetas.appendChild(todos);
    }
  }

  function fixar() {
    var termo = limpar(campo.value).trim();
    if (termo && fixados.indexOf(termo) === -1) {
      fixados.push(termo);
    }
    campo.value = '';
    aplicar();
    campo.focus();
  }

  campo.addEventListener('input', aplicar);
  campo.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      fixar();
    }
    if (e.key === 'Backspace' && !campo.value && fixados.length) {
      fixados.pop();
      aplicar();
    }
  });
  var botaoFixar = caixa.querySelector('[data-filtro-fixar]');
  if (botaoFixar) botaoFixar.addEventListener('click', fixar);
  var botaoLimpar = caixa.querySelector('[data-filtro-limpar]');
  if (botaoLimpar) {
    botaoLimpar.addEventListener('click', function () {
      fixados = [];
      campo.value = '';
      aplicar();
      campo.focus();
    });
  }
  aplicar();
})();
