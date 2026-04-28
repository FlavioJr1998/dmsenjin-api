from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date
import oracledb

# Ajuste o import conforme a localização exata do seu get_db_connection
from core.database import get_db_connection
from app.veiculos.query.query_consulta_estoque import query_base_consulta

# Criamos o router específico para veículos
router = APIRouter(
    prefix="/api/v1/veiculos",
    tags=["Veículos"]
)

QUERY_BASE = query_base_consulta()

# 2. FUNÇÃO AUXILIAR: Evita repetição de código e previne SQL Injection (Bind Variables)
def buscar_estoque_dinamico(conn: oracledb.Connection, tipo_veiculo: str = None):
    try:
        cursor = conn.cursor()
        query = QUERY_BASE
        parametros = {}
        
        # Se um tipo for passado ('N' ou 'U'), adiciona o filtro na query e no dicionário de parâmetros
        if tipo_veiculo:
            query += " AND V.NOVO_USADO = :tipo"
            parametros['tipo'] = tipo_veiculo
            
        # Adiciona a ordenação no final da montagem da query
        query += " ORDER BY V.REVENDA_ORIGEM, V.VEICULO"
        
        # Executa passando os parâmetros bind (segurança máxima para o Oracle)
        cursor.execute(query, parametros)
        
        colunas = [col[0] for col in cursor.description]
        resultados = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
        
        return resultados

    except oracledb.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de banco: {str(e)}")
    finally:
        cursor.close()

# 3. AS ROTAS DE NEGÓCIO
@router.get("/estoque/geral", summary="Consulta de Estoque Geral (Novos e Usados)")
def consultar_estoque_geral(conn: oracledb.Connection = Depends(get_db_connection)):
    """ Retorna todos os veículos em estoque, sem distinção prévia. """
    dados = buscar_estoque_dinamico(conn, tipo_veiculo=None)
    return {"status": "sucesso", "total_registros": len(dados), "dados": dados}

@router.get("/estoque/novos", summary="Consulta apenas veículos NOVOS")
def consultar_estoque_novos(conn: oracledb.Connection = Depends(get_db_connection)):
    """ Retorna apenas os veículos O KM (Novos) em estoque. """
    dados = buscar_estoque_dinamico(conn, tipo_veiculo='N')
    return {"status": "sucesso", "total_registros": len(dados), "dados": dados}

@router.get("/estoque/usados", summary="Consulta apenas veículos USADOS")
def consultar_estoque_usados(conn: oracledb.Connection = Depends(get_db_connection)):
    """ Retorna apenas os veículos Seminovos/Usados em estoque. """
    dados = buscar_estoque_dinamico(conn, tipo_veiculo='U')
    return {"status": "sucesso", "total_registros": len(dados), "dados": dados}

# ==========================================
# ÁREA COMERCIAL - DASHBOARDS DE VENDAS
# ==========================================

