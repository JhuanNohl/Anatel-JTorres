/* Envio de fotos sem recarregar a página.
   O problema que isto resolve: cada cartão é um formulário; enviar um recarregava a
   página inteira e apagava as fotos já escolhidas nos outros cartões.
   Agora a foto sobe sozinha assim que é escolhida (ou arrastada) e nada se perde. */

(function () {
  "use strict";

  var painel = document.querySelector("[data-fotos]");
  if (!painel || !window.fetch) return;   // sem JS o formulário normal continua funcionando

  // com envio automático o botão "Enviar" deixa de fazer sentido
  painel.classList.add("envio-automatico");

  function porCartao(cartao, seletor) {
    return cartao.querySelector(seletor);
  }

  function estado(cartao, texto, tipo) {
    var alvo = porCartao(cartao, ".estado-envio");
    if (!alvo) return;
    alvo.className = "estado-envio " + (tipo || "");
    alvo.textContent = texto || "";
    alvo.hidden = !texto;
  }

  function atualizarContagem(cartao) {
    var total = cartao.querySelectorAll(".mini").length;
    var etiqueta = porCartao(cartao, "[data-contagem]");
    if (etiqueta) {
      etiqueta.textContent = total + (total === 1 ? " foto" : " fotos");
      etiqueta.hidden = total === 0;
    }
    var na = cartao.dataset.na === "1";
    var obrigatoria = cartao.dataset.obrigatoria === "1";
    cartao.classList.toggle("pronta", !na && total > 0);
    cartao.classList.toggle("pendente", !na && obrigatoria && total === 0);
    var selo = porCartao(cartao, "[data-selo]");
    if (selo && !na && obrigatoria) selo.className = "badge " + (total ? "ok" : "warn");
  }

  function atualizarResumo(resumo) {
    var aviso = document.querySelector("[data-resumo]");
    if (!aviso || !resumo) return;
    if (resumo.faltando === 0) {
      aviso.className = "aviso ok";
      aviso.innerHTML = "<span>✓</span><div>Todas as " + resumo.total_obrigatorias +
        " vistas obrigatórias têm foto.</div>";
      return;
    }
    var atalhos = resumo.nomes_faltando.map(function (nome, i) {
      return '<a href="#vista-' + resumo.codigos_faltando[i] + '" class="chip">' + nome + "</a>";
    }).join("");
    aviso.className = "aviso erro";
    aviso.innerHTML = "<span>!</span><div><strong>Faltam " + resumo.faltando + " de " +
      resumo.total_obrigatorias + " vistas obrigatórias:</strong> " + atalhos + "</div>";
  }

  function miniatura(cartao, foto) {
    var galeria = porCartao(cartao, ".miniaturas");
    if (!galeria) {
      galeria = document.createElement("div");
      galeria.className = "miniaturas";
      cartao.insertBefore(galeria, porCartao(cartao, ".rodape"));
    }
    var caixa = document.createElement("div");
    caixa.className = "mini nova";
    caixa.innerHTML =
      '<a href="' + foto.url + '" target="_blank"><img src="' + foto.url + '" alt=""></a>' +
      '<form method="post" action="' + foto.excluir_url + '" class="js-excluir">' +
      '<button class="x" title="Remover">×</button></form>' +
      "<small>" + (foto.largura ? foto.largura + "×" + foto.altura : foto.nome) + "</small>";
    galeria.appendChild(caixa);
    ligarExclusao(caixa.querySelector(".js-excluir"));
    setTimeout(function () { caixa.classList.remove("nova"); }, 900);
  }

  function enviar(cartao, arquivos) {
    if (!arquivos || !arquivos.length) return;
    var dados = new FormData();
    if (cartao.dataset.vista) dados.append("vista_id", cartao.dataset.vista);
    var legenda = porCartao(cartao, "[name=legenda]");
    if (legenda) dados.append("legenda", legenda.value);
    for (var i = 0; i < arquivos.length; i++) dados.append("fotos", arquivos[i]);

    cartao.classList.add("enviando");
    estado(cartao, "Enviando " + arquivos.length +
      (arquivos.length === 1 ? " foto…" : " fotos…"), "carregando");

    fetch(painel.dataset.envio, {
      method: "POST", body: dados, headers: { "X-Requested-With": "fetch" }
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (dados) {
      cartao.classList.remove("enviando");
      (dados.fotos || []).forEach(function (foto) { miniatura(cartao, foto); });
      atualizarContagem(cartao);
      atualizarResumo(dados.resumo);
      if (dados.erros && dados.erros.length) {
        estado(cartao, dados.erros.join(" "), "erro");
      } else {
        estado(cartao, "✓ " + dados.fotos.length +
          (dados.fotos.length === 1 ? " foto enviada" : " fotos enviadas"), "ok");
        setTimeout(function () { estado(cartao, ""); }, 4000);
      }
    }).catch(function () {
      cartao.classList.remove("enviando");
      estado(cartao, "Não foi possível enviar. Verifique o arquivo e tente de novo.", "erro");
    });
  }

  function excluirFoto(form) {
    var cartao = form.closest("[data-vista-cartao]");
    return fetch(form.action, { method: "POST", headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.json(); })
      .then(function (dados) {
        var mini = form.closest(".mini");
        if (mini) mini.remove();
        if (cartao) atualizarContagem(cartao);
        atualizarResumo(dados.resumo);
      });
  }

  function ligarExclusao(form) {
    if (!form) return;
    form.addEventListener("submit", function (evento) {
      evento.preventDefault();
      if (!confirm("Remover esta foto?")) return;
      excluirFoto(form);
    });
  }

  /* ---------------------------------------------------------------- visor
     Clicar na miniatura abre a foto em pop up, sem sair da tela.
     Setas do teclado passam de uma para outra; Esc fecha. */
  var visor = null, fotos = [], atual = 0;

  function montarVisor() {
    visor = document.createElement("div");
    visor.className = "visor";
    visor.hidden = true;
    visor.innerHTML =
      '<div class="visor-topo">' +
        '<div><strong class="visor-titulo"></strong>' +
        '<span class="visor-info"></span></div>' +
        '<div class="visor-acoes">' +
          '<a class="btn btn-mini visor-abrir" target="_blank" rel="noopener">Abrir original</a>' +
          '<button type="button" class="btn btn-mini btn-perigo visor-remover">Remover foto</button>' +
          '<button type="button" class="btn btn-mini visor-fechar">✕ Fechar</button>' +
        "</div></div>" +
      '<div class="visor-palco">' +
        '<button type="button" class="visor-nav visor-anterior" title="Anterior">‹</button>' +
        '<img alt="">' +
        '<button type="button" class="visor-nav visor-proxima" title="Próxima">›</button>' +
      "</div>" +
      '<div class="visor-rodape"></div>';
    document.body.appendChild(visor);

    visor.querySelector(".visor-fechar").addEventListener("click", fechar);
    visor.querySelector(".visor-anterior").addEventListener("click", function () { andar(-1); });
    visor.querySelector(".visor-proxima").addEventListener("click", function () { andar(1); });
    visor.addEventListener("click", function (e) {
      // clicar no fundo (fora da imagem e dos botões) fecha
      if (e.target === visor || e.target.classList.contains("visor-palco")) fechar();
    });
    visor.querySelector(".visor-remover").addEventListener("click", function () {
      var mini = fotos[atual];
      if (!mini || !confirm("Remover esta foto?")) return;
      var form = mini.querySelector(".js-excluir");
      excluirFoto(form).then(function () {
        fotos.splice(atual, 1);
        if (!fotos.length) return fechar();
        if (atual >= fotos.length) atual = fotos.length - 1;
        mostrar();
      });
    });
    document.addEventListener("keydown", function (e) {
      if (visor.hidden) return;
      if (e.key === "Escape") fechar();
      if (e.key === "ArrowLeft") andar(-1);
      if (e.key === "ArrowRight") andar(1);
    });
  }

  function mostrar() {
    var mini = fotos[atual];
    var link = mini.querySelector("a");
    var cartao = mini.closest("[data-vista-cartao]");
    var titulo = cartao && cartao.querySelector("h3");
    var legenda = mini.querySelector("small");

    visor.querySelector(".visor-palco img").src = link.getAttribute("href");
    visor.querySelector(".visor-titulo").textContent =
      titulo ? titulo.textContent.trim() : "Foto avulsa";
    visor.querySelector(".visor-info").textContent =
      (legenda ? " · " + legenda.textContent.trim() : "");
    visor.querySelector(".visor-abrir").href = link.getAttribute("href");
    visor.querySelector(".visor-anterior").hidden = fotos.length < 2;
    visor.querySelector(".visor-proxima").hidden = fotos.length < 2;
    visor.querySelector(".visor-rodape").innerHTML = fotos.length > 1
      ? "Foto " + (atual + 1) + " de " + fotos.length +
        " · use <kbd>←</kbd> <kbd>→</kbd> para passar · <kbd>Esc</kbd> para fechar"
      : "<kbd>Esc</kbd> para fechar";
  }

  function abrir(mini) {
    if (!visor) montarVisor();
    fotos = Array.prototype.slice.call(document.querySelectorAll(".mini"));
    atual = fotos.indexOf(mini);
    if (atual < 0) return;
    visor.hidden = false;
    document.body.style.overflow = "hidden";
    mostrar();
  }

  function andar(passo) {
    if (fotos.length < 2) return;
    atual = (atual + passo + fotos.length) % fotos.length;
    mostrar();
  }

  function fechar() {
    if (!visor) return;
    visor.hidden = true;
    document.body.style.overflow = "";
  }

  // delegação: vale também para as miniaturas que aparecem depois de enviar
  document.addEventListener("click", function (e) {
    var link = e.target.closest && e.target.closest(".mini a");
    if (!link) return;
    e.preventDefault();
    abrir(link.closest(".mini"));
  });

  // ---- liga tudo
  document.querySelectorAll("[data-vista-cartao]").forEach(function (cartao) {
    var campo = porCartao(cartao, "input[type=file]");
    if (!campo) return;

    campo.addEventListener("change", function () {
      enviar(cartao, campo.files);
      campo.value = "";          // libera o campo para a próxima escolha
    });

    ["dragenter", "dragover"].forEach(function (evt) {
      cartao.addEventListener(evt, function (e) {
        e.preventDefault();
        cartao.classList.add("arrastando");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      cartao.addEventListener(evt, function (e) {
        e.preventDefault();
        if (evt === "dragleave" && cartao.contains(e.relatedTarget)) return;
        cartao.classList.remove("arrastando");
      });
    });
    cartao.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files.length) enviar(cartao, e.dataTransfer.files);
    });
  });

  document.querySelectorAll(".js-excluir").forEach(ligarExclusao);
})();
