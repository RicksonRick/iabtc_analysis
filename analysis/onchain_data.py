import os
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import streamlit as st

load_dotenv()  

class OnChain:
    def __init__(self):
        self.on_chain_volume = self.on_chain_volume()
        self.blockchain_data = self.blockchain_data()
        self.exchange_analysis=self.exchange_analysis()
        
    class on_chain_volume:
        def get_onchain_data(self):
            url = 'https://api.santiment.net/graphql'

            to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            from_date = "2023-09-14T00:00:00Z"

            query = f"""
            {{
            getMetric(metric: "transaction_volume") {{
                timeseriesData(
                slug: "bitcoin"
                from: "{from_date}"
                to: "{to_date}"
                interval: "30m"
                ) {{
                datetime
                value
                }}
            }}
            }}
            """

            headers = {'Authorization': f"Apikey {os.getenv('santiment_KEY')}"}

            response = requests.post(url, json={'query': query}, headers=headers)

            if response.status_code == 200:
                data = response.json()

                if 'data' in data and 'getMetric' in data['data'] and 'timeseriesData' in data['data']['getMetric']:
                    data = data['data']['getMetric']['timeseriesData']

                    if data:
                        df = pd.DataFrame(data)
                        if 'datetime' in df.columns:
                            df['datetime'] = pd.to_datetime(df['datetime'])
                        else:
                            return "A chave 'datetime' não foi encontrada. Verifique o JSON retornado."

                        df['datetime'] = df['datetime'].dt.tz_convert('America/Sao_Paulo')
                        return df
                    else:
                        return "Nenhum dado foi retornado para o período solicitado."
                else:
                    return "A estrutura de dados retornada pela API não está correta. Verifique a resposta JSON."
            else:
                return f'Erro na requisição: {response.status_code}, {response.text}'

        def analysis(self):
            on_chain = self.get_onchain_data()

            if isinstance(on_chain, pd.DataFrame):
                avg_volume = on_chain['value'].mean()
                max_volume = on_chain['value'].max()
                last_volume = on_chain['value'].iloc[-1]

                if last_volume > avg_volume:
                    trend = "acima da média"
                else:
                    trend = "abaixo da média"

                analise_onchain = (f"O volume médio de transações on-chain para o Bitcoin no período analisado é de {avg_volume:.2f}. "
                                   f"O volume máximo registrado foi de {max_volume:.2f}. "
                                   f"O volume mais recente está {trend}, indicando uma possível {('alta' if trend == 'acima da média' else 'queda')} "
                                   f"no número de transações em comparação com a média do período.")
                return analise_onchain
            else:
                return f"Erro ao analisar os dados: {on_chain}"

    class blockchain_data:
        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = ZoneInfo("America/Sao_Paulo")
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def get_blockchain_data(self):
            url = "https://min-api.cryptocompare.com/data/blockchain/histo/day"
            params = {
                'fsym': 'BTC',
                'limit': '30',
                'api_key': os.getenv('CRYPTOCOMPARE_API_KEY')
            }
            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()

                if 'Data' in data and 'Data' in data['Data']:
                    return data['Data']['Data']
                else:
                    return "Estrutura de dados inesperada"
            else:
                return f"Failed to retrieve data. Status code: {response.status_code}, Response: {response.text}"

        def parse_blockchain_data(self, data):
            parsed_data = []
            for day_data in data:
                parsed_data.append({
                    'data': self.convert_to_brt(day_data['time']),
                    'enderecos_ativos': day_data['active_addresses'],
                    'volume_transacoes': day_data['transaction_count'],
                    'hash_rate': day_data['hashrate'],
                    'dificuldade': day_data['difficulty'],
                    'movimentacao_whales': day_data['large_transaction_count'],
                    'valor_transferido': day_data['average_transaction_value']
                })
            return parsed_data

        def analysis(self):
            blockchain_data = self.get_blockchain_data()
            if blockchain_data == "Failed to retrieve data":
                return "Falha ao recuperar os dados da blockchain"

            parsed_blockchain_data = self.parse_blockchain_data(blockchain_data)

            total_enderecos_ativos = sum(d['enderecos_ativos'] for d in parsed_blockchain_data)
            media_enderecos_ativos = total_enderecos_ativos / len(parsed_blockchain_data)

            total_volume_transacoes = sum(d['volume_transacoes'] for d in parsed_blockchain_data)
            media_volume_transacoes = total_volume_transacoes / len(parsed_blockchain_data)

            total_hash_rate = sum(d['hash_rate'] for d in parsed_blockchain_data)
            media_hash_rate = total_hash_rate / len(parsed_blockchain_data)

            total_movimentacao_whales = sum(d['movimentacao_whales'] for d in parsed_blockchain_data)
            media_movimentacao_whales = total_movimentacao_whales / len(parsed_blockchain_data)

            blockchain_analysis = (f"Média de Endereços Ativos: {media_enderecos_ativos:.2f}\n"
                                   f"Média de Volume de Transações: {media_volume_transacoes:.2f}\n"
                                   f"Média de Hash Rate: {media_hash_rate:.2f}\n"
                                   f"Média de Movimentação de Whales: {media_movimentacao_whales:.2f}")

            return blockchain_analysis

    class exchange_analysis:
    
        def get_exchange_balance(self, symbol="BTC"):
            url = f"https://open-api-v3.coinglass.com/api/exchange/balance/v2/list?symbol={symbol}"
            headers = {
                "accept": "application/json",
                "CG-API-KEY": '936395e1aa6943659c5ff7b729981532'
            }

            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                print(f"Erro na requisição: {response.text}")
                return None

            data = response.json()
            if data.get("code") != "0":
                print(f"Erro na resposta da API: {data.get('msg')}")
                return None

            if not data.get("data"):
                print("Nenhum dado retornado pela API.")
                return None

            return data["data"]

        def process_data_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for exchange in data:
                exchange_name = exchange.get("exchangeName", "N/A")
                balance = exchange.get("balance", "N/A")
                change1d = exchange.get("change1d", "N/A")
                change_percent1d = exchange.get("changePercent1d", "N/A")
                change7d = exchange.get("change7d", "N/A")
                change_percent7d = exchange.get("changePercent7d", "N/A")
                change30d = exchange.get("change30d", "N/A")
                change_percent30d = exchange.get("changePercent30d", "N/A")

                records.append({
                    "Exchange": exchange_name,
                    "Saldo": balance,
                    "Variação 1D": change1d,
                    "Variação % 1D": change_percent1d,
                    "Variação 7D": change7d,
                    "Variação % 7D": change_percent7d,
                    "Variação 30D": change30d,
                    "Variação % 30D": change_percent30d
                })

            df = pd.DataFrame(records)
            return df

        def fetch_exchange_balance(self, symbol="BTC"):
            data = self.get_exchange_balance(symbol=symbol)
            df = self.process_data_to_df(data)
            return df

        def analysis(self):
            exchange_balance_data = self.fetch_exchange_balance()

            if not exchange_balance_data.empty:
                total_balance = exchange_balance_data["Saldo"].sum()
                max_balance = exchange_balance_data["Saldo"].max()
                max_balance_exchange = exchange_balance_data.loc[exchange_balance_data["Saldo"].idxmax()]["Exchange"]
                avg_change_1d = exchange_balance_data["Variação % 1D"].mean()

                analysis = (
                    f"O saldo total de Bitcoin nas exchanges é de {total_balance:.2f} BTC. "
                    f"A exchange com o maior saldo é {max_balance_exchange} com {max_balance:.2f} BTC. "
                    f"A variação média de saldo nas últimas 24 horas foi de {avg_change_1d:.2f}%. "
                )

                return analysis
            else:
                return "Nenhum dado foi retornado para análise."
        