@router.get("/vendas/totais", summary="Total e Faturamento de Vendas")
def total_vendas(
    data_inicio: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    data_fim: date = Query(..., description="Data final (YYYY-MM-DD)"),
    empresa: int = Query(1),
    revenda: int = Query(1),
    conn: oracledb.Connection = Depends(get_db_connection)
):
    try:
        cursor = conn.cursor()
        
        # OTIMIZAÇÃO: Tudo resolvido em uma única ida ao banco!
        # Ajuste a coluna P.VAL_TOTAL_PROPOSTA para a coluna real de valor faturado no seu banco.
        # Ajuste o 'VENDA DIRETA' para a descrição exata que aparece na tabela FAT_SEGMENTO.
        query = """
            SELECT
                COUNT(CASE WHEN (PV.NOVO_USADO = 'N' OR V.NOVO_USADO = 'N') THEN 1 END) AS QTD_NOVOS,
                COUNT(CASE WHEN (PV.NOVO_USADO = 'U' OR V.NOVO_USADO = 'U') THEN 1 END) AS QTD_USADOS,
                COUNT(P.PROPOSTA) AS QTD_GERAL,
                
                -- SOMAS DE FATURAMENTO
                COALESCE(SUM(CASE WHEN (PV.NOVO_USADO = 'N' OR V.NOVO_USADO = 'N') THEN (SELECT SUM(VAL_PAGAMENTO) FROM VEI_PAGAMENTO WHERE EMPRESA = P.EMPRESA AND REVENDA = P.REVENDA AND PROPOSTA = P.PROPOSTA) ELSE 0 END), 0) AS VALOR_FATURADO_NOVOS,
                COALESCE(SUM(CASE WHEN (PV.NOVO_USADO = 'U' OR V.NOVO_USADO = 'U') THEN (SELECT SUM(VAL_PAGAMENTO) FROM VEI_PAGAMENTO WHERE EMPRESA = P.EMPRESA AND REVENDA = P.REVENDA AND PROPOSTA = P.PROPOSTA) ELSE 0 END), 0) AS VALOR_FATURADO_USADOS,
                COALESCE(SUM((SELECT SUM(VAL_PAGAMENTO) FROM VEI_PAGAMENTO WHERE EMPRESA = P.EMPRESA AND REVENDA = P.REVENDA AND PROPOSTA = P.PROPOSTA)), 0) AS VALOR_FATURADO_GERAL,
                
                -- VENDAS DIRETAS (Fábrica)
                SUM(CASE WHEN V.SITUACAO = 'VD' THEN 1 ELSE 0 END) AS QTD_VENDA_DIRETA
                
            FROM VEI_PROPOSTA P
            LEFT OUTER JOIN VEI_PROPOSTA_VEICULO PV ON (PV.EMPRESA = P.EMPRESA AND PV.REVENDA = P.REVENDA AND PV.PROPOSTA = P.PROPOSTA)
            LEFT OUTER JOIN VEI_VEICULO V ON (P.EMPRESA_VEICULO = V.EMPRESA AND P.VEICULO = V.VEICULO)
            LEFT OUTER JOIN FAT_SEGMENTO S ON (S.SEGMENTO = P.SEGMENTO_VD)
            WHERE P.EMPRESA = :emp
              AND P.REVENDA = :rev
              AND P.SITUACAO = '9' 
              AND P.DTA_EMISSAO >= TO_DATE(:dt_ini, 'YYYY-MM-DD')
              AND P.DTA_EMISSAO <= TO_DATE(:dt_fim, 'YYYY-MM-DD')
        """
        
        parametros = {
            "emp": empresa, "rev": revenda,
            "dt_ini": data_inicio.strftime('%Y-%m-%d'), "dt_fim": data_fim.strftime('%Y-%m-%d')
        }
        
        cursor.execute(query, parametros)
        colunas = [col[0].lower() for col in cursor.description]
        resultado = dict(zip(colunas, cursor.fetchone()))
        
        return {"status": "sucesso", "dados": resultado}

    except oracledb.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de banco: {str(e)}")
    finally:
        cursor.close()

