"""Modelo do arquivo WSGI do PythonAnywhere.

No painel Web, clique no link do arquivo WSGI, apague tudo o que estiver la
e cole este conteudo, trocando SEU_USUARIO pelo seu nome de usuario.

As variaveis de ambiente precisam ficar aqui dentro: o site nao le o .bashrc.
"""
import os
import sys

CAMINHO = "/home/SEU_USUARIO/cartola_nautico"
if CAMINHO not in sys.path:
    sys.path.insert(0, CAMINHO)

# Gere a chave uma vez e guarde: nunca coloque a mesma chave no GitHub.
#   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
os.environ["DJANGO_SECRET_KEY"] = "cole-aqui-a-chave-gerada"
os.environ["DJANGO_DEBUG"] = "0"
os.environ["DJANGO_ALLOWED_HOSTS"] = "SEU_USUARIO.pythonanywhere.com"
os.environ["DJANGO_CSRF_ORIGINS"] = "https://SEU_USUARIO.pythonanywhere.com"
os.environ["DJANGO_SETTINGS_MODULE"] = "cartola.settings"

# Opcional, se for usar a API-Football:
# os.environ["API_FOOTBALL_KEY"] = "sua-chave-da-api"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
