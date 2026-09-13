"""Testes das regras do Cartola Nautico.

Cada teste aponta a secao das regras que ele verifica.
Rode com: python manage.py test
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from . import mercado, pontuacao
from .models import Escalacao, Jogador, Rodada, Scout


def acoes(**kwargs):
    return kwargs


class TestValorizacao(TestCase):
    """Secao 12 — os seis exemplos das regras oficiais."""

    def test_exemplos_das_regras(self):
        casos = [
            ("5.0", "4.10"),
            ("5.5", "4.15"),
            ("6.0", "4.20"),
            ("3.0", "3.90"),
            ("2.5", "3.85"),
            ("4.0", "4.00"),
        ]
        for pontos, esperado in casos:
            with self.subTest(pontos=pontos):
                self.assertEqual(
                    pontuacao.novo_valor(Decimal("4"), Decimal(pontos)), Decimal(esperado)
                )

    def test_arredonda_em_duas_casas(self):
        # 4,15 PC com 5,0 pontos: 4,15 + 0,085 = 4,235 -> 4,24
        self.assertEqual(
            pontuacao.novo_valor(Decimal("4.15"), Decimal("5.0")), Decimal("4.24")
        )

    def test_respeita_o_teto_de_12(self):
        self.assertEqual(
            pontuacao.novo_valor(Decimal("11.95"), Decimal("30")), Decimal("12")
        )

    def test_respeita_o_piso_de_1(self):
        self.assertEqual(
            pontuacao.novo_valor(Decimal("1.05"), Decimal("-20")), Decimal("1")
        )

    def test_quem_fica_no_banco_nao_muda_de_valor(self):
        self.assertEqual(
            pontuacao.novo_valor(Decimal("6"), Decimal("0"), entrou_em_campo=False),
            Decimal("6.00"),
        )


class TestCartoes(TestCase):
    """Secao 5 — a expulsao substitui o desconto dos amarelos."""

    def test_amarelo_sozinho(self):
        self.assertEqual(pontuacao.pontos_de_cartoes(1), Decimal("-1.0"))

    def test_vermelho_direto_sem_amarelo(self):
        self.assertEqual(
            pontuacao.pontos_de_cartoes(0, pontuacao.VERMELHO_DIRETO), Decimal("-2.0")
        )

    def test_dois_amarelos_com_expulsao(self):
        self.assertEqual(
            pontuacao.pontos_de_cartoes(2, pontuacao.VERMELHO_SEGUNDO_AMARELO),
            Decimal("-3.0"),
        )

    def test_amarelo_mais_vermelho_direto(self):
        self.assertEqual(
            pontuacao.pontos_de_cartoes(1, pontuacao.VERMELHO_DIRETO), Decimal("-3.0")
        )


class TestPontuacao(TestCase):
    """Secoes 3, 4, 6, 7, 8, 9 e 11."""

    def test_gol_soma_tambem_a_finalizacao(self):
        # Um gol de dentro: +8,0 do gol e +0,5 da finalizacao no gol.
        pontos = pontuacao.calcular_pontuacao(
            acoes(gols=1, finalizacoes_no_gol=1), "ATA", True, 2
        )
        self.assertEqual(pontos, Decimal("8.50"))

    def test_atacante_completo(self):
        pontos = pontuacao.calcular_pontuacao(
            acoes(
                gols=1,
                finalizacoes_no_gol=2,
                finalizacoes_fora=3,
                dribles=2,
                faltas_sofridas=4,
                faltas_cometidas=1,
                cartoes_amarelos=1,
            ),
            "ATA",
            True,
            1,
        )
        # 8 + 1 + 0,3 + 1 + 0,4 - 0,2 - 1 = 9,5
        self.assertEqual(pontos, Decimal("9.50"))

    def test_penalti_perdido_e_gol_contra(self):
        self.assertEqual(
            pontuacao.calcular_pontuacao(acoes(penaltis_perdidos=1), "ATA", True, 1),
            Decimal("-3.00"),
        )
        self.assertEqual(
            pontuacao.calcular_pontuacao(acoes(gols_contra=1), "DEF", True, 1),
            Decimal("-3.00"),
        )

    def test_goleiro_com_penalti_defendido(self):
        # +5,0 do penalti e +1,0 de uma defesa dentro da area, sem contar duas vezes.
        pontos = pontuacao.calcular_pontuacao(
            acoes(penaltis_defendidos=1, defesas_dentro_area=1), "GOL", True, 3
        )
        self.assertEqual(pontos, Decimal("6.00"))

    def test_defesas_nao_contam_para_jogador_de_linha(self):
        pontos = pontuacao.calcular_pontuacao(
            acoes(defesas_dentro_area=3), "DEF", True, 1
        )
        self.assertEqual(pontos, Decimal("0.00"))

    def test_clean_sheet_para_quem_entrou_em_campo(self):
        self.assertEqual(
            pontuacao.calcular_pontuacao({}, "DEF", True, 0), Decimal("2.00")
        )
        self.assertEqual(
            pontuacao.calcular_pontuacao({}, "GOL", True, 0), Decimal("2.00")
        )

    def test_clean_sheet_nao_vale_para_meia_nem_atacante(self):
        self.assertEqual(pontuacao.calcular_pontuacao({}, "MEI", True, 0), Decimal("0.00"))
        self.assertEqual(pontuacao.calcular_pontuacao({}, "ATA", True, 0), Decimal("0.00"))

    def test_gol_sofrido_derruba_o_clean_sheet(self):
        self.assertEqual(pontuacao.calcular_pontuacao({}, "DEF", True, 1), Decimal("0.00"))

    def test_banco_zera_a_pontuacao(self):
        pontos = pontuacao.calcular_pontuacao(
            acoes(gols=2, desarmes=5), "ATA", False, 0
        )
        self.assertEqual(pontos, Decimal("0.00"))


class BaseComElenco(TestCase):
    def setUp(self):
        self.jogadores = {}
        elenco = [
            ("Muriel", "GOL", "6"),
            ("Guruceaga", "GOL", "2"),
            ("Léo Índio", "DEF", "6"),
            ("Riquelme", "DEF", "1"),
            ("Arnaldo", "DEF", "4"),
            ("Wenderson", "MEI", "8"),
            ("Auremir", "MEI", "1"),
            ("Jean Carlos", "ATA", "8"),
            ("Derek", "ATA", "4"),
            ("Borazi", "ATA", "4"),
        ]
        for nome, posicao, valor in elenco:
            self.jogadores[nome] = Jogador.objects.create(
                nome=nome, posicao=posicao, valor=Decimal(valor)
            )
        self.rodada = Rodada.objects.create(
            numero=1,
            adversario="Sport",
            data_jogo=timezone.now() + timedelta(days=3),
        )
        self.usuario = User.objects.create_user("miguel", password="timbu-1901")

    def time_padrao(self):
        # 6 + 1 + 4 + 1 + 4 + 4 = 20 PC
        return [
            self.jogadores[nome]
            for nome in ("Muriel", "Riquelme", "Arnaldo", "Auremir", "Derek", "Borazi")
        ]


class TestMercado(BaseComElenco):
    """Secoes 1 e 2."""

    def test_salva_time_valido_e_atualiza_o_saldo(self):
        mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())
        perfil = self.usuario.perfil
        perfil.refresh_from_db()
        self.assertEqual(perfil.moedas, Decimal("10.00"))
        self.assertEqual(perfil.patrimonio(self.rodada), Decimal("30.00"))

    def test_recusa_formacao_errada(self):
        time = self.time_padrao()
        time[0] = self.jogadores["Jean Carlos"]  # tres atacantes, nenhum goleiro
        with self.assertRaises(ValidationError):
            mercado.salvar_escalacao(self.usuario, self.rodada, time)

    def test_recusa_time_acima_do_patrimonio(self):
        caro = [
            self.jogadores[nome]
            for nome in ("Muriel", "Léo Índio", "Arnaldo", "Wenderson", "Jean Carlos", "Derek")
        ]  # 36 PC
        with self.assertRaises(ValidationError):
            mercado.salvar_escalacao(self.usuario, self.rodada, caro)

    def test_recusa_jogador_repetido(self):
        time = self.time_padrao()
        time[5] = time[4]
        with self.assertRaises(ValidationError):
            mercado.salvar_escalacao(self.usuario, self.rodada, time)

    def test_recusa_jogador_fora_do_elenco(self):
        self.jogadores["Derek"].no_elenco = False
        self.jogadores["Derek"].save()
        with self.assertRaises(ValidationError):
            mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())

    def test_mercado_fecha_24h_antes(self):
        self.assertTrue(self.rodada.mercado_aberto)
        self.rodada.data_jogo = timezone.now() + timedelta(hours=23)
        self.rodada.save()
        self.assertFalse(self.rodada.mercado_aberto)
        with self.assertRaises(ValidationError):
            mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())

    def test_trocar_jogador_devolve_o_valor_do_vendido(self):
        mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())
        novo_time = self.time_padrao()
        novo_time[1] = self.jogadores["Léo Índio"]  # sai Riquelme (1), entra Leo (6)
        mercado.salvar_escalacao(self.usuario, self.rodada, novo_time)
        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.moedas, Decimal("5.00"))


class TestProcessamento(BaseComElenco):
    """Secoes 9, 11, 12 e 15."""

    def setUp(self):
        super().setUp()
        mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())
        mercado.criar_fichas_de_scout(self.rodada)

    def test_soma_os_pontos_do_time_e_valoriza(self):
        self.rodada.gols_sofridos = 0
        self.rodada.save()

        muriel = Scout.objects.get(rodada=self.rodada, jogador=self.jogadores["Muriel"])
        muriel.entrou_em_campo = True
        muriel.defesas_dentro_area = 2  # +2,0 e +2,0 do clean sheet
        muriel.save()

        derek = Scout.objects.get(rodada=self.rodada, jogador=self.jogadores["Derek"])
        derek.entrou_em_campo = True
        derek.gols = 1
        derek.finalizacoes_no_gol = 1  # +8,5
        derek.save()

        for nome in ("Riquelme", "Arnaldo"):
            scout = Scout.objects.get(rodada=self.rodada, jogador=self.jogadores[nome])
            scout.entrou_em_campo = True  # so o clean sheet: +2,0 cada
            scout.save()

        mercado.processar_rodada(self.rodada)

        escalacao = Escalacao.objects.get(usuario=self.usuario, rodada=self.rodada)
        # 4,0 (Muriel) + 2,0 + 2,0 (defensores) + 8,5 (Derek) + 0 (Auremir e Borazi no banco)
        self.assertEqual(escalacao.pontos, Decimal("16.50"))
        self.usuario.perfil.refresh_from_db()
        self.assertEqual(self.usuario.perfil.pontos_total, Decimal("16.50"))

        self.jogadores["Derek"].refresh_from_db()
        self.assertEqual(self.jogadores["Derek"].valor, Decimal("4.45"))

        self.jogadores["Borazi"].refresh_from_db()
        self.assertEqual(self.jogadores["Borazi"].valor, Decimal("4.00"))

    def test_nao_processa_sem_informar_os_gols_sofridos(self):
        with self.assertRaises(ValidationError):
            mercado.processar_rodada(self.rodada)

    def test_nao_processa_duas_vezes(self):
        self.rodada.gols_sofridos = 1
        self.rodada.save()
        mercado.processar_rodada(self.rodada)
        with self.assertRaises(ValidationError):
            mercado.processar_rodada(self.rodada)

    def test_time_e_mantido_na_rodada_seguinte(self):
        proxima = Rodada.objects.create(
            numero=2, adversario="Ceará", data_jogo=timezone.now() + timedelta(days=10)
        )
        self.rodada.gols_sofridos = 2
        self.rodada.save()
        mercado.processar_rodada(self.rodada)

        nova = Escalacao.objects.get(usuario=self.usuario, rodada=proxima)
        self.assertEqual(
            {j.nome for j in nova.jogadores.all()},
            {j.nome for j in self.time_padrao()},
        )

    def test_empate_divide_a_mesma_posicao(self):
        outro = User.objects.create_user("torcedor2", password="timbu-1901")
        for perfil, pontos in ((self.usuario.perfil, "10"), (outro.perfil, "10")):
            perfil.pontos_total = Decimal(pontos)
            perfil.save()
        posicoes = mercado.posicoes_com_empate(
            list(mercado.ranking_geral()), lambda perfil: perfil.pontos_total
        )
        self.assertEqual([posicao for posicao, _ in posicoes], [1, 1])


class TestTelas(BaseComElenco):
    def test_home_abre_sem_login(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_meu_time_exige_login(self):
        resposta = self.client.get("/meu-time/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/entrar/", resposta.url)

    def test_salva_o_time_pela_tela(self):
        self.client.login(username="miguel", password="timbu-1901")
        resposta = self.client.post(
            "/meu-time/", {"jogadores": [j.id for j in self.time_padrao()]}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            Escalacao.objects.filter(usuario=self.usuario, rodada=self.rodada).exists()
        )

    def test_ranking_abre(self):
        self.assertEqual(self.client.get("/ranking/").status_code, 200)


class TestHerancaDeEscalacao(BaseComElenco):
    """A ordem entre criar a proxima rodada e processar a atual nao importa."""

    def test_rodada_criada_depois_do_processamento_herda_o_time(self):
        mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())
        self.rodada.gols_sofridos = 1
        self.rodada.save()
        mercado.processar_rodada(self.rodada)

        proxima = Rodada.objects.create(
            numero=2, adversario="Ceará", data_jogo=timezone.now() + timedelta(days=10)
        )
        nova = Escalacao.objects.get(usuario=self.usuario, rodada=proxima)
        self.assertEqual(nova.jogadores.count(), 6)

    def test_nao_duplica_quando_as_duas_copias_acontecem(self):
        proxima = Rodada.objects.create(
            numero=2, adversario="Ceará", data_jogo=timezone.now() + timedelta(days=10)
        )
        mercado.salvar_escalacao(self.usuario, self.rodada, self.time_padrao())
        self.rodada.gols_sofridos = 0
        self.rodada.save()
        mercado.processar_rodada(self.rodada)

        self.assertEqual(
            Escalacao.objects.filter(usuario=self.usuario, rodada=proxima).count(), 1
        )
