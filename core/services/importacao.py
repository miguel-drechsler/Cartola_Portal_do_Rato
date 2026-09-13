"""Liga a API-Football ao jogo: elenco, rodada e scouts.

Nada aqui grava direto na pontuacao. Os scouts entram como rascunho, com
`conferido` desmarcado, e voce revisa no admin antes de processar a rodada.
Uma ficha ja marcada como conferida nunca e sobrescrita pela importacao.
"""
import re
import unicodedata
from django.conf import settings
from django.db import transaction
from django.utils.dateparse import parse_datetime

from core.models import Jogador, Posicao, Rodada, Scout
from core.services import api_football

CAMPOS_DE_GOLEIRO = ("defesas_dentro_area", "defesas_fora_area", "penaltis_defendidos")


class ErroDeImportacao(RuntimeError):
    pass


def id_do_time():
    valor = getattr(settings, "API_FOOTBALL_TEAM_ID", "")
    if not valor:
        raise ErroDeImportacao(
            "Defina API_FOOTBALL_TEAM_ID com o ID do Náutico na API-Football."
        )
    return int(valor)


def normalizar(nome):
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", sem_acento.lower()).strip()


@transaction.atomic
def vincular_elenco():
    """Preenche o api_id de cada jogador comparando os nomes.

    Devolve (vinculados, sem_correspondencia). Quem nao casar pelo nome voce
    resolve a mao no admin: e so copiar o ID da lista que o comando imprime.
    """
    elenco = api_football.elenco(id_do_time())
    por_nome = {normalizar(p["name"]): p for p in elenco}

    vinculados, sem_correspondencia = [], []
    for jogador in Jogador.objects.filter(no_elenco=True):
        encontrado = None
        for apelido in jogador.lista_apelidos:
            chave = normalizar(apelido)
            encontrado = por_nome.get(chave)
            if encontrado:
                break
            # "Leo Indio" casa com "Leonardo Indio da Costa"
            parciais = [p for nome, p in por_nome.items() if chave and chave in nome]
            if len(parciais) == 1:
                encontrado = parciais[0]
                break

        if encontrado:
            jogador.api_id = encontrado["id"]
            jogador.save(update_fields=["api_id"])
            vinculados.append((jogador.nome, encontrado["name"], encontrado["id"]))
        else:
            sem_correspondencia.append(jogador.nome)

    return vinculados, sem_correspondencia


def numero_da_rodada(dados):
    """Tenta ler o numero da rodada em 'Regular Season - 28'."""
    rodada_api = (dados.get("league") or {}).get("round") or ""
    numeros = re.findall(r"\d+", rodada_api)
    if numeros:
        return int(numeros[-1])
    ultima = Rodada.objects.order_by("-numero").first()
    return (ultima.numero + 1) if ultima else 1


@transaction.atomic
def sincronizar_proxima_rodada():
    """Cria ou atualiza a rodada do proximo jogo do Nautico.

    Se a CBF remarcar, rodar de novo corrige a data, e o fechamento do
    mercado acompanha sozinho.
    """
    time = id_do_time()
    dados = api_football.proximo_jogo(time)
    if not dados:
        raise ErroDeImportacao("A API não retornou nenhum jogo futuro para o time.")

    partida = dados["fixture"]
    times = dados["teams"]
    em_casa = times["home"]["id"] == time
    adversario = times["away"]["name"] if em_casa else times["home"]["name"]

    numero = numero_da_rodada(dados)
    campos = {
        "adversario": adversario,
        "mando": "casa" if em_casa else "fora",
        "data_jogo": parse_datetime(partida["date"]),
        "api_fixture_id": partida["id"],
    }

    # Aproveita a rodada que ja existe: primeiro pelo ID da partida, depois
    # pelo numero. Assim, uma rodada criada a mao no admin e completada em vez
    # de virar uma segunda rodada com o mesmo numero.
    rodada = (
        Rodada.objects.filter(api_fixture_id=partida["id"]).first()
        or Rodada.objects.filter(numero=numero).first()
    )
    if rodada is None:
        rodada = Rodada.objects.create(numero=numero, **campos)
        return rodada, True

    if rodada.processada:
        raise ErroDeImportacao(
            f"A rodada {rodada.numero} já foi processada e não pode ser alterada."
        )
    for campo, valor in campos.items():
        setattr(rodada, campo, valor)
    rodada.numero = numero
    rodada.save()
    return rodada, False


@transaction.atomic
def importar_scouts(rodada):
    """Preenche as fichas da rodada com o que a API traz da partida.

    Devolve (preenchidos, ignorados, protegidos):
      preenchidos  - fichas atualizadas
      ignorados    - jogadores da API sem correspondencia no cadastro
      protegidos   - fichas ja marcadas como conferidas, que nao foram tocadas
    """
    if not rodada.api_fixture_id:
        raise ErroDeImportacao(
            "Esta rodada não tem o ID da partida. Rode a sincronização ou "
            "preencha o campo à mão."
        )
    if rodada.processada:
        raise ErroDeImportacao("Rodada já processada: os scouts não podem mudar.")

    time = id_do_time()
    dados = api_football.scouts_da_partida(rodada.api_fixture_id, time)
    if not dados:
        raise ErroDeImportacao(
            "A API não retornou estatísticas. Confira se a partida já terminou."
        )

    por_api_id = {j.api_id: j for j in Jogador.objects.exclude(api_id=None)}
    preenchidos, ignorados, protegidos = [], [], []

    for api_id, campos in dados.items():
        jogador = por_api_id.get(api_id)
        if jogador is None:
            ignorados.append(api_id)
            continue

        scout, _ = Scout.objects.get_or_create(jogador=jogador, rodada=rodada)
        if scout.conferido:
            protegidos.append(jogador.nome)
            continue

        for campo, valor in campos.items():
            if campo in CAMPOS_DE_GOLEIRO and jogador.posicao != Posicao.GOLEIRO:
                continue
            setattr(scout, campo, valor)
        scout.full_clean()
        scout.save()
        preenchidos.append(jogador.nome)

    partida = api_football.partida(rodada.api_fixture_id, id_do_time=time)
    if partida:
        sofridos = api_football.gols_sofridos(partida, time)
        if sofridos is not None:
            rodada.gols_sofridos = sofridos
            rodada.save(update_fields=["gols_sofridos"])

    return preenchidos, ignorados, protegidos