# Cartola Náutico — Portal do Rato (Versão Beta)

Jogo de fantasy do Náutico: 6 jogadores, 30 Portal Coins iniciais, valorização por rodada
e ranking geral. Feito em Django, com telas em HTML, CSS e JavaScript puro.

O jogo roda num servidor só. O torcedor abre o endereço no navegador, cria a
conta e escala o time, sem instalar nada. Os comandos deste arquivo são seus,
para rodar na sua máquina enquanto desenvolve. Para colocar no ar, veja
DEPLOY.md.

## Rodar na sua máquina (desenvolvimento)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py carregar_elenco   # cadastra os 30 jogadores com os valores das regras
python manage.py createsuperuser   # sua conta de administrador
python manage.py runserver
```

Rodar os testes das regras:

```bash
python manage.py test
```

## Como tocar uma rodada

1. No admin, crie a **Rodada**: número, adversário e a data e hora do jogo.
O mercado fecha sozinho 24 horas antes. Se a CBF remarcar, é só mudar a data.
2. Os participantes escalam em **Meu time** enquanto o mercado estiver aberto.
3. Depois do jogo, selecione a rodada no admin e rode a ação
**1. Criar fichas de scout para o elenco**.
4. Preencha as fichas em **Scouts**. Marque *entrou em campo* só para quem jogou.
5. Preencha **gols sofridos** na rodada. É esse campo que define o clean sheet.
6. Rode a ação **2. Processar rodada**. Ela soma os pontos, atualiza o ranking,
valoriza os jogadores e copia as escalações para a rodada seguinte.

## Onde cada regra está no código

| Regra | Arquivo |
| --- | --- |
| Pontuação, cartões, clean sheet e valorização | `core/pontuacao.py` |
| Mercado, patrimônio e processamento da rodada | `core/mercado.py` |
| Tabelas do banco | `core/models.py` |
| Telas | `core/views.py`, `core/templates/` |
| Campo e seletor de jogadores | `core/static/js/escalacao.js` |
| Testes das regras | `core/tests.py` |

`core/pontuacao.py` não acessa o banco: recebe números e devolve números.
Para mudar um peso da tabela, mexa só no dicionário `PESOS_GERAIS` e rode os testes.

## API-Football (opcional)

`core/services/api_football.py` traz os scouts prontos da partida. O mapeamento
segue a documentação, mas ainda não foi conferido com um JSON real da Série B.

```bash
export API_FOOTBALL_KEY=sua-chave
python manage.py coletar_amostra --partida 123456
```

O comando salva as respostas em `amostras_api/`, sem a chave dentro, para você
conferir os nomes dos campos antes de confiar na importação.

Três scouts continuam manuais porque a API não entrega: bola na trave, a divisão
das defesas entre dentro e fora da área, e os pênaltis sofridos e defendidos,
que costumam vir vazios fora das ligas grandes.
