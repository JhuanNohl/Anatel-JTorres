/* Prévia ao vivo do seletor de cor do status.
 *
 * A conta é a mesma de app/cores.py — mistura linear com branco (fundo e borda)
 * e com o cinza escuro do tema (texto), escurecendo o texto até o contraste
 * chegar a 4.5:1. Se mudar a fórmula lá, mude aqui também: o que vale de
 * verdade é o Python; isto aqui só evita ter que salvar para ver o resultado.
 */
(function () {
  var BRANCO = [255, 255, 255];
  var ESCURO = [35, 38, 41];
  var CONTRASTE_MINIMO = 4.5;

  function paraRgb(hex) {
    var h = (hex || '').replace('#', '');
    if (h.length === 3) h = h.split('').map(function (d) { return d + d; }).join('');
    return [0, 2, 4].map(function (i) { return parseInt(h.substr(i, 2), 16) || 0; });
  }

  function paraHex(rgb) {
    return '#' + rgb.map(function (c) {
      var v = Math.max(0, Math.min(255, Math.round(c))).toString(16);
      return v.length === 1 ? '0' + v : v;
    }).join('');
  }

  function misturar(cor, alvo, peso) {
    return cor.map(function (c, i) { return c * (1 - peso) + alvo[i] * peso; });
  }

  function luminancia(rgb) {
    var c = rgb.map(function (v) {
      v = v / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }

  function contraste(a, b) {
    var la = luminancia(a), lb = luminancia(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  }

  function derivar(hex) {
    var base = paraRgb(hex);
    var fundo = misturar(base, BRANCO, 0.86);
    var borda = misturar(base, BRANCO, 0.60);
    var peso = 0.40;
    var texto = misturar(base, ESCURO, peso);
    while (contraste(texto, fundo) < CONTRASTE_MINIMO && peso < 0.95) {
      peso += 0.05;
      texto = misturar(base, ESCURO, peso);
    }
    return { fundo: paraHex(fundo), borda: paraHex(borda), texto: paraHex(texto) };
  }

  document.querySelectorAll('.seletor-cor').forEach(function (caixa) {
    var campo = caixa.querySelector('input[type=hidden]');
    var previa = caixa.querySelector('.cor-previa .badge');
    var codigo = caixa.querySelector('.cor-previa code');
    var livre = caixa.querySelector('input[type=color]');
    var nomeStatus = caixa.dataset.exemplo || 'Status';

    function aplicar(hex, vindoDaPaleta) {
      var c = derivar(hex);
      campo.value = hex;
      if (codigo) codigo.textContent = hex.toUpperCase();
      if (previa) {
        previa.style.background = c.fundo;
        previa.style.borderColor = c.borda;
        previa.style.color = c.texto;
        previa.textContent = (campo.form.querySelector('[name=nome]') || {}).value || nomeStatus;
      }
      if (livre && vindoDaPaleta) livre.value = hex;
      caixa.querySelectorAll('.cor-amostra').forEach(function (b) {
        b.classList.toggle('escolhida', b.dataset.cor.toLowerCase() === hex.toLowerCase());
      });
    }

    caixa.querySelectorAll('.cor-amostra').forEach(function (botao) {
      botao.addEventListener('click', function () { aplicar(botao.dataset.cor, true); });
    });
    if (livre) {
      livre.addEventListener('input', function () { aplicar(livre.value, false); });
    }
    var nome = caixa.closest('form').querySelector('[name=nome]');
    if (nome) nome.addEventListener('input', function () { aplicar(campo.value, false); });

    aplicar(campo.value || '#8b9296', true);
  });
})();
