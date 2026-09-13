/* Escalação: seis vagas, um seletor por posição e o saldo sempre visível.
   Toda validação também roda no servidor — aqui é só para o torcedor ver o que
   está acontecendo enquanto monta o time. */
(function () {
  "use strict";

  var script = document.currentScript;
  var mercadoAberto = script.dataset.mercadoAberto === "1";
  var patrimonio = parseFloat(script.dataset.patrimonio);

  var jogadores = JSON.parse(document.getElementById("dados-jogadores").textContent);
  var escalados = JSON.parse(document.getElementById("dados-escalados").textContent);

  var porId = {};
  jogadores.forEach(function (jogador) { porId[jogador.id] = jogador; });

  var vagas = Array.prototype.slice.call(document.querySelectorAll(".vaga"));
  var seletor = document.getElementById("seletor");
  var lista = document.getElementById("lista-jogadores");
  var tituloSeletor = document.getElementById("seletor-titulo");
  var saldoElemento = document.getElementById("saldo");
  var camposOcultos = document.getElementById("campos-ocultos");
  var formulario = document.getElementById("formulario-time");
  var botaoSalvar = document.getElementById("salvar");

  var nomesDePosicao = { GOL: "Goleiro", DEF: "Defensor", MEI: "Meio-campista", ATA: "Atacante" };
  var escolha = {};   // chave da vaga -> id do jogador
  var vagaAberta = null;

  function preencherComTimeSalvo() {
    escalados.forEach(function (id) {
      var jogador = porId[id];
      if (!jogador) return;
      var vagaLivre = vagas.find(function (vaga) {
        return vaga.dataset.posicao === jogador.posicao && !escolha[vaga.dataset.vaga];
      });
      if (vagaLivre) escolha[vagaLivre.dataset.vaga] = id;
    });
  }

  function custoAtual() {
    return Object.keys(escolha).reduce(function (total, chave) {
      var jogador = porId[escolha[chave]];
      return jogador ? total + jogador.valor : total;
    }, 0);
  }

  function desenhar() {
    vagas.forEach(function (vaga) {
      var id = escolha[vaga.dataset.vaga];
      var jogador = porId[id];
      vaga.disabled = !mercadoAberto;
      vaga.classList.toggle("ocupada", Boolean(jogador));
      if (jogador) {
        var alerta = jogador.status_chave === "provavel" ? "" : '<span class="alerta" title="' + jogador.status + '">⚠</span>';
        vaga.innerHTML =
          '<span class="nome">' + jogador.nome + "</span>" +
          '<span class="preco">' + jogador.valor.toFixed(2) + " PC</span>" + alerta;
        vaga.setAttribute("aria-label", nomesDePosicao[vaga.dataset.posicao] + ": " + jogador.nome + ". Trocar.");
      } else {
        vaga.innerHTML = '<span class="rotulo">' + nomesDePosicao[vaga.dataset.posicao] + "</span>";
        vaga.setAttribute("aria-label", "Escolher " + nomesDePosicao[vaga.dataset.posicao].toLowerCase());
      }
    });

    var sobra = patrimonio - custoAtual();
    saldoElemento.textContent = sobra.toFixed(2);
    saldoElemento.parentElement.classList.toggle("estourado", sobra < 0);

    camposOcultos.innerHTML = "";
    Object.keys(escolha).forEach(function (chave) {
      var campo = document.createElement("input");
      campo.type = "hidden";
      campo.name = "jogadores";
      campo.value = escolha[chave];
      camposOcultos.appendChild(campo);
    });

    var completo = Object.keys(escolha).length === vagas.length;
    if (botaoSalvar) botaoSalvar.disabled = !mercadoAberto || !completo || sobra < 0;
  }

  function abrirSeletor(vaga) {
    vagaAberta = vaga;
    var posicao = vaga.dataset.posicao;
    tituloSeletor.textContent = "Escolher " + nomesDePosicao[posicao].toLowerCase();
    lista.innerHTML = "";

    var jaEscalados = Object.keys(escolha)
      .filter(function (chave) { return chave !== vaga.dataset.vaga; })
      .map(function (chave) { return escolha[chave]; });

    var sobraSemEstaVaga = patrimonio - custoAtual() +
      (porId[escolha[vaga.dataset.vaga]] ? porId[escolha[vaga.dataset.vaga]].valor : 0);

    jogadores
      .filter(function (jogador) { return jogador.posicao === posicao; })
      .sort(function (a, b) { return b.valor - a.valor || a.nome.localeCompare(b.nome); })
      .forEach(function (jogador) {
        var item = document.createElement("li");
        var botao = document.createElement("button");
        botao.type = "button";
        botao.disabled = jaEscalados.indexOf(jogador.id) !== -1 || jogador.valor > sobraSemEstaVaga;

        var motivo = "";
        if (jaEscalados.indexOf(jogador.id) !== -1) motivo = "já está no time";
        else if (jogador.valor > sobraSemEstaVaga) motivo = "acima do seu saldo";

        botao.innerHTML =
          '<span class="jogador-info"><span>' + jogador.nome + "</span>" +
          '<span class="jogador-status ' + jogador.status_chave + '">' +
          (motivo || jogador.status) + "</span></span>" +
          '<span class="jogador-preco">' + jogador.valor.toFixed(2) + " PC</span>";

        botao.addEventListener("click", function () {
          escolha[vaga.dataset.vaga] = jogador.id;
          seletor.close();
          desenhar();
        });

        item.appendChild(botao);
        lista.appendChild(item);
      });

    if (typeof seletor.showModal === "function") seletor.showModal();
    else seletor.setAttribute("open", "");
  }

  vagas.forEach(function (vaga) {
    vaga.addEventListener("click", function () {
      if (mercadoAberto) abrirSeletor(vaga);
    });
  });

  var botaoLimpar = document.getElementById("limpar");
  if (botaoLimpar) {
    botaoLimpar.addEventListener("click", function () {
      escolha = {};
      desenhar();
    });
  }

  if (formulario) {
    formulario.addEventListener("submit", function (evento) {
      if (Object.keys(escolha).length !== vagas.length) {
        evento.preventDefault();
        alert("Complete as seis vagas antes de salvar.");
      }
    });
  }

  preencherComTimeSalvo();
  desenhar();
})();
