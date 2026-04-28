from fastapi import FastAPI, Depends, HTTPException
import oracledb

# Importa a função do seu arquivo de configuração
from core.database import get_db_connection
from app.veiculos.router import router as veiculos_router
app = FastAPI(
    title="API_BASE_APOLLO",
    description="API para automações e dashboards",
    version="0.1.0"
)
app.include_router( veiculos_router)

@app.get("/teste-conexao", tags=["Testes de Infraestrutura"])

def testar_conexao(conn: oracledb.Connection = Depends(get_db_connection)):
    """
    Rota simples para validar a comunicação entre a API e o banco Oracle.
    """
    try:
        cursor = conn.cursor()
        
        # A clássica consulta no DUAL para teste. 
        # Você pode substituir pela sua própria query de teste aqui!
        query = "SELECT * FROM GER_EMPRESA"
        
        cursor.execute(query)
        resultado = cursor.fetchone()
        
        return {
            "status": "sucesso",
            "mensagem_banco": resultado[0]
        }
        
    except oracledb.Error as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao executar a query de teste: {str(e)}"
        )
    finally:
        # Importante: O FastAPI vai fechar a conexão automaticamente devido ao 'yield'
        # no get_db_connection, mas o cursor nós fechamos aqui.
        cursor.close()