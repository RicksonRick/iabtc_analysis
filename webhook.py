import json
import os
import requests
import pandas as pd
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Header, APIRouter
from database.database_setting import connect_to_db

router = APIRouter()

URLS_FILE = "urls.json"

class URLRequest(BaseModel):
    url: str

def load_data():
    if not os.path.exists(URLS_FILE):
        return {"API_KEYS": {}}
    
    with open(URLS_FILE, 'r') as file:
        return json.load(file)

def save_data(data):
    with open(URLS_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def add_url(api_key, new_url):
    data = load_data()
    api_data = data["API_KEYS"].get(api_key, {"urls": []})
    
    if new_url not in api_data["urls"]:
        api_data["urls"].append(new_url)
        data["API_KEYS"][api_key] = api_data
        save_data(data)
        return True
    return False

def get_bitcoin_data():
    connection = connect_to_db()
    query = """
    SELECT "recommendation", "stop_loss", "take_profit", "risk_return", "value_btc", "datetime" 
    FROM "public"."chatbot_data" 
    ORDER BY "datetime" DESC
    LIMIT 1;
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    
    if not df.empty:
        data = df.to_dict(orient='records')[0]
        data['recommendation'] = data['recommendation'].strip()
        data['risk_return'] = data['risk_return'].strip()
        data['datetime'] = data['datetime'].isoformat()
        return 200, data
    
    return 400, "Erro ao recuperar os dados da IA"

def enviar_dados_para_urls():
    status, analysis_data = get_bitcoin_data()
    
    if status != 200:
        print("Erro ao recuperar os dados da IA. Nenhum dado enviado.")
        return
    
    data = load_data() 
    all_urls = []

    for api_key, api_data in data.get("API_KEYS", {}).items():
        urls = api_data.get("urls", [])
        all_urls.extend(urls) 
    
    if not all_urls:
        print("Nenhuma URL cadastrada.")
        return
    
    for url in all_urls:
        try:
            response = requests.post(url, json=analysis_data, headers={'Content-Type': 'application/json'})
            if response.status_code == 200:
                print(f"Dados enviados com sucesso para {url}")
            else:
                print(f"Erro ao enviar para {url}: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Erro ao tentar enviar para {url}: {e}")

@router.post("/cadastrar-url",
    summary="Cadastrar URL para Webhook",
    description="""
    Este endpoint permite cadastrar uma URL para receber automaticamente os dados da análise do GPT.

    **Funcionamento:**
    - As análises são enviadas diariamente às 21:15 (horário local), 15 minutos após o fechamento do mercado às 00:00 UTC.
    - A URL cadastrada será acionada via webhook com os dados gerados pela IA.

    **Campos obrigatórios no cabeçalho:**
    - `api-key`: Chave da API (fornecida pelo sistema).

    **Exemplo de corpo da requisição:**
    ```json
    {
        "url": "https://meuservico.com/webhook"
    }
    ```

    **Resposta de sucesso:**
    - Em caso de sucesso, o sistema retornará uma mensagem confirmando o cadastro da URL.
    
    ***Exemplo de resposta da análise do GPT:***
    (200, {'recommendation': 'Compra', 'stop_loss': 66200.0, 'take_profit': 68500.0, 'risk_return': '1:2', 'value_btc': 67187.0, 'datetime': '2024-10-23T00:30:03.324596'})
    """)
async def cadastrar_url(request: URLRequest, api_key: str = Header(...)):
    data = load_data()
    
    if api_key not in data["API_KEYS"]:
        data["API_KEYS"][api_key] = {"urls": []} 
    
    if add_url(api_key, request.url):
        return {"message": "URL cadastrada com sucesso."}
    else:
        return {"message": "A URL já está cadastrada."}

@router.post("/DadosGPT",
    summary="Receber dados do GPT",
    description="""
    Este endpoint receber automaticamente os dados da última análise do GPT.

    **Funcionamento:**
    - As análises são feitas diariamente às 21:05 (horário local), 5 minutos após o fechamento do mercado às 00:00 UTC.

    **Campos obrigatórios no cabeçalho:**
    - `api-key`: Chave da API (fornecida pelo sistema).

    **Resposta de sucesso:**
    - Em caso de sucesso, o sistema retornará 200.
    
    ***Exemplo de resposta da análise do GPT:***
    (200, {'recommendation': 'Compra', 'stop_loss': 66200.0, 'take_profit': 68500.0, 'risk_return': '1:2', 'value_btc': 67187.0, 'datetime': '2024-10-23T00:30:03.324596'})
    """)
def receber_previsões(api_key: str = Header(...)):
    data = load_data()
    if api_key not in data["API_KEYS"]:
        return "API não cadastrada"
    
    status, dados = get_bitcoin_data()
    if status == 200:
        return {"status": status, "dados": dados}
    
    else:
        {"status": 400, "resposta": "Erro na requisição"}
