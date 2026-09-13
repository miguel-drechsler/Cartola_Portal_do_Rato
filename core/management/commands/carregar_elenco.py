"""Cadastra o elenco inicial com os valores da secao 16 das regras."""
from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import Jogador

ELENCO = [
    ("Muriel", "GOL", "6"),
    ("Gastón Guruceaga", "GOL", "2"),
    ("Arnaldo", "DEF", "4"),
    ("Reginaldo", "DEF", "3"),
    ("Betão", "DEF", "5"),
    ("Léo Índio", "DEF", "6"),
    ("Gustavo Henrique", "DEF", "3"),
    ("Wanderson", "DEF", "2"),
    ("Matheus Silva", "DEF", "2"),
    ("Igor Fernandes", "DEF", "5"),
    ("Ryan", "DEF", "3"),
    ("Riquelme", "DEF", "1"),
    ("Samuel", "MEI", "4"),
    ("Auremir", "MEI", "1"),
    ("Wenderson", "MEI", "8"),
    ("Pato Nunes", "MEI", "2"),
    ("Caio Soares", "MEI", "1"),
    ("Hallanzinho", "MEI", "1"),
    ("Luiz Felipe", "MEI", "3"),
    ("Jean Carlos", "ATA", "8"),
    ("Júnior Todinho", "ATA", "3"),
    ("Vinícius", "ATA", "6"),
    ("Borazi", "ATA", "4"),
    ("Danielzinho", "ATA", "5"),
    ("Derek", "ATA", "4"),
    ("Kauã Maranhão", "ATA", "6"),
    ("Luiz Cláudio", "ATA", "4"),
]


class Command(BaseCommand):
    help = "Cadastra o elenco do Náutico com os valores iniciais."

    def handle(self, *args, **opcoes):
        criados = 0
        for nome, posicao, valor in ELENCO:
            _, novo = Jogador.objects.get_or_create(
                nome=nome, defaults={"posicao": posicao, "valor": Decimal(valor)}
            )
            criados += int(novo)
        self.stdout.write(
            self.style.SUCCESS(f"{criados} jogadores cadastrados ({len(ELENCO)} no elenco).")
        )
