from openai import OpenAI
import pandas as pd
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import sys

# Adicionar o diretório raiz ao PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database_setting import connect_to_db
from chatbot.prompts import get_current_date_time_utc
from database.update_db import save_4h_analysis
import re

load_dotenv()
    
class InvestmentAnalysisResponse(BaseModel):
    recommended_action: str
    justification: str
    stop_loss: float 
    take_profit: float 
    attention_points: List[str]
    
class Conversation4:
    def __init__(self):
        openai_api_key = os.getenv('OPENAI_KEY')
        if not openai_api_key:
            raise ValueError("A chave da API OpenAI não foi encontrada nas variáveis de ambiente.")
        self.client = OpenAI(api_key=openai_api_key)
        print("Cliente OpenAI inicializado.")  

    def get_bitcoin_movement_since_midnight(self):
        print("Iniciando análise de movimentação desde 00:00 UTC")

        base_url = "https://api.coingecko.com/api/v3"
        api_key = os.getenv('COINGEKO_KEY')
        headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": api_key
        }

        def get_current_price():
            price_url = f"{base_url}/simple/price?ids=bitcoin&vs_currencies=usd"
            try:
                response = requests.get(price_url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                price = Decimal(data['bitcoin']['usd'])
                print(f"Preço atual: ${price}")
                return price
            except requests.RequestException as e:
                print(f"Erro ao obter preço atual:", e)
                return None

        def get_midnight_price():
            now = datetime.utcnow()
            midnight = datetime(now.year, now.month, now.day)
        
            # Calcula o timestamp em segundos
            from_timestamp = int(midnight.timestamp())
            to_timestamp = from_timestamp + 300  # Adiciona 5 minutos para garantir alguns dados
        
            market_data_url = f"{base_url}/coins/bitcoin/market_chart/range?vs_currency=usd&from={from_timestamp}&to={to_timestamp}"
        
            try:
                response = requests.get(market_data_url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
            
                if data['prices'] and len(data['prices']) > 0:
                    # Pega o primeiro preço disponível após a meia-noite
                    price = Decimal(data['prices'][0][1])
                    print(f"Preço à meia-noite: ${price}")
                    return price
                else:
                    print("Dados de preço não disponíveis para meia-noite")
                    return None
            except requests.RequestException as e:
                print(f"Erro ao obter preço da meia-noite:", e)
                return None

        price_midnight = get_midnight_price()
        if price_midnight is None:
            return "Erro ao obter preço às 00:00 UTC."

        price_now = get_current_price()
        if price_now is None:
            return "Erro ao obter preço atual."

        price_change = price_now - price_midnight
        percentage_change = (price_change / price_midnight) * 100

        print("Análise concluída")
        return {
            "price_midnight": float(price_midnight),
            "price_now": float(price_now),
            "price_change": float(price_change),
            "percentage_change": float(percentage_change)
        }

    
    def get_last_prediction(self):
        
        try:
            connection = connect_to_db()
        
            with connection.cursor() as cursor:
                cursor.execute("""
                SELECT "id", "response", "recommendation", "stop_loss", "take_profit" FROM
                "public"."chatbot_data" 
                ORDER BY "id" DESC
                LIMIT 1;
                """
                )
            
                data = cursor.fetchone()
            
                if data: 
                    return {
                        "id": data[0],
                        "response": data[1],
                        "recommendation": data[2],
                        "stop_loss": data[3],
                        "take_profit": data[4],
                    }
                else:
                    return None
            
        except Exception as e:
            print(f"Error fetching last prediction: {e}")
            return None
        finally:
            if connection:
                connection.close() 
                
    def analyze(self):
        dados = self.get_last_prediction
        data = get_current_date_time_utc()
        dados_movimentacao_btc = self.get_bitcoin_movement_since_midnight()
        prompt = f"""
        Data e Hora Atual: {data}

        ---

        ### Contexto:

        Você é um analista de investimentos especializado em Bitcoin, focado em operações intradiárias. Sua tarefa é reavaliar a posição atual a cada 4 horas, com base na análise anterior e nos dados de mercado mais recentes.

        ### Entrada:

        - **Movimentação do BTC desde a Análise Anterior**:  
        {dados_movimentacao_btc}

        ---

        ### Objetivo:

        Com base nas informações fornecidas, determine se é necessário realizar alguma ação entre as seguintes opções:

        - **Manter** a posição atual.
        - **Ajustar Stop Loss (SL) e/ou Take Profit (TP)**.
        - **Reverter Posição (Vender/Comprar)**.

        ---

        ### Processo de Análise:

        1. **Revisão da Análise Anterior**:  
        Releia a análise anterior para compreender as premissas e recomendações feitas.

        2. **Análise da Movimentação Recente**:  
        - Avalie os dados de preço, volume e volatilidade do BTC desde a última análise.
        - Identifique padrões técnicos ou eventos significativos ocorridos nas últimas 4 horas.

        3. **Validação das Premissas**:  
        Verifique se as premissas da análise anterior continuam válidas à luz dos novos dados.

        4. **Análise Técnica Atual**:  
        - Utilize indicadores como RSI, MACD, médias móveis e padrões de velas para avaliar a tendência atual.
        - Considere níveis de suporte e resistência relevantes.

        5. **Tomada de Decisão**:  
        - **Manter**: Se a posição atual ainda é suportada pelos dados técnicos.
        - **Ajustar SL/TP**: Se for necessário otimizar os níveis de saída para melhor gestão de risco.
        - **Reverter Posição**: Se os indicadores técnicos apontarem para uma mudança na tendência que invalida a posição atual.

        6. **Justificativa**:  
        Forneça uma justificativa clara e objetiva para a ação recomendada, baseada exclusivamente em análise técnica.

        ---

        ### Output Esperado:

        Forneça as seguintes informações, mantendo os títulos exatos para facilitar a extração de dados:

        1. **Ação Recomendada**:  
        Especifique uma das opções: "Manter", "Ajustar SL/TP" ou "Reverter Posição (Vender/Comprar)".

        2. **Justificativa Técnica**:  
        Detalhe os motivos técnicos que levaram à recomendação, citando indicadores e padrões observados.

        3. **Níveis de SL/TP**:  
        - **Stop Loss (SL)**: Valor atualizado do SL, se não houver ajuste, coloque o mesmo que estava anteriormente.
        - **Take Profit (TP)**: Valor atualizado do TP, se não houver ajuste, coloque o mesmo que estava anteriormente.

        4. **Pontos de Atenção**:  
        Liste eventos ou níveis de preço críticos a serem monitorados nas próximas 4 horas.

        ---

        ### Observações:

        - Baseie sua análise exclusivamente em dados técnicos e objetivos.
        - Evite qualquer viés ou predisposição para ajustar a posição sem justificativa sólida.
        - Seja claro e conciso em suas recomendações, focando na qualidade da análise.
        
        *** Responda em Português ***
        
        - **Análise Anterior**:  
        """
        
        messages = [{"role": "system", "content": prompt}]

        dados_str = str(dados)
        print(dados_str)
        messages.append({"role": "user", "content": dados_str})

        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-11-20",
                messages=messages,
                response_format=InvestmentAnalysisResponse
            )
            analyzed_data = response.choices[0].message.content
            
            save_success = save_4h_analysis(analyzed_data)
            if not save_success:
                print("Aviso: Não foi possível salvar a análise no banco de dados")
                
            print(analyzed_data)
            return analyzed_data
        
        except Exception as e:
            print(f"Erro ao conectar à API da OpenAI: {e}")
            return
        
if __name__ == '__main__':
    # Inicializa a classe Conversation4
    conversation = Conversation4()
    
    # Testa o método de análise de movimentação de Bitcoin
    print("Teste: Movimentação de Bitcoin desde 00:00 UTC")
    btc_movement = conversation.get_bitcoin_movement_since_midnight()
    print(btc_movement)
    
    # Testa o método que obtém a última previsão
    print("\nTeste: Última Previsão")
    last_prediction = conversation.get_last_prediction()
    print(last_prediction)
    
    # Testa o método de análise (com as dependências necessárias)
    print("\nTeste: Análise de Dados")
    try:
        conversation.analyze()
    except Exception as e:
        print(f"Erro durante a análise: {e}")