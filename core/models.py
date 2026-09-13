"""Modelos do Cartola Nautico."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from . import pontuacao

MOEDAS_INICIAIS = Decimal("30.00")
HORAS_FECHAMENTO_MERCADO = 24

FORMACAO = {"GOL": 1, "DEF": 2, "MEI": 1, "ATA": 2}


class Posicao(models.TextChoices):
    GOLEIRO = "GOL", "Goleiro"
    DEFENSOR = "DEF", "Defensor"
    MEIO_CAMPISTA = "MEI", "Meio-campista"
    ATACANTE = "ATA", "Atacante"


class StatusJogador(models.TextChoices):
    PROVAVEL = "provavel", "Provável"
    DUVIDA = "duvida", "Dúvida"
    LESIONADO = "lesionado", "Lesionado"
    SUSPENSO = "suspenso", "Suspenso"


class Jogador(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    posicao = models.CharField(max_length=3, choices=Posicao.choices)
    valor = models.DecimalField(
        "valor em Portal Coins",
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("12"))],
    )
    status = models.CharField(
        max_length=12, choices=StatusJogador.choices, default=StatusJogador.PROVAVEL
    )
    noticia_url = models.URLField(
        "link da notícia que justifica o status", blank=True, max_length=500
    )
    apelidos = models.CharField(
        "apelidos separados por vírgula",
        max_length=200,
        blank=True,
        help_text="Como o jogador aparece nas manchetes. Ex.: Léo, Léo Índio",
    )
    no_elenco = models.BooleanField(
        "ainda está no clube",
        default=True,
        help_text="Desmarque quando o jogador deixar o Náutico. "
        "Ele para de pontuar, congela de valor e some do mercado.",
    )
    api_id = models.PositiveIntegerField(
        "ID na API-Football", null=True, blank=True, unique=True
    )

    class Meta:
        verbose_name_plural = "jogadores"
        ordering = ["posicao", "-valor", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_posicao_display()}) — {self.valor} PC"

    @property
    def lista_apelidos(self):
        nomes = [self.nome] + [a.strip() for a in self.apelidos.split(",")]
        return [nome for nome in nomes if nome]


class Rodada(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    adversario = models.CharField(max_length=60)
    mando = models.CharField(
        max_length=4, choices=[("casa", "Em casa"), ("fora", "Fora")], default="casa"
    )
    data_jogo = models.DateTimeField("data e hora do jogo")
    gols_sofridos = models.PositiveIntegerField(
        "gols sofridos pelo Náutico",
        null=True,
        blank=True,
        help_text="Preencha depois do jogo. É o que define o clean sheet.",
    )
    processada = models.BooleanField(default=False)
    api_fixture_id = models.PositiveIntegerField(
        "ID da partida na API-Football",
        null=True,
        blank=True,
        help_text="Opcional. Deixe em branco se você preenche os scouts à mão. "
        "Só é usado para importar os scouts da API.",
    )

    class Meta:
        ordering = ["-numero"]

    def __str__(self):
        return f"Rodada {self.numero} — Náutico x {self.adversario}"

    @property
    def fechamento_mercado(self):
        return self.data_jogo - timedelta(hours=HORAS_FECHAMENTO_MERCADO)

    @property
    def mercado_aberto(self):
        return not self.processada and timezone.now() < self.fechamento_mercado

    @classmethod
    def atual(cls):
        """A proxima rodada ainda nao processada."""
        return cls.objects.filter(processada=False).order_by("numero").first()


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    moedas = models.DecimalField(
        "Portal Coins livres", max_digits=6, decimal_places=2, default=MOEDAS_INICIAIS
    )
    pontos_total = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    time_nome = models.CharField("nome do time", max_length=40, blank=True)

    class Meta:
        ordering = ["-pontos_total"]

    def __str__(self):
        return f"{self.time_nome or self.usuario.username}: {self.pontos_total} pts"

    def patrimonio(self, rodada=None):
        """Moedas livres + valor atual dos jogadores escalados."""
        escalacao = self.escalacao_da_rodada(rodada)
        return self.moedas + (escalacao.custo_atual() if escalacao else Decimal("0"))

    def escalacao_da_rodada(self, rodada=None):
        rodada = rodada or Rodada.atual()
        if rodada is None:
            return None
        return self.usuario.escalacoes.filter(rodada=rodada).first()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)


class Escalacao(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="escalacoes"
    )
    rodada = models.ForeignKey(Rodada, on_delete=models.CASCADE, related_name="escalacoes")
    jogadores = models.ManyToManyField(Jogador, related_name="escalacoes")
    pontos = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    custo = models.DecimalField(
        "custo no momento em que foi salva", max_digits=5, decimal_places=2, default=Decimal("0")
    )
    criada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "escalações"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "rodada"], name="uma_escalacao_por_rodada"
            )
        ]

    def __str__(self):
        return f"{self.usuario.username} — rodada {self.rodada.numero}"

    def custo_atual(self):
        return sum((j.valor for j in self.jogadores.all()), Decimal("0"))


class Scout(models.Model):
    """Acoes de um jogador em uma partida. Uma ficha por jogador por rodada."""

    jogador = models.ForeignKey(Jogador, on_delete=models.CASCADE, related_name="scouts")
    rodada = models.ForeignKey(Rodada, on_delete=models.CASCADE, related_name="scouts")
    entrou_em_campo = models.BooleanField(
        default=False, help_text="Desmarcado = ficou no banco: 0,0 ponto e valor congelado."
    )

    gols = models.PositiveSmallIntegerField(default=0)
    assistencias = models.PositiveSmallIntegerField(default=0)
    desarmes = models.PositiveSmallIntegerField("desarmes e interceptações", default=0)
    finalizacoes_no_gol = models.PositiveSmallIntegerField(default=0)
    finalizacoes_na_trave = models.PositiveSmallIntegerField(default=0)
    finalizacoes_fora = models.PositiveSmallIntegerField(
        "finalizações para fora ou bloqueadas", default=0
    )
    dribles = models.PositiveSmallIntegerField(default=0)
    faltas_sofridas = models.PositiveSmallIntegerField(default=0)
    faltas_cometidas = models.PositiveSmallIntegerField(default=0)
    penaltis_sofridos = models.PositiveSmallIntegerField(default=0)
    penaltis_cometidos = models.PositiveSmallIntegerField(default=0)
    penaltis_perdidos = models.PositiveSmallIntegerField(default=0)
    gols_contra = models.PositiveSmallIntegerField(default=0)

    cartoes_amarelos = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(2)]
    )
    cartao_vermelho = models.CharField(
        max_length=16,
        default=pontuacao.SEM_VERMELHO,
        choices=[
            (pontuacao.SEM_VERMELHO, "Não foi expulso"),
            (pontuacao.VERMELHO_DIRETO, "Vermelho direto"),
            (pontuacao.VERMELHO_SEGUNDO_AMARELO, "Expulso pelo segundo amarelo"),
        ],
    )

    defesas_dentro_area = models.PositiveSmallIntegerField("defesas dentro da área", default=0)
    defesas_fora_area = models.PositiveSmallIntegerField("defesas fora da área", default=0)
    penaltis_defendidos = models.PositiveSmallIntegerField(default=0)

    conferido = models.BooleanField(
        default=False,
        help_text="Marque depois de conferir os dados importados da API.",
    )

    class Meta:
        verbose_name_plural = "scouts"
        constraints = [
            models.UniqueConstraint(
                fields=["jogador", "rodada"], name="um_scout_por_jogador_por_rodada"
            )
        ]

    def __str__(self):
        return f"{self.jogador.nome} — rodada {self.rodada.numero}"

    def clean(self):
        if self.cartao_vermelho == pontuacao.VERMELHO_SEGUNDO_AMARELO and self.cartoes_amarelos != 2:
            raise ValidationError(
                {"cartoes_amarelos": "Expulsão pelo segundo amarelo exige 2 cartões amarelos."}
            )
        if self.jogador_id and self.jogador.posicao != Posicao.GOLEIRO:
            se_goleiro = self.defesas_dentro_area + self.defesas_fora_area + self.penaltis_defendidos
            if se_goleiro:
                raise ValidationError("Defesas só contam para goleiros.")

    def como_dicionario(self):
        campos = list(pontuacao.PESOS_GERAIS) + list(pontuacao.PESOS_GOLEIRO)
        acoes = {campo: getattr(self, campo) for campo in campos}
        acoes["cartoes_amarelos"] = self.cartoes_amarelos
        acoes["cartao_vermelho"] = self.cartao_vermelho
        return acoes

    def pontos(self):
        return pontuacao.calcular_pontuacao(
            self.como_dicionario(),
            self.jogador.posicao,
            self.entrou_em_campo,
            self.rodada.gols_sofridos or 0,
        )
