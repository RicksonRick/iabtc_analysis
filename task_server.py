import schedule
import time
import pytz
import re
import json
import threading
from datetime import datetime, timedelta
from chatbot.chatbot_v3 import Conversation
from bot_4h.bot_4h_chatbot import Conversation4
from database.database_setting import insert_actual_bitcoin_data, connect_to_db
from analysis.exec_script import get_bitcoin_price_and_variation
import pandas as pd
import logging
from webhook import enviar_dados_para_urls, get_bitcoin_data


# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('task_server.log'),
        logging.StreamHandler()
    ]
)

brazil_tz = pytz.timezone('America/Sao_Paulo')

def update_operation_data():
    connection = connect_to_db()
    query = """
    SELECT 
        prediction_date,
        AVG("Risk_return") as avg_risk_return
    FROM 
        chatbot_data
    WHERE 
        actual_date IS NOT NULL
    GROUP BY 
        prediction_date
    ORDER BY 
        prediction_date
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    save_operation_data(df)
    print(f"Dados de operação atualizados em {datetime.now(brazil_tz)}")

def calculate_bitcoin_returns():
    connection = connect_to_db()
    query = """
    SELECT 
        DATE(datetime) as date,
        BTC_close
    FROM 
        chatbot_data
    ORDER BY 
        datetime
    """
    btc_df = pd.read_sql_query(query, connection)
    connection.close()
    
    btc_df['return'] = btc_df['BTC_close'].pct_change()
    btc_df = btc_df.groupby('date')['return'].mean().reset_index()
    btc_df['cumulative_return'] = (1 + btc_df['return']).cumprod() - 1
    
    save_bitcoin_returns(btc_df)
    print(f"Retornos do Bitcoin calculados em {datetime.now(brazil_tz)}")

def save_gpt_analysis(analysis):
    connection = connect_to_db()
    cursor = connection.cursor()
    cursor.execute("""
    INSERT INTO gpt_analysis (timestamp, analysis)
    VALUES (%s, %s)
    """, (datetime.now(brazil_tz), analysis))
    connection.commit()
    connection.close()

def save_bitcoin_data(data):
    connection = connect_to_db()
    cursor = connection.cursor()
    cursor.execute("""
    INSERT INTO bitcoin_data (timestamp, price, var_30d, var_14d, var_7d)
    VALUES (%s, %s, %s, %s, %s)
    """, (datetime.now(brazil_tz), data['price'], data['var_30d'], data['var_14d'], data['var_7d']))
    connection.commit()
    connection.close()

def save_operation_data(df):
    connection = connect_to_db()
    df.to_sql('operation_data', connection, if_exists='replace', index=False)
    connection.close()

def save_bitcoin_returns(df):
    connection = connect_to_db()
    df.to_sql('bitcoin_returns', connection, if_exists='replace', index=False)
    connection.close()

def schedule_next_run(task, scheduled_time):
    now = datetime.now(brazil_tz)
    next_run = now.replace(hour=scheduled_time.hour, minute=scheduled_time.minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()
    threading.Timer(delay, task).start()
    print(f"Próxima execução de {task.__name__} agendada para {next_run}")
    
def update_bitcoin_data():
    data = get_bitcoin_price_and_variation()

    if isinstance(data, str):
        price_match = re.search(r"Preço atual do Bitcoin: \$([0-9,.]+)", data)
        var_30d_match = re.search(r"Variação nos últimos 30 dias: ([0-9,.]+)%", data)
        var_14d_match = re.search(r"Variação nos últimos 14 dias: ([0-9,.]+)%", data)
        var_7d_match = re.search(r"Variação nos últimos 7 dias: ([0-9,.]+)%", data)
        
        if price_match and var_30d_match and var_14d_match and var_7d_match:
            data = {
                'price': float(price_match.group(1).replace(',', '')),
                'var_30d': float(var_30d_match.group(1).replace(',', '')),
                'var_14d': float(var_14d_match.group(1).replace(',', '')),
                'var_7d': float(var_7d_match.group(1).replace(',', ''))
            }
        else:
            print("Erro ao processar os dados da string.")
            return
    else:
        print("Erro: O objeto data não é uma string.")

    save_bitcoin_data(data)
    print(f"Dados do Bitcoin atualizados em {datetime.now(brazil_tz)}")
    
def run_conversation():
    print("Iniciando analise do GPT")
    ai_response = Conversation()
    response = ai_response.send()
    save_gpt_analysis(response)
    print(response)
    print(f"Análise GPT executada em {datetime.now(brazil_tz)}, {response}")
    
def run_4h_bot():
    print("Iniciando Bot 4h")
    bot_4h_response = Conversation4()
    response = bot_4h_response.analyze()
    print (response)

def job_wrapper(func):
    """Wrapper para garantir que as tarefas continuem executando mesmo com erros"""
    def wrapped():
        try:
            logging.info(f"Iniciando tarefa: {func.__name__}")
            func()
            logging.info(f"Tarefa concluída: {func.__name__}")
        except Exception as e:
            logging.error(f"Erro na execução de {func.__name__}: {str(e)}")
    return wrapped

def initialize_scheduler():
    """Inicializa todas as tarefas agendadas"""
    # Tarefas diárias existentes
    schedule.every().day.at("21:00").do(job_wrapper(run_conversation))
    schedule.every().day.at("21:05").do(job_wrapper(insert_actual_bitcoin_data))
    schedule.every().day.at("21:15").do(job_wrapper(enviar_dados_para_urls))
    
    # Bot 4h - executa 5 vezes ao dia
    schedule.every().day.at("04:00").do(job_wrapper(run_4h_bot))
    schedule.every().day.at("08:00").do(job_wrapper(run_4h_bot))
    schedule.every().day.at("12:00").do(job_wrapper(run_4h_bot))
    schedule.every().day.at("16:00").do(job_wrapper(run_4h_bot))
    schedule.every().day.at("20:00").do(job_wrapper(run_4h_bot))
    
    # Tarefas horárias existentes
    schedule.every().hour.do(job_wrapper(update_operation_data))
    schedule.every().hour.do(job_wrapper(calculate_bitcoin_returns))
    schedule.every().hour.do(job_wrapper(update_bitcoin_data))
    
    logging.info("Todas as tarefas foram agendadas com sucesso")

if __name__ == "__main__":
    logging.info("Iniciando servidor de tarefas")
    
    # Inicializa o scheduler
    initialize_scheduler()
    
    # Execução inicial dos bots
    logging.info("Executando análises iniciais")
    
    logging.info(f"Servidor de tarefas iniciado. (Horário de Brasília: {datetime.now(brazil_tz)})")
    
    # Loop principal com tratamento de erros
    while True:
        try:
            schedule.run_pending()
            
            # Log das próximas tarefas (a cada hora)
            if datetime.now().minute == 0:
                next_task = schedule.next_run()
                if next_task:
                    logging.info(f"Próxima tarefa agendada para: {next_task.astimezone(brazil_tz)}")
            
            time.sleep(1)
            
        except Exception as e:
            logging.error(f"Erro no loop principal: {str(e)}")
            time.sleep(5)
            
            
