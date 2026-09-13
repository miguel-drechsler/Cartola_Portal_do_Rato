from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from . import mercado
from .models import Escalacao, Jogador, Perfil, Rodada, Scout
from .services import api_football, importacao

admin.site.site_header = "Cartola do Portal"
admin.site.site_title = "Cartola do Portal"
admin.site.index_title = "Administração do jogo"


@admin.register(Jogador)
class JogadorAdmin(admin.ModelAdmin):
    list_display = ("nome", "posicao", "valor", "status", "no_elenco")
    list_filter = ("posicao", "status", "no_elenco")
    list_editable = ("valor", "status", "no_elenco")
    search_fields = ("nome", "apelidos")
    fieldsets = (
        (None, {"fields": ("nome", "posicao", "valor", "no_elenco")}),
        (
            "Situação para a próxima rodada",
            {"fields": ("status", "noticia_url", "apelidos")},
        ),
        (
            "API-Football",
            {
                "classes": ("collapse",),
                "description": "Preenchido pelo comando "
                "<code>sincronizar_api elenco</code>. Só mexa aqui se o "
                "jogador não casou pelo nome.",
                "fields": ("api_id",),
            },
        ),
    )


@admin.register(Rodada)
class RodadaAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "adversario",
        "data_jogo",
        "fechamento_mercado",
        "mercado_aberto",
        "gols_sofridos",
        "processada",
    )
    list_filter = ("processada",)
    actions = ("acao_criar_fichas", "acao_importar_scouts", "acao_processar")
    fieldsets = (
        (None, {"fields": ("numero", "adversario", "mando", "data_jogo")}),
        (
            "Depois do jogo",
            {"fields": ("gols_sofridos", "processada")},
        ),
        (
            "API-Football",
            {
                "classes": ("collapse",),
                "description": "Deixe em branco. O comando "
                "<code>sincronizar_api rodada</code> cria a rodada já com este "
                "campo preenchido.",
                "fields": ("api_fixture_id",),
            },
        ),
    )

    @admin.display(boolean=True, description="mercado aberto")
    def mercado_aberto(self, rodada):
        return rodada.mercado_aberto

    @admin.action(description="1. Criar fichas de scout para o elenco")
    def acao_criar_fichas(self, request, queryset):
        for rodada in queryset:
            criadas = mercado.criar_fichas_de_scout(rodada)
            self.message_user(
                request, f"Rodada {rodada.numero}: {criadas} fichas criadas.", messages.SUCCESS
            )

    @admin.action(description="1b. Importar scouts da API-Football")
    def acao_importar_scouts(self, request, queryset):
        for rodada in queryset:
            try:
                preenchidos, ignorados, protegidos = importacao.importar_scouts(rodada)
            except (importacao.ErroDeImportacao, api_football.ErroDaApi) as erro:
                self.message_user(
                    request, f"Rodada {rodada.numero}: {erro}", messages.ERROR
                )
                continue
            recado = f"Rodada {rodada.numero}: {len(preenchidos)} fichas preenchidas."
            if protegidos:
                recado += f" Mantidas por já estarem conferidas: {', '.join(protegidos)}."
            if ignorados:
                recado += f" {len(ignorados)} jogadores da API sem cadastro aqui."
            self.message_user(request, recado, messages.SUCCESS)
            self.message_user(
                request,
                "Confira os scouts e marque como conferido antes de processar.",
                messages.WARNING,
            )

    @admin.action(description="2. Processar rodada (pontua e valoriza)")
    def acao_processar(self, request, queryset):
        for rodada in queryset:
            try:
                mercado.processar_rodada(rodada)
            except ValidationError as erro:
                self.message_user(
                    request,
                    f"Rodada {rodada.numero}: {' '.join(erro.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request, f"Rodada {rodada.numero} processada.", messages.SUCCESS
                )


@admin.register(Scout)
class ScoutAdmin(admin.ModelAdmin):
    list_display = (
        "jogador",
        "rodada",
        "entrou_em_campo",
        "gols",
        "assistencias",
        "desarmes",
        "finalizacoes_no_gol",
        "cartoes_amarelos",
        "conferido",
        "pontos",
    )
    list_filter = ("rodada", "conferido", "entrou_em_campo", "jogador__posicao")
    list_editable = ("entrou_em_campo", "gols", "assistencias", "desarmes", "conferido")
    search_fields = ("jogador__nome",)
    autocomplete_fields = ("jogador",)

    @admin.display(description="pontos")
    def pontos(self, scout):
        return scout.pontos()

    fieldsets = (
        (None, {"fields": ("rodada", "jogador", "entrou_em_campo", "conferido")}),
        (
            "Ataque",
            {
                "fields": (
                    "gols",
                    "assistencias",
                    "finalizacoes_no_gol",
                    "finalizacoes_na_trave",
                    "finalizacoes_fora",
                    "dribles",
                )
            },
        ),
        ("Defesa", {"fields": ("desarmes",)}),
        (
            "Faltas, pênaltis e cartões",
            {
                "fields": (
                    "faltas_sofridas",
                    "faltas_cometidas",
                    "penaltis_sofridos",
                    "penaltis_cometidos",
                    "penaltis_perdidos",
                    "gols_contra",
                    "cartoes_amarelos",
                    "cartao_vermelho",
                )
            },
        ),
        (
            "Só para goleiros",
            {
                "fields": (
                    "defesas_dentro_area",
                    "defesas_fora_area",
                    "penaltis_defendidos",
                )
            },
        ),
    )


@admin.register(Escalacao)
class EscalacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rodada", "custo", "pontos")
    list_filter = ("rodada",)
    filter_horizontal = ("jogadores",)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "time_nome", "moedas", "pontos_total")
    search_fields = ("usuario__username", "time_nome")
