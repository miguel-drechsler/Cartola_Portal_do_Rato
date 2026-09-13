"""Motor de pontuacao e de valorizacao do Cartola Nautico.

Funcoes puras, sem acesso ao banco: recebem numeros e devolvem numeros.
Cada regra abaixo esta numerada conforme as REGRAS OFICIAIS.
"""
from decimal import Decimal, ROUND_HALF_UP

CENTAVO = Decimal("0.01")
FATOR_VALORIZACAO = Decimal("0.1")
VALOR_MINIMO = Decimal("1")
VALOR_MAXIMO = Decimal("12")
BONUS_CLEAN_SHEET = Decimal("2.0")

# Secao 3 das regras. Vale para qualquer jogador.
PESOS_GERAIS = {
    "gols": Decimal("8.0"),
    "assistencias": Decimal("5.0"),
    "desarmes": Decimal("1.0"),
    "finalizacoes_no_gol": Decimal("0.5"),
    "finalizacoes_na_trave": Decimal("0.3"),
    "finalizacoes_fora": Decimal("0.1"),
    "faltas_sofridas": Decimal("0.1"),
    "dribles": Decimal("0.5"),
    "penaltis_sofridos": Decimal("3.0"),
    "faltas_cometidas": Decimal("-0.2"),
    "penaltis_cometidos": Decimal("-3.0"),
    "penaltis_perdidos": Decimal("-3.0"),
    "gols_contra": Decimal("-3.0"),
}

# Secao 8 das regras. So conta para goleiros.
PESOS_GOLEIRO = {
    "defesas_dentro_area": Decimal("1.0"),
    "defesas_fora_area": Decimal("0.5"),
    "penaltis_defendidos": Decimal("5.0"),
}

SEM_VERMELHO = "nenhum"
VERMELHO_DIRETO = "direto"
VERMELHO_SEGUNDO_AMARELO = "segundo_amarelo"


def pontos_de_cartoes(amarelos, vermelho=SEM_VERMELHO):
    """Secao 5: a expulsao substitui o desconto dos amarelos, nao soma."""
    if vermelho == VERMELHO_SEGUNDO_AMARELO:
        return Decimal("-3.0")
    if vermelho == VERMELHO_DIRETO:
        return Decimal("-3.0") if amarelos >= 1 else Decimal("-2.0")
    return Decimal("-1.0") * amarelos


def tem_clean_sheet(posicao, entrou_em_campo, gols_sofridos):
    """Secao 9: goleiro ou defensor que pisou em campo, com o time sem sofrer gol."""
    return bool(entrou_em_campo) and posicao in ("GOL", "DEF") and gols_sofridos == 0


def calcular_pontuacao(acoes, posicao, entrou_em_campo, gols_sofridos):
    """Pontuacao de um jogador na rodada.

    acoes: dicionario com os scouts da partida.
    posicao: GOL, DEF, MEI ou ATA.
    entrou_em_campo: False para quem ficou no banco (secao 11).
    gols_sofridos: gols que o Nautico levou na partida inteira.
    """
    if not entrou_em_campo:
        return Decimal("0.00")

    total = Decimal("0")
    for campo, peso in PESOS_GERAIS.items():
        total += peso * acoes.get(campo, 0)

    if posicao == "GOL":
        for campo, peso in PESOS_GOLEIRO.items():
            total += peso * acoes.get(campo, 0)

    total += pontos_de_cartoes(
        acoes.get("cartoes_amarelos", 0),
        acoes.get("cartao_vermelho", SEM_VERMELHO),
    )

    if tem_clean_sheet(posicao, entrou_em_campo, gols_sofridos):
        total += BONUS_CLEAN_SHEET

    return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def novo_valor(valor_atual, pontos, entrou_em_campo=True):
    """Secao 12: a cada ponto acima do valor atual, +0,1 PC (e vice-versa)."""
    if not entrou_em_campo:
        return Decimal(valor_atual).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    valor_atual = Decimal(valor_atual)
    variacao = (Decimal(pontos) - valor_atual) * FATOR_VALORIZACAO
    valor = (valor_atual + variacao).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return min(max(valor, VALOR_MINIMO), VALOR_MAXIMO)
