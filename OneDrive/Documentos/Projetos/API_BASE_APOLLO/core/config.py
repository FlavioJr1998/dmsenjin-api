import os
from dotenv import load_dotenv

load_dotenv()

ORACLE_CLIENT_LIB = os.getenv("ORACLE_CLIENT_LIB")

EMPRESA = int(os.getenv("EMPRESA", 2))

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

if os.getenv('AMBIENTE_DESCRICAO') == 'PRODUCAO':
    AMBIENTE_DESCRICAO = 'PRODUÇÃO'
    DB_DSN = os.getenv("DB_DSN_PROD")
else:
    DB_DSN = os.getenv("DB_DSN_HOMO")
