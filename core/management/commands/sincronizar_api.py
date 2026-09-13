"""Comandos da API-Football, num lugar so.

    python manage.py sincronizar_api elenco     # liga cada jogador ao ID da API
    python manage.py sincronizar_api rodada     # cria/atualiza a rodada do proximo jogo
    python manage.py sincronizar_api scouts     # traz os scouts da ultima rodada com ID
"""
from django.core.management.base import BaseCommand, CommandError

from core.models import Rodada
from core.services import api_football, importacao


class Command(BaseCommand):
    help = "Sincroniza elenco, rodada e scouts com a API-Football."

    def add_arguments(self, parser):
        parser.add_argument("acao", choices=["elenco", "rodada", "scouts"])
        parser.add_argument(
            "--rodada", type=int, help="Número da rodada (padrão: a rodada atual)"
        )

    def handle(self, *args, **opcoes):
        try:
            getattr(self, f"acao_{opcoes['acao']}")(opcoes)
        except (importacao.ErroDeImportacao, api_football.ErroDaApi) as erro:
            raise CommandError(str(erro))

    def acao_elenco(self, opcoes):
        vinculados, faltando = importacao.vincular_elenco()
        for nome, nome_api, api_id in vinculados:
            self.stdout.write(f"  {nome} → {nome_api} (id {api_id})")
        self.stdout.write(self.style.SUCCESS(f"{len(vinculados)} jogadores vinculados."))
        if faltando:
            self.stdout.write(
                self.style.WARNING(
                    "Sem correspondência automática (preencha o api_id no admin): "
                    + ", ".join(faltando)
                )
            )

    def acao_rodada(self, opcoes):
        rodada, criada = importacao.sincronizar_proxima_rodada()
        verbo = "criada" if criada else "atualizada"
        self.stdout.write(
            self.style.SUCCESS(
                f"Rodada {rodada.numero} {verbo}: Náutico x {rodada.adversario}, "
                f"{rodada.data_jogo:%d/%m às %H:%M}. "
                f"O mercado fecha {rodada.fechamento_mercado:%d/%m às %H:%M}."
            )
        )

    def acao_scouts(self, opcoes):
        if opcoes["rodada"]:
            rodada = Rodada.objects.filter(numero=opcoes["rodada"]).first()
        else:
            rodada = Rodada.atual()
        if rodada is None:
            raise CommandError("Rodada não encontrada.")

        preenchidos, ignorados, protegidos = importacao.importar_scouts(rodada)
        self.stdout.write(
            self.style.SUCCESS(f"{len(preenchidos)} fichas preenchidas na rodada {rodada.numero}.")
        )
        if protegidos:
            self.stdout.write(f"Já conferidas, mantidas como estavam: {', '.join(protegidos)}")
        if ignorados:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(ignorados)} jogadores da API sem cadastro aqui. "
                    "Rode 'sincronizar_api elenco' se faltou vincular alguém."
                )
            )
        self.stdout.write(
            "Confira as fichas no admin, marque como conferido e só então processe a rodada."
        )
