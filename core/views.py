import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from . import mercado
from .forms import CadastroForm
from .models import Escalacao, Jogador, Rodada


def home(request):
    return render(request, "home.html", {"rodada": Rodada.atual()})


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("escalacao")
    formulario = CadastroForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()
        login(request, usuario)
        messages.success(request, "Conta criada. Bem-vindo ao Cartola Náutico!")
        return redirect("escalacao")
    return render(request, "cadastro.html", {"formulario": formulario})


@login_required
def escalacao(request):
    rodada = Rodada.atual()
    perfil = request.user.perfil
    time_atual = perfil.escalacao_da_rodada(rodada)
    escalados = list(time_atual.jogadores.all()) if time_atual else []

    if request.method == "POST":
        ids = request.POST.getlist("jogadores")
        escolhidos = list(Jogador.objects.filter(id__in=ids))
        try:
            mercado.salvar_escalacao(request.user, rodada, escolhidos)
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
            escalados = escolhidos
        else:
            messages.success(request, "Time salvo para a rodada.")
            return redirect("escalacao")

    jogadores = [
        {
            "id": jogador.id,
            "nome": jogador.nome,
            "posicao": jogador.posicao,
            "valor": float(jogador.valor),
            "status": jogador.get_status_display(),
            "status_chave": jogador.status,
            "noticia": jogador.noticia_url,
        }
        for jogador in Jogador.objects.filter(no_elenco=True)
    ]

    contexto = {
        "rodada": rodada,
        "perfil": perfil,
        "patrimonio": perfil.patrimonio(rodada),
        "jogadores_json": json.dumps(jogadores),
        "escalados_json": json.dumps([j.id for j in escalados]),
        "mercado_aberto": rodada.mercado_aberto if rodada else False,
    }
    return render(request, "escalacao.html", contexto)


def ranking(request):
    rodada_atual = Rodada.atual()
    ultima_processada = Rodada.objects.filter(processada=True).order_by("-numero").first()

    geral = mercado.posicoes_com_empate(
        list(mercado.ranking_geral()), lambda perfil: perfil.pontos_total
    )
    da_rodada = []
    if ultima_processada:
        da_rodada = mercado.posicoes_com_empate(
            list(mercado.ranking_da_rodada(ultima_processada)),
            lambda escalacao: escalacao.pontos,
        )

    return render(
        request,
        "ranking.html",
        {
            "geral": geral,
            "da_rodada": da_rodada,
            "rodada_processada": ultima_processada,
            "rodada": rodada_atual,
        },
    )
