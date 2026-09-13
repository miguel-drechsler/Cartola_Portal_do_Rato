"""Backup do banco em um arquivo, para guardar fora do servidor.

    python manage.py backup

Gera um .json com contas, perfis, jogadores, rodadas, escalacoes e scouts.
Funciona igual em SQLite e em Postgres, entao o mesmo arquivo serve para
restaurar em qualquer hospedagem.

Para restaurar num banco vazio:

    python manage.py migrate
    python manage.py loaddata backups/cartola-AAAA-MM-DD.json
"""
from pathlib import Path

from django.conf import settings
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

APLICACOES = ["auth.User", "core"]


class Command(BaseCommand):
    help = "Salva um backup do banco em backups/cartola-<data>.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pasta",
            default=None,
            help="Onde salvar. Padrão: pasta backups/ ao lado do manage.py.",
        )

    def handle(self, *args, **opcoes):
        # Sempre ao lado do manage.py, e nao no diretorio em que voce esta.
        pasta = Path(opcoes["pasta"]) if opcoes["pasta"] else Path(settings.BASE_DIR) / "backups"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"cartola-{timezone.localtime():%Y-%m-%d-%H%M}.json"

        with destino.open("w", encoding="utf-8") as arquivo:
            call_command(
                "dumpdata",
                *APLICACOES,
                indent=2,
                natural_foreign=True,
                natural_primary=True,
                stdout=arquivo,
            )

        tamanho = destino.stat().st_size / 1024
        self.stdout.write(
            self.style.SUCCESS(f"Backup salvo em {destino.resolve()} ({tamanho:.0f} KB).")
        )
        self.stdout.write(
            "Guarde esse arquivo fora do servidor: no seu computador ou no Drive."
        )
        self.stdout.write(
            "As senhas vão criptografadas, mas o arquivo tem e-mails dos "
            "participantes. Não suba para o GitHub."
        )