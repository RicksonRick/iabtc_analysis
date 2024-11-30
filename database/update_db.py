from psycopg2 import sql
from database.database_setting import connect_to_db
from typing import Union

def update_db():
    connection = connect_to_db()
    with connection.cursor() as cursor:
        # Lista de todas as colunas que devem estar na tabela
        expected_columns = [
            'id', 'datetime', 'prompt', 'response', 'Recommendation', 'Trust_rate',
            'Stop_loss', 'Take_profit', 'Risk_return', 'BTC_high', 'BTC_low',
            'BTC_close', 'BTC_open', 'prediction_date', 'actual_date'
        ]

        # Verifica quais colunas já existem na tabela
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'chatbot_data';
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]

        # Adiciona as colunas que estão faltando
        for column in expected_columns:
            if column.lower() not in [col.lower() for col in existing_columns]:
                # Determina o tipo de dados para a nova coluna
                if column in ['id']:
                    data_type = 'SERIAL PRIMARY KEY'
                elif column in ['datetime']:
                    data_type = 'TIMESTAMP'
                elif column in ['prompt', 'response', 'Recommendation']:
                    data_type = 'TEXT'
                elif column in ['Trust_rate', 'Stop_loss', 'Take_profit', 'Risk_return', 'BTC_high', 'BTC_low', 'BTC_close', 'BTC_open']:
                    data_type = 'NUMERIC'
                elif column in ['prediction_date', 'actual_date']:
                    data_type = 'DATE'
                else:
                    data_type = 'TEXT'  # Tipo padrão para colunas não especificadas

                # Adiciona a nova coluna
                cursor.execute(sql.SQL("ALTER TABLE chatbot_data ADD COLUMN {} {};").format(
                    sql.Identifier(column),
                    sql.SQL(data_type)
                ))
                print(f"Coluna '{column}' adicionada à tabela chatbot_data.")

        connection.commit()
    connection.close()
    print("Atualização do banco de dados concluída.")
    
from datetime import datetime
import json
from psycopg2.extras import Json
from typing import Dict, Any
from database.database_setting import connect_to_db

from datetime import datetime, timezone
import json
from typing import Dict, Any

def save_4h_analysis(analyzed_data: Union[str, dict]) -> bool:
    """
    Salva os resultados da análise do bot 4H no banco de dados.
    
    Args:
        analyzed_data: String JSON ou dicionário contendo os dados da análise
    
    Returns:
        bool: True se salvou com sucesso, False caso contrário
    """
    try:
        # Converte para dicionário se for string JSON
        data = json.loads(analyzed_data) if isinstance(analyzed_data, str) else analyzed_data
        
        connection = connect_to_db()
        with connection.cursor() as cursor:
            query = """
                INSERT INTO bot_4h_analysis (
                    analysis_datetime,
                    recommended_action,
                    justification,
                    stop_loss,
                    take_profit,
                    attention_points,
                    raw_response
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id;
            """
            
            cursor.execute(query, (
                datetime.now(timezone.utc),
                data['recommended_action'],
                data['justification'],
                data['stop_loss'],
                data['take_profit'],
                data['attention_points'],
                analyzed_data if isinstance(analyzed_data, str) else json.dumps(data)
            ))
            
            new_id = cursor.fetchone()[0]
            connection.commit()
            print(f"Análise 4H salva com sucesso. ID: {new_id}")
            return True
            
    except Exception as e:
        print(f"Erro ao salvar análise no banco de dados: {e}")
        if 'connection' in locals() and connection:
            connection.rollback()
        return False
        
    finally:
        if 'connection' in locals() and connection:
            connection.close()

def get_latest_analysis() -> Dict[str, Any]:
    """
    Recupera a análise mais recente do banco de dados.
    
    Returns:
        Dict contendo os dados da última análise ou None se houver erro
    """
    try:
        connection = connect_to_db()
        with connection.cursor() as cursor:
            query = """
                SELECT 
                    analysis_datetime,
                    recommended_action,
                    justification,
                    stop_loss,
                    take_profit,
                    attention_points,
                    raw_response
                FROM bot_4h_analysis
                ORDER BY analysis_datetime DESC
                LIMIT 1;
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                return {
                    'analysis_datetime': result[0],
                    'recommended_action': result[1],
                    'justification': result[2],
                    'stop_loss': float(result[3]),
                    'take_profit': float(result[4]),
                    'attention_points': result[5],
                    'raw_response': result[6]
                }
            return None
            
    except Exception as e:
        print(f"Erro ao recuperar última análise: {e}")
        return None
        
    finally:
        if connection:
            connection.close()

# Exemplo de uso
#if __name__ == "__main__":
 #   update_db()