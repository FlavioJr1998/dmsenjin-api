import oracledb
import os
from core.config import DB_USER, DB_PASS, DB_DSN, ORACLE_CLIENT_LIB

def get_db_connection():
    if os.name == "nt":
        oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB)

    return oracledb.connect(
        user=DB_USER,
        password=DB_PASS,
        dsn=DB_DSN
    )