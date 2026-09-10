/* Ajusta o texto da etiqueta ao retângulo dela.
 *
 * A etiqueta tem tamanho FÍSICO (mm) definido pela pessoa. O conteúdo é sempre
 * o mesmo — fabricante, modelo, país, rastreabilidade —, mas o comprimento
 * varia: "China" ocupa cinco letras, "30001447024010189" ocupa dezessete. Com
 * fonte fixa, ou sobra espaço (foi o que aconteceu na impressão) ou o texto
 * estoura a etiqueta.
 *
 * Então a fonte é procurada por bisseção: a maior que ainda couber. Duas casas
 * decimais bastam e doze passos cobrem de 3pt a 30pt com folga.
 */
(function () {
  var MENOR = 3.0;          // pt - abaixo disso ninguém lê
  var MAIOR = 30.0;
  var PASSOS = 12;
  var LEGIVEL = 5.0;        // pt - abaixo disto a etiqueta impressa não se lê

  function cabe(caixa) {
    // Sem tolerância: 1px de folga aqui era 1px de conteúdo passando da caixa,
    // e o overflow:hidden comia justamente a última linha do texto.
    return caixa.scrollWidth <= caixa.clientWidth &&
           caixa.scrollHeight <= caixa.clientHeight;
  }

  /* No SELO o texto nao pode competir com a logo.
   *
   * O selo tem so duas coisas: o desenho e o numero de homologacao. Sem teto, a
   * busca crescia o numero ate 24 pt num selo de 20 mm - o numero tomava a
   * altura toda, a logo era espremida pelo flex e as duas encostavam no quadro
   * (era a "borda comida"). Nao havia estouro para a busca perceber: o flex
   * comprime em vez de transbordar.
   *
   * Medido em selo de 40x20 mm com numero real: 22% da altura deixa a fonte em
   * 12,2 pt, a logo em 45% e uns 13 px de respiro ate a borda.
   */
  var FATIA_DO_NUMERO = 0.22;

  function tetoDaCaixa(caixa) {
    if (!caixa.querySelector('.selo-anatel')) return MAIOR;
    var emPontos = caixa.clientHeight * FATIA_DO_NUMERO * 0.75;   // px -> pt
    return Math.max(MENOR, Math.min(MAIOR, emPontos));
  }

  function ajustar(caixa) {
    var menor = MENOR, maior = tetoDaCaixa(caixa);
    for (var i = 0; i < PASSOS; i++) {
      var meio = (menor + maior) / 2;
      caixa.style.fontSize = meio + 'pt';
      if (cabe(caixa)) { menor = meio; } else { maior = meio; }
    }
    // Sem arredondar: texto quebra em DEGRAUS, nao continuamente. Um centesimo
    // de ponto a mais faz "ZKTECO CO., LTDA." pular para outra linha e estourar
    // a etiqueta inteira - foi exatamente o que um toFixed(2) para cima causou.
    caixa.style.fontSize = menor + 'pt';
    // e confere de fato: se ainda estourou, desce de 0,25 em 0,25 ate caber
    var voltas = 0;
    while (!cabe(caixa) && menor > MENOR && voltas++ < 40) {
      menor = Math.max(MENOR, menor - 0.25);
      caixa.style.fontSize = menor + 'pt';
    }
    caixa.dataset.fonte = menor.toFixed(1);
    caixa.dataset.coube = cabe(caixa) ? '1' : '0';
  }

  function ajustarTudo() {
    var etiquetas = document.querySelectorAll('[data-etiqueta]');
    Array.prototype.forEach.call(etiquetas, ajustar);
    if (!etiquetas.length) return;
    var fontes = Array.prototype.map.call(etiquetas, function (e) {
      return parseFloat(e.dataset.fonte);
    });
    var menor = Math.min.apply(null, fontes);
    // virgula decimal: o sistema inteiro fala portugues
    var mostrador = document.querySelector('[data-fonte-usada]');
    if (mostrador) mostrador.textContent = menor.toFixed(1).replace('.', ',');

    // avisar e mais util do que deixar imprimir uma etiqueta ilegivel
    var aviso = document.querySelector('[data-aviso-fonte]');
    if (aviso) {
      aviso.hidden = menor >= LEGIVEL;
      var valor = aviso.querySelector('[data-fonte-pequena]');
      if (valor) valor.textContent = menor.toFixed(1).replace('.', ',');
    }
  }

  /* ------------------------------------------------ aplicar enquanto digita
   * A barra aplica o tamanho na hora, sem recarregar: mudou o numero, a
   * etiqueta muda junto e o texto se reajusta. O botao "Aplicar" so continua
   * existindo para quem estiver sem JavaScript - aqui ele some.
   * Guardar e outra coisa: vai por tras, com um respiro, para nao gravar uma
   * vez por tecla digitada.
   */
  var ESPERA_PARA_GRAVAR = 500;   // ms depois da ultima mexida
  var gravacao = null;

  function barra() {
    return document.querySelector('[data-barra-etiqueta]');
  }

  function aplicarMedida() {
    var b = barra();
    if (!b) return;
    var largura = parseInt(b.querySelector('[name=largura]').value, 10);
    var altura = parseInt(b.querySelector('[name=altura]').value, 10);
    var folha = document.querySelector('.selos');
    if (folha && largura > 0) folha.style.setProperty('--etiqueta-largura', largura + 'mm');
    if (folha && altura > 0) folha.style.setProperty('--etiqueta-altura', altura + 'mm');

    var rotulo = b.querySelector('[name=quebra_rotulo]');
    var valor = b.querySelector('[name=quebra_valor]');
    Array.prototype.forEach.call(document.querySelectorAll('.selo-dados'), function (t) {
      if (rotulo) t.classList.toggle('quebra-rotulo', rotulo.checked);
      if (valor) t.classList.toggle('sem-quebra-valor', !valor.checked);
    });

    var medida = document.querySelector('[data-medida-atual]');
    if (medida && largura > 0 && altura > 0) {
      medida.textContent = largura + ' × ' + altura + ' mm';
    }
    ajustarTudo();
    agendarGravacao();
  }

  function agendarGravacao() {
    var b = barra();
    if (!b || !b.dataset.gravarEm) return;
    clearTimeout(gravacao);
    gravacao = setTimeout(function () {
      var dados = new FormData();
      dados.append('alvo', b.dataset.alvo || 'etiqueta');
      dados.append('largura', b.querySelector('[name=largura]').value);
      dados.append('altura', b.querySelector('[name=altura]').value);
      var rotulo = b.querySelector('[name=quebra_rotulo]');
      var valor = b.querySelector('[name=quebra_valor]');
      if (rotulo) dados.append('quebra_rotulo', rotulo.checked ? '1' : '');
      if (valor) dados.append('quebra_valor', valor.checked ? '1' : '');
      fetch(b.dataset.gravarEm, { method: 'POST', body: dados })
        .then(function () { marcarGravado(b); })
        .catch(function () { /* sem rede o tamanho continua valendo na tela */ });
    }, ESPERA_PARA_GRAVAR);
  }

  function marcarGravado(b) {
    var recado = b.querySelector('[data-gravado]');
    if (!recado) return;
    recado.hidden = false;
    clearTimeout(recado._sumir);
    recado._sumir = setTimeout(function () { recado.hidden = true; }, 1800);
  }

  function ligarBarra() {
    var b = barra();
    if (!b) return;
    Array.prototype.forEach.call(b.querySelectorAll('input'), function (campo) {
      campo.addEventListener('input', aplicarMedida);
      campo.addEventListener('change', aplicarMedida);
    });
    // o botao so serve a quem esta sem JavaScript; com JS ele vira ruido
    Array.prototype.forEach.call(b.querySelectorAll('[data-so-sem-js]'), function (e) {
      e.hidden = true;
    });
    b.addEventListener('submit', function (e) { e.preventDefault(); aplicarMedida(); });
  }

  document.addEventListener('DOMContentLoaded', ligarBarra);

  // as fontes da página podem chegar depois do DOM; sem isto o primeiro
  // ajuste mede com a fonte errada e a etiqueta sai menor do que podia
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(ajustarTudo);
  }
  document.addEventListener('DOMContentLoaded', ajustarTudo);
  window.addEventListener('resize', ajustarTudo);
  window.addEventListener('beforeprint', ajustarTudo);
  window.ajustarEtiquetas = ajustarTudo;
})();
