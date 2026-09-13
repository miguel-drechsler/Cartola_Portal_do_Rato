"""Ponte com a API-Football (api-sports.io).

Serve para preencher os scouts sem digitar tudo a mao. O que ela traz vira
rascunho: o admin confere e marca "conferido" antes de processar a rodada.

ATENCAO: o mapeamento abaixo segue a documentacao da API, mas ainda nao foi
conferido com um JSON real da Serie B. Rode primeiro:

    python manage.py coletar_amostra <id_da_partida>

e confira os nomes dos campos no arquivo gerado.

Tres scouts das regras nao vem da API e continuam manuais:
  - bola na trave
  - divisao das defesas do goleiro entre dentro e fora da area
  - penalti sofrido e penalti defendido, que costumam vir vazios fora das ligas grandes
"""
import requests
from django.conf import settings

BASE = "https://v3.football.api-sports.io"
TEMPO_LIMITE = 15


class ErroDaApi(RuntimeError):
    pass


def chamar(endpoint, **parametros):
    chave = settings.API_FOOTBALL_KEY
    if not chave:
        raise ErroDaApi("Defina a variável de ambiente API_FOOTBALL_KEY.")

    resposta = requests.get(
        f"{BASE}/{endpoint}",
        headers={"x-apisports-key": chave},
        params=parametros,
        timeout=TEMPO_LIMITE,
    )
    if resposta.status_code == 429:
        raise ErroDaApi("Cota de requisições da API esgotada (100 por dia no plano grátis).")
    resposta.raise_for_status()

    dados = resposta.json()
    if dados.get("errors"):
        # Costuma ser parametro faltando, chave invalida ou temporada fora do plano.
        raise ErroDaApi(str(dados["errors"]))
    return dados["response"]


def elenco(id_do_time):
    """Jogadores do time, para ligar cada um ao cadastro do jogo."""
    resposta = chamar("players/squads", team=id_do_time)
    return resposta[0]["players"] if resposta else []


def lesionados(id_da_partida):
    """Quem pode desfalcar a partida. Vira sugestao de status, nunca mudanca direta."""
    return chamar("injuries", fixture=id_da_partida)


def numero(valor):
    """A API manda null no lugar de zero em quase todo campo."""
    return int(valor or 0)


def traduzir_estatisticas(estatisticas):
    """Converte o bloco da API nos campos do modelo Scout."""
    jogo = estatisticas.get("games") or {}
    chutes = estatisticas.get("shots") or {}
    gols = estatisticas.get("goals") or {}
    faltas = estatisticas.get("fouls") or {}
    cartoes = estatisticas.get("cards") or {}
    dribles = estatisticas.get("dribbles") or {}
    desarmes = estatisticas.get("tackles") or {}
    penaltis = estatisticas.get("penalty") or {}

    no_gol = numero(chutes.get("on"))
    total = numero(chutes.get("total"))

    # A API nao diz se a expulsao foi por segundo amarelo ou vermelho direto.
    # Nao faz diferenca na pontuacao: com amarelo antes, a secao 5 manda -3 nos
    # dois casos. So o vermelho direto sem amarelo vale -2.
    amarelos = min(numero(cartoes.get("yellow")), 2)
    if numero(cartoes.get("red")) == 0:
        vermelho = "nenhum"
    elif amarelos >= 2:
        vermelho = "segundo_amarelo"
    else:
        vermelho = "direto"

    return {
        "entrou_em_campo": numero(jogo.get("minutes")) > 0,
        "gols": numero(gols.get("total")),
        "assistencias": numero(gols.get("assists")),
        "desarmes": numero(desarmes.get("total")) + numero(desarmes.get("interceptions")),
        # Secao 4: cada finalizacao conta uma vez so. Bola na trave entra a mao
        # depois e o admin desconta de "finalizacoes_fora".
        "finalizacoes_no_gol": no_gol,
        "finalizacoes_fora": max(total - no_gol, 0),
        "dribles": numero(dribles.get("success")),
        "faltas_sofridas": numero(faltas.get("drawn")),
        "faltas_cometidas": numero(faltas.get("committed")),
        "penaltis_sofridos": numero(penaltis.get("won")),
        "penaltis_cometidos": numero(penaltis.get("commited")),  # erro de grafia da propria API
        "penaltis_perdidos": numero(penaltis.get("missed")),
        "penaltis_defendidos": numero(penaltis.get("saved")),
        "cartoes_amarelos": amarelos,
        "cartao_vermelho": vermelho,
        # A API nao separa as defesas por area: tudo entra como defesa de dentro
        # e o admin corrige o que foi de fora.
        "defesas_dentro_area": numero(gols.get("saves")),
    }


def scouts_da_partida(id_da_partida, id_do_time):
    """Devolve {api_id do jogador: campos do Scout} para o time informado."""
    resultado = {}
    for time in chamar("fixtures/players", fixture=id_da_partida):
        if time["team"]["id"] != id_do_time:
            continue
        for item in time["players"]:
            estatisticas = item["statistics"][0] if item.get("statistics") else {}
            resultado[item["player"]["id"]] = traduzir_estatisticas(estatisticas)
    return resultado


FUSO = "America/Recife"
AINDA_NAO_COMECOU = {"NS", "TBD", "PST"}


def erro_de_plano(erro):
    """O plano gratuito recusa alguns parametros, como next e last."""
    texto = str(erro).lower()
    return "plan" in texto or "subscription" in texto


def temporada_atual():
    from django.utils import timezone

    return timezone.now().year


def jogos_da_temporada(id_do_time, temporada=None):
    """Todas as partidas do time na temporada. Uma requisicao so."""
    return chamar(
        "fixtures",
        team=id_do_time,
        season=temporada or temporada_atual(),
        timezone=FUSO,
    )


def proximo_jogo(id_do_time, temporada=None):
    """Proxima partida do time, com ID, data e adversario.

    Tenta o atalho next=1 e, se o plano nao liberar, busca a temporada
    inteira e escolhe o primeiro jogo que ainda nao comecou.
    """
    try:
        resposta = chamar("fixtures", team=id_do_time, next=1, timezone=FUSO)
        if resposta:
            return resposta[0]
    except ErroDaApi as erro:
        if not erro_de_plano(erro):
            raise

    futuros = [
        jogo
        for jogo in jogos_da_temporada(id_do_time, temporada)
        if ((jogo["fixture"].get("status") or {}).get("short") in AINDA_NAO_COMECOU)
    ]
    futuros.sort(key=lambda jogo: jogo["fixture"]["date"])
    return futuros[0] if futuros else None


def partida(id_da_partida, id_do_time=None, temporada=None):
    """Dados de uma partida especifica, incluindo o placar."""
    try:
        resposta = chamar("fixtures", id=id_da_partida, timezone=FUSO)
        if resposta:
            return resposta[0]
    except ErroDaApi as erro:
        if not erro_de_plano(erro):
            raise

    if id_do_time:
        for jogo in jogos_da_temporada(id_do_time, temporada):
            if jogo["fixture"]["id"] == id_da_partida:
                return jogo
    return None


def gols_sofridos(dados_da_partida, id_do_time):
    """Quantos gols o time levou. E o que define o clean sheet (secao 9)."""
    gols = dados_da_partida["goals"]
    em_casa = dados_da_partida["teams"]["home"]["id"] == id_do_time
    sofridos = gols["away"] if em_casa else gols["home"]
    return None if sofridos is None else int(sofridos)


def situacao_da_conta():
    """Plano atual e requisicoes restantes no dia."""
    return chamar("status")