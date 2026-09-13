"""Testes da importacao, com respostas falsas da API.

Nenhum teste aqui acessa a internet: as chamadas sao substituidas por JSONs
no mesmo formato que a API-Football devolve.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Jogador, Rodada, Scout
from core.services import api_football, importacao

TIME = 123  # ID ficticio do Nautico


def estatisticas(**valores):
    """Monta um bloco no formato da API, com null onde a API manda null."""
    base = {
        "games": {"minutes": valores.get("minutos", 90)},
        "shots": {"total": valores.get("chutes"), "on": valores.get("no_gol")},
        "goals": {
            "total": valores.get("gols"),
            "assists": valores.get("assistencias"),
            "saves": valores.get("defesas"),
        },
        "fouls": {"drawn": valores.get("sofridas"), "committed": valores.get("cometidas")},
        "cards": {"yellow": valores.get("amarelos", 0), "red": valores.get("vermelhos", 0)},
        "dribbles": {"success": valores.get("dribles")},
        "tackles": {"total": valores.get("desarmes"), "interceptions": valores.get("intercepcoes")},
        "penalty": {
            "won": valores.get("penalti_sofrido"),
            "commited": valores.get("penalti_cometido"),
            "missed": valores.get("penalti_perdido"),
            "saved": valores.get("penalti_defendido"),
        },
    }
    return base


class TestTraducao(TestCase):
    def test_null_vira_zero(self):
        campos = api_football.traduzir_estatisticas(estatisticas())
        self.assertEqual(campos["gols"], 0)
        self.assertEqual(campos["finalizacoes_fora"], 0)
        self.assertTrue(campos["entrou_em_campo"])

    def test_quem_nao_jogou(self):
        campos = api_football.traduzir_estatisticas(estatisticas(minutos=None))
        self.assertFalse(campos["entrou_em_campo"])

    def test_finalizacao_nao_conta_duas_vezes(self):
        # 5 chutes, 2 no gol: sobram 3 para fora ou bloqueados.
        campos = api_football.traduzir_estatisticas(estatisticas(chutes=5, no_gol=2))
        self.assertEqual(campos["finalizacoes_no_gol"], 2)
        self.assertEqual(campos["finalizacoes_fora"], 3)

    def test_desarmes_somam_intercepcoes(self):
        campos = api_football.traduzir_estatisticas(estatisticas(desarmes=3, intercepcoes=2))
        self.assertEqual(campos["desarmes"], 5)

    def test_vermelho_direto_sem_amarelo(self):
        campos = api_football.traduzir_estatisticas(estatisticas(vermelhos=1))
        self.assertEqual(campos["cartao_vermelho"], "direto")
        self.assertEqual(campos["cartoes_amarelos"], 0)

    def test_expulsao_com_dois_amarelos(self):
        campos = api_football.traduzir_estatisticas(estatisticas(amarelos=2, vermelhos=1))
        self.assertEqual(campos["cartao_vermelho"], "segundo_amarelo")

    def test_amarelo_sem_expulsao(self):
        campos = api_football.traduzir_estatisticas(estatisticas(amarelos=1))
        self.assertEqual(campos["cartao_vermelho"], "nenhum")


@override_settings(API_FOOTBALL_TEAM_ID=str(TIME), API_FOOTBALL_KEY="chave-de-teste")
class TestImportacao(TestCase):
    def setUp(self):
        self.muriel = Jogador.objects.create(
            nome="Muriel", posicao="GOL", valor=Decimal("6"), api_id=1
        )
        self.derek = Jogador.objects.create(
            nome="Derek", posicao="ATA", valor=Decimal("4"), api_id=2
        )
        self.sem_vinculo = Jogador.objects.create(
            nome="Riquelme", posicao="DEF", valor=Decimal("1")
        )
        self.rodada = Rodada.objects.create(
            numero=28,
            adversario="Sport",
            data_jogo=timezone.now() + timedelta(days=2),
            api_fixture_id=999,
        )

    def resposta_de_jogadores(self):
        return [
            {
                "team": {"id": TIME},
                "players": [
                    {"player": {"id": 1}, "statistics": [estatisticas(defesas=3)]},
                    {
                        "player": {"id": 2},
                        "statistics": [estatisticas(gols=1, chutes=4, no_gol=2, dribles=3)],
                    },
                    {"player": {"id": 77}, "statistics": [estatisticas()]},  # sem cadastro
                ],
            },
            {"team": {"id": 456}, "players": [{"player": {"id": 9}, "statistics": [estatisticas()]}]},
        ]

    def resposta_da_partida(self, gols_casa=2, gols_fora=0):
        return [
            {
                "fixture": {"id": 999, "date": "2026-09-20T19:00:00-03:00"},
                "teams": {"home": {"id": TIME, "name": "Nautico"}, "away": {"id": 456, "name": "Sport"}},
                "goals": {"home": gols_casa, "away": gols_fora},
                "league": {"round": "Regular Season - 28"},
            }
        ]

    def falsa_chamada(self, endpoint, **parametros):
        if endpoint == "fixtures/players":
            return self.resposta_de_jogadores()
        if endpoint == "fixtures":
            return self.resposta_da_partida()
        raise AssertionError(f"endpoint inesperado: {endpoint}")

    def test_importa_scouts_e_placar(self):
        with mock.patch.object(api_football, "chamar", side_effect=self.falsa_chamada):
            preenchidos, ignorados, protegidos = importacao.importar_scouts(self.rodada)

        self.assertEqual(sorted(preenchidos), ["Derek", "Muriel"])
        self.assertEqual(ignorados, [77])
        self.assertEqual(protegidos, [])

        derek = Scout.objects.get(jogador=self.derek, rodada=self.rodada)
        self.assertEqual(derek.gols, 1)
        self.assertEqual(derek.finalizacoes_no_gol, 2)
        self.assertEqual(derek.finalizacoes_fora, 2)
        self.assertEqual(derek.dribles, 3)

        # O adversario nao marcou: clean sheet na conta da rodada.
        self.rodada.refresh_from_db()
        self.assertEqual(self.rodada.gols_sofridos, 0)

        muriel = Scout.objects.get(jogador=self.muriel, rodada=self.rodada)
        self.assertEqual(muriel.defesas_dentro_area, 3)
        self.assertEqual(muriel.pontos(), Decimal("5.00"))  # 3 defesas + clean sheet

    def test_nao_sobrescreve_ficha_ja_conferida(self):
        scout = Scout.objects.create(
            jogador=self.derek, rodada=self.rodada, gols=5, conferido=True
        )
        with mock.patch.object(api_football, "chamar", side_effect=self.falsa_chamada):
            _, _, protegidos = importacao.importar_scouts(self.rodada)

        scout.refresh_from_db()
        self.assertEqual(scout.gols, 5)
        self.assertEqual(protegidos, ["Derek"])

    def test_defesas_nao_vao_para_jogador_de_linha(self):
        self.derek.api_id = 1  # recebe o bloco com defesas
        self.muriel.api_id = 50
        self.muriel.save(update_fields=["api_id"])
        self.derek.save(update_fields=["api_id"])

        with mock.patch.object(api_football, "chamar", side_effect=self.falsa_chamada):
            importacao.importar_scouts(self.rodada)

        scout = Scout.objects.get(jogador=self.derek, rodada=self.rodada)
        self.assertEqual(scout.defesas_dentro_area, 0)

    def test_rodada_sem_id_da_partida(self):
        self.rodada.api_fixture_id = None
        self.rodada.save()
        with self.assertRaises(importacao.ErroDeImportacao):
            importacao.importar_scouts(self.rodada)

    def test_sincroniza_proxima_rodada(self):
        resposta = self.resposta_da_partida()
        resposta[0]["fixture"]["id"] = 1000
        resposta[0]["fixture"]["date"] = "2026-09-27T16:00:00-03:00"
        resposta[0]["teams"]["home"] = {"id": 456, "name": "Ceará"}
        resposta[0]["teams"]["away"] = {"id": TIME, "name": "Nautico"}
        resposta[0]["league"]["round"] = "Regular Season - 29"

        with mock.patch.object(api_football, "chamar", return_value=resposta):
            rodada, criada = importacao.sincronizar_proxima_rodada()

        self.assertTrue(criada)
        self.assertEqual(rodada.numero, 29)
        self.assertEqual(rodada.adversario, "Ceará")
        self.assertEqual(rodada.mando, "fora")
        self.assertEqual(
            rodada.fechamento_mercado, rodada.data_jogo - timedelta(hours=24)
        )

    def test_remarcacao_atualiza_a_mesma_rodada(self):
        resposta = self.resposta_da_partida()
        with mock.patch.object(api_football, "chamar", return_value=resposta):
            importacao.sincronizar_proxima_rodada()
            resposta[0]["fixture"]["date"] = "2026-09-24T21:30:00-03:00"
            rodada, criada = importacao.sincronizar_proxima_rodada()

        self.assertFalse(criada)
        self.assertEqual(Rodada.objects.filter(api_fixture_id=999).count(), 1)
        self.assertEqual(rodada.data_jogo.hour, 21)

    def test_vincula_elenco_por_nome_parcial(self):
        Jogador.objects.create(nome="Léo Índio", posicao="DEF", valor=Decimal("6"))
        elenco = [
            {"id": 10, "name": "Muriel Becker"},
            {"id": 20, "name": "Derek"},
            {"id": 30, "name": "Leonardo Leo Indio da Costa"},
        ]
        with mock.patch.object(api_football, "chamar", return_value=[{"players": elenco}]):
            vinculados, faltando = importacao.vincular_elenco()

        # "Muriel" casa dentro de "Muriel Becker" e "Leo Indio" dentro do nome completo.
        self.assertEqual(len(vinculados), 3)
        self.assertEqual(faltando, ["Riquelme"])

    def test_sem_id_do_time_configurado(self):
        with override_settings(API_FOOTBALL_TEAM_ID=""):
            with self.assertRaises(importacao.ErroDeImportacao):
                importacao.id_do_time()
