/* Visor de fotos em pop up, para qualquer galeria da aplicacao.
 *
 * Uso: envolva as fotos num elemento com data-galeria e marque cada imagem com
 * data-visor (o link em volta continua servindo para "abrir original" e para
 * quem estiver sem JavaScript).
 *
 * Dentro do visor:
 *   ‹ ›  ou  setas do teclado    andar entre as fotos
 *   clique na foto               liga/desliga o zoom; com zoom, o mouse passeia
 *   Esc, clique fora, ✕          fecha
 *
 * O estilo (.visor*) e o mesmo do visor das fotos do processo.
 */
(function () {
  var galerias = document.querySelectorAll('[data-galeria]');
  if (!galerias.length) return;

  var visor = null, palco = null, imagem = null;
  var titulo = null, info = null, abrir = null, rodape = null;
  var lista = [], atual = 0, ampliado = false;

  function montar() {
    visor = document.createElement('div');
    visor.className = 'visor';
    visor.hidden = true;
    visor.innerHTML =
      '<div class="visor-topo">' +
        '<div><strong class="visor-titulo"></strong>' +
        '<span class="visor-info"></span></div>' +
        '<div class="visor-acoes">' +
          '<a class="btn btn-mini visor-abrir" target="_blank" rel="noopener">Abrir original</a>' +
          '<button type="button" class="btn btn-mini visor-fechar">✕ Fechar</button>' +
        '</div>' +
      '</div>' +
      '<div class="visor-palco">' +
        '<button type="button" class="visor-nav visor-anterior" title="Anterior (←)">‹</button>' +
        '<img alt="">' +
        '<button type="button" class="visor-nav visor-proxima" title="Próxima (→)">›</button>' +
      '</div>' +
      '<div class="visor-rodape"></div>';
    document.body.appendChild(visor);

    palco = visor.querySelector('.visor-palco');
    imagem = visor.querySelector('.visor-palco img');
    titulo = visor.querySelector('.visor-titulo');
    info = visor.querySelector('.visor-info');
    abrir = visor.querySelector('.visor-abrir');
    rodape = visor.querySelector('.visor-rodape');

    visor.querySelector('.visor-fechar').addEventListener('click', fechar);
    visor.querySelector('.visor-anterior').addEventListener('click', function (e) {
      e.stopPropagation(); andar(-1);
    });
    visor.querySelector('.visor-proxima').addEventListener('click', function (e) {
      e.stopPropagation(); andar(1);
    });
    palco.addEventListener('click', function (e) {
      if (e.target === palco) fechar();               // clique no vazio fecha
    });
    imagem.addEventListener('click', function (e) {
      e.stopPropagation();
      alternarZoom(e);
    });
    imagem.addEventListener('mousemove', function (e) {
      if (ampliado) posicionar(e);
    });
    document.addEventListener('keydown', function (e) {
      if (visor.hidden) return;
      if (e.key === 'Escape') fechar();
      if (e.key === 'ArrowLeft') andar(-1);
      if (e.key === 'ArrowRight') andar(1);
    });
  }

  function alternarZoom(e) {
    ampliado = !ampliado;
    imagem.classList.toggle('ampliada', ampliado);
    if (ampliado) {
      posicionar(e);
    } else {
      imagem.style.transform = '';
      imagem.style.transformOrigin = '';
    }
    atualizarRodape();
  }

  function posicionar(e) {
    // O zoom cresce a partir do ponto clicado. Se a imagem ainda nao tem
    // tamanho (acabou de trocar de src), amplia pelo centro.
    var caixa = imagem.getBoundingClientRect();
    var x = 50, y = 50;
    if (caixa.width > 0 && caixa.height > 0) {
      x = Math.min(100, Math.max(0, ((e.clientX - caixa.left) / caixa.width) * 100));
      y = Math.min(100, Math.max(0, ((e.clientY - caixa.top) / caixa.height) * 100));
    }
    imagem.style.transformOrigin = x.toFixed(2) + '% ' + y.toFixed(2) + '%';
    imagem.style.transform = 'scale(2.5)';
  }

  function atualizarRodape() {
    rodape.innerHTML =
      '<kbd>←</kbd> <kbd>→</kbd> anterior e próxima · ' +
      '<kbd>clique na foto</kbd> ' + (ampliado ? 'volta ao tamanho normal' : 'amplia') +
      ' · <kbd>Esc</kbd> fecha';
  }

  function mostrar(i) {
    atual = (i + lista.length) % lista.length;
    var item = lista[atual];
    if (ampliado) {                                   // troca de foto volta ao normal
      ampliado = false;
      imagem.classList.remove('ampliada');
      imagem.style.transform = '';
    }
    imagem.src = item.src;
    imagem.alt = item.titulo || '';
    titulo.textContent = item.titulo || 'Foto';
    info.textContent = lista.length > 1
      ? ' · ' + (atual + 1) + ' de ' + lista.length : '';
    abrir.href = item.src;
    visor.querySelector('.visor-anterior').hidden = lista.length < 2;
    visor.querySelector('.visor-proxima').hidden = lista.length < 2;
    atualizarRodape();
  }

  function andar(passo) {
    if (lista.length > 1) mostrar(atual + passo);
  }

  function fechar() {
    visor.hidden = true;
    document.body.style.overflow = '';
  }

  function abrirVisor(itens, indice) {
    if (!visor) montar();
    lista = itens;
    visor.hidden = false;
    document.body.style.overflow = 'hidden';
    mostrar(indice);
  }

  Array.prototype.forEach.call(galerias, function (galeria) {
    var imagens = Array.prototype.slice.call(galeria.querySelectorAll('[data-visor]'));
    if (!imagens.length) return;
    var itens = imagens.map(function (img) {
      return { src: img.dataset.original || img.src,
               titulo: img.dataset.titulo || img.alt || '' };
    });
    imagens.forEach(function (img, i) {
      var clicavel = img.closest('a') || img;
      clicavel.addEventListener('click', function (e) {
        e.preventDefault();
        abrirVisor(itens, i);
      });
      img.style.cursor = 'zoom-in';
    });
  });
})();
