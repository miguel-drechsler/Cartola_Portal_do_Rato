"""Salva respostas cruas da API-Football para conferir os nomes dos campos.

Uso:
    export API_FOOTBALL_KEY=sua-chave
    python manage.py coletar_amostra --partida 123456

A chave nao aparece nos arquivos gerados, entao da para compartilhar a amostra.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.services import api_football


class Command(BaseCommand):
    help = "Baixa amostras da API-Football para conferir o mapeamento dos scouts."

    def add_arguments(self, parser):
        parser.add_argument("--partida", type=int, help="ID da partida (fixture)")
        parser.add_argument("--time", type=int, help="ID do time na API")
        parser.add_argument("--pasta", default="amostras_api")

    def handle(self, *args, **opcoes):
        pasta = Path(opcoes["pasta"])
        pasta.mkdir(exist_ok=True)
        chamadas = []

        if opcoes["partida"]:
            chamadas += [
                ("fixtures_players", "fixtures/players", {"fixture": opcoes["partida"]}),
                ("injuries", "injuries", {"fixture": opcoes["partida"]}),
            ]
        if opcoes["time"]:
            chamadas.append(("squad", "players/squads", {"team": opcoes["time"]}))
        if not chamadas:
            raise CommandError("Informe --partida e/ou --time.")

        for nome, endpoint, parametros in chamadas:
            try:
                dados = api_football.chamar(endpoint, **parametros)
            except api_football.ErroDaApi as erro:
                self.stderr.write(self.style.ERROR(f"{nome}: {erro}"))
                continue
            destino = pasta / f"{nome}.json"
            destino.write_text(json.dumps(dados, indent=2, ensure_ascii=False))
            self.stdout.write(self.style.SUCCESS(f"{nome}: {destino}"))
