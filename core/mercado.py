"""Regras de mercado: montar time, processar rodada e valorizar jogadores."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from . import pontuacao
from .models import FORMACAO, Escalacao, Jogador, Perfil, Rodada, Scout


class EscalacaoInvalida(ValidationError):
    pass


def validar_formacao(jogadores):
    if len(jogadores) != sum(FORMACAO.values()):
        raise EscalacaoInvalida("O time precisa ter exatamente 6 jogadores.")
    if len({j.id for j in jogadores}) != len(jogadores):
        raise EscalacaoInvalida("Não dá para escalar o mesmo jogador duas vezes.")
    for posicao, quantidade in FORMACAO.items():
        escolhidos = [j for j in jogadores if j.posicao == posicao]
        if len(escolhidos) != quantidade:
            nome = dict(GOL="goleiro", DEF="defensor", MEI="meio-campista", ATA="atacante")[posicao]
            raise EscalacaoInvalida(
                f"O time precisa de {quantidade} {nome}(s), e não {len(escolhidos)}."
            )
    fora_do_elenco = [j.nome for j in jogadores if not j.no_elenco]
    if fora_do_elenco:
        raise EscalacaoInvalida(
            "Estes jogadores não estão mais no elenco: " + ", ".join(fora_do_elenco)
        )


@transaction.atomic
def salvar_escalacao(usuario, rodada, jogadores):
    """Grava o time do participante e atualiza as moedas livres.

    O patrimonio e a soma das moedas livres com o valor do time atual.
    Depois de salvar, as moedas livres sao o que sobrou do patrimonio.
    """
    if not rodada.mercado_aberto:
        raise EscalacaoInvalida("O mercado desta rodada já fechou.")

    validar_formacao(jogadores)

    perfil = usuario.perfil
    patrimonio = perfil.patrimonio(rodada)
    custo = sum((j.valor for j in jogadores), Decimal("0"))
    if custo > patrimonio:
        raise EscalacaoInvalida(
            f"O time custa {custo:.2f} PC e você tem {patrimonio:.2f} PC."
        )

    escalacao, _ = Escalacao.objects.get_or_create(usuario=usuario, rodada=rodada)
    escalacao.jogadores.set(jogadores)
    escalacao.custo = custo
    escalacao.save()

    perfil.moedas = patrimonio - custo
    perfil.save(update_fields=["moedas"])
    return escalacao


@transaction.atomic
def replicar_escalacoes(rodada_origem, rodada_destino):
    """Secao 1: quem nao mexer no time mantem a escalacao da rodada anterior."""
    criadas = 0
    ja_tem = set(
        rodada_destino.escalacoes.values_list("usuario_id", flat=True)
    )
    for anterior in rodada_origem.escalacoes.prefetch_related("jogadores"):
        if anterior.usuario_id in ja_tem:
            continue
        nova = Escalacao.objects.create(usuario=anterior.usuario, rodada=rodada_destino)
        jogadores = list(anterior.jogadores.all())
        nova.jogadores.set(jogadores)
        nova.custo = sum((j.valor for j in jogadores), Decimal("0"))
        nova.save(update_fields=["custo"])
        criadas += 1
    return criadas


@transaction.atomic
def processar_rodada(rodada):
    """Fecha a rodada: soma os pontos, valoriza os jogadores e abre a proxima."""
    if rodada.processada:
        raise ValidationError("Esta rodada já foi processada.")
    if rodada.gols_sofridos is None:
        raise ValidationError(
            "Preencha quantos gols o Náutico sofreu antes de processar a rodada."
        )

    scouts = Scout.objects.filter(rodada=rodada).select_related("jogador")
    pontos_por_jogador = {scout.jogador_id: scout.pontos() for scout in scouts}

    for escalacao in rodada.escalacoes.select_related("usuario__perfil").prefetch_related(
        "jogadores"
    ):
        total = sum(
            (pontos_por_jogador.get(j.id, Decimal("0")) for j in escalacao.jogadores.all()),
            Decimal("0"),
        )
        escalacao.pontos = total
        escalacao.save(update_fields=["pontos"])
        perfil = escalacao.usuario.perfil
        perfil.pontos_total = perfil.pontos_total + total
        perfil.save(update_fields=["pontos_total"])

    for scout in scouts:
        jogador = scout.jogador
        if not scout.entrou_em_campo or not jogador.no_elenco:
            continue
        jogador.valor = pontuacao.novo_valor(jogador.valor, pontos_por_jogador[jogador.id])
        jogador.save(update_fields=["valor"])

    rodada.processada = True
    rodada.save(update_fields=["processada"])

    proxima = (
        Rodada.objects.filter(processada=False, numero__gt=rodada.numero)
        .order_by("numero")
        .first()
    )
    if proxima:
        replicar_escalacoes(rodada, proxima)
    return rodada


def criar_fichas_de_scout(rodada):
    """Cria uma ficha em branco para cada jogador do elenco."""
    criadas = 0
    for jogador in Jogador.objects.filter(no_elenco=True):
        _, novo = Scout.objects.get_or_create(jogador=jogador, rodada=rodada)
        criadas += int(novo)
    return criadas


def ranking_geral():
    return Perfil.objects.select_related("usuario").order_by("-pontos_total", "usuario__username")


def ranking_da_rodada(rodada):
    return (
        rodada.escalacoes.select_related("usuario__perfil")
        .order_by("-pontos", "usuario__username")
    )


def posicoes_com_empate(itens, chave):
    """Participantes empatados dividem a mesma posicao no ranking (secao 15)."""
    resultado = []
    posicao_anterior = 0
    pontos_anteriores = None
    for indice, item in enumerate(itens, start=1):
        pontos = chave(item)
        if pontos == pontos_anteriores:
            posicao = posicao_anterior
        else:
            posicao = indice
            posicao_anterior = indice
            pontos_anteriores = pontos
        resultado.append((posicao, item))
    return resultado