@router.get("/vendas/ranking-modelos", summary="Ranking de Modelos Mais Vendidos")
def ranking_modelos(
    data_inicio: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    data_fim: date = Query(..., description="Data final (YYYY-MM-DD)"),
    tipo_veiculo: str = Query(None, description="'N' para Novos, 'U' para Usados"),
    empresa: int = Query(1),
    revenda: int = Query(1),
    limite: int = Query(10, description="Top N modelos a retornar"),
    conn: oracledb.Connection = Depends(get_db_connection)
):
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT
                M.DES_MODELO AS MODELO,
                COUNT(P.PROPOSTA) AS QTD_VENDIDA
            FROM VEI_PROPOSTA P
            LEFT OUTER JOIN VEI_PROPOSTA_VEICULO PV ON (PV.EMPRESA = P.EMPRESA AND PV.REVENDA = P.REVENDA AND PV.PROPOSTA = P.PROPOSTA)
            LEFT OUTER JOIN VEI_VEICULO V ON (P.EMPRESA_VEICULO = V.EMPRESA AND P.VEICULO = V.VEICULO)
            LEFT OUTER JOIN VEI_MODELO M ON (M.EMPRESA = V.EMPRESA AND M.MODELO = COALESCE(V.MODELO, PV.MODELO))
            WHERE P.EMPRESA = :emp
              AND P.REVENDA = :rev
              AND P.SITUACAO = '9'
              AND P.DTA_EMISSAO >= TO_DATE(:dt_ini, 'YYYY-MM-DD')
              AND P.DTA_EMISSAO <= TO_DATE(:dt_fim, 'YYYY-MM-DD')
        """
        
        parametros = {
            "emp": empresa, "rev": revenda,
            "dt_ini": data_inicio.strftime('%Y-%m-%d'), "dt_fim": data_fim.strftime('%Y-%m-%d')
        }
        
        if tipo_veiculo in ['N', 'U']:
            query += " AND (PV.NOVO_USADO = :tipo OR V.NOVO_USADO = :tipo)"
            parametros['tipo'] = tipo_veiculo
            
        # Oracle 12c+ suporta FETCH FIRST n ROWS ONLY. 
        # Agrupamos pelo nome do modelo e ordenamos pela quantidade
        query += """
            GROUP BY M.DES_MODELO 
            ORDER BY QTD_VENDIDA DESC 
            FETCH FIRST :limit_rows ROWS ONLY
        """
        parametros['limit_rows'] = limite
        
        cursor.execute(query, parametros)
        colunas = [col[0].lower() for col in cursor.description]
        resultados = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
        
        return {"status": "sucesso", "top_modelos": resultados}

    except oracledb.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de banco: {str(e)}")
    finally:
        cursor.close()

@router.get("/vendas/ranking-vendedores", summary="Ranking de Vendedores")
def ranking_vendedores(
    data_inicio: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    data_fim: date = Query(..., description="Data final (YYYY-MM-DD)"),
    tipo_veiculo: str = Query(None, description="Filtre por 'N' (Novos) ou 'U' (Usados). Deixe vazio para Geral."),
    empresa: int = Query(1),
    revenda: int = Query(1),
    conn: oracledb.Connection = Depends(get_db_connection)
):
    """
    Retorna a lista de vendedores ordenada do maior para o menor número de vendas no período.
    """
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT
                E.NOME AS VENDEDOR,
                COUNT(P.PROPOSTA) AS TOTAL_VENDAS
            FROM VEI_PROPOSTA P
            INNER JOIN FAT_VENDEDOR E ON (P.EMPRESA = E.EMPRESA AND P.REVENDA = E.REVENDA AND P.VENDEDOR = E.VENDEDOR)
            LEFT OUTER JOIN VEI_PROPOSTA_VEICULO PV ON (PV.EMPRESA = P.EMPRESA AND PV.REVENDA = P.REVENDA AND PV.PROPOSTA = P.PROPOSTA)
            LEFT OUTER JOIN VEI_VEICULO V ON (P.EMPRESA_VEICULO = V.EMPRESA AND P.VEICULO = V.VEICULO)
            WHERE P.EMPRESA = :emp
              AND P.REVENDA = :rev
              AND P.SITUACAO = '9'
              AND P.DTA_EMISSAO >= TO_DATE(:dt_ini, 'YYYY-MM-DD')
              AND P.DTA_EMISSAO <= TO_DATE(:dt_fim, 'YYYY-MM-DD')
        """
        
        parametros = {
            "emp": empresa,
            "rev": revenda,
            "dt_ini": data_inicio.strftime('%Y-%m-%d'),
            "dt_fim": data_fim.strftime('%Y-%m-%d')
        }
        
        # Aplica o filtro de Novo/Usado se o usuário solicitar na URL
        if tipo_veiculo in ['N', 'U']:
            query += " AND (PV.NOVO_USADO = :tipo OR V.NOVO_USADO = :tipo)"
            parametros['tipo'] = tipo_veiculo
            
        # Agrupa e ordena para formar o ranking
        query += " GROUP BY E.NOME ORDER BY TOTAL_VENDAS DESC"
        
        cursor.execute(query, parametros)
        colunas = [col[0] for col in cursor.description]
        resultados = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
        
        return {"status": "sucesso", "total_vendedores": len(resultados), "ranking": resultados}

    except oracledb.Error as e:
        raise HTTPException(status_code=500, detail=f"Erro de banco: {str(e)}")
    finally:
        cursor.close()