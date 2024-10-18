import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import numpy as np
import ta
import pytz
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import streamlit as st


load_dotenv()

class derivatives_data:
    
    def __init__(self):
        # Instancia a classe options_volume em vez de chamar diretamente a análise
        self.options_volume = self.options_volume()
        self.coinglass_key = "936395e1aa6943659c5ff7b729981532"

    def convert_to_brt(self, timestamp):
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        brt_tz = ZoneInfo("America/Sao_Paulo")
        dt_brt = dt.astimezone(brt_tz)
        return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

    def get_unix_timestamp(self, days_ago=0):
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return int(dt.timestamp())

    class options_volume:
        def get_options_volume(self):
            url = 'https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option'
            response = requests.get(url)

            if response.status_code == 200:
                options_data = response.json().get('result', [])
                if not options_data:
                    print("Nenhum dado de opções foi retornado.")
                    return None

                df = pd.DataFrame(options_data)

                if 'volume' in df.columns:
                    df_volume = df[['instrument_name', 'volume']]
                    return df_volume
                else:
                    return "O campo de volume de negociação (volume) não está disponível nos dados."
            else:
                return "Erro ao obter dados de opções:", response.status_code, response.text
            
        def analysis(self):
            vol_negociacao = self.get_options_volume()

            if vol_negociacao is not None and not vol_negociacao.empty:
                vol_negociacao['volume'] = vol_negociacao['volume'].astype(float)

                total_volume = vol_negociacao['volume'].sum()
                avg_volume = vol_negociacao['volume'].mean()
                max_volume = vol_negociacao['volume'].max()

                top_instrument = vol_negociacao.loc[vol_negociacao['volume'].idxmax()]

                analysis = (f"O volume total de negociação de opções de Bitcoin foi de {total_volume:.2f}. "
                            f"O volume médio por instrumento foi de {avg_volume:.2f}. "
                            f"O maior volume registrado foi de {max_volume:.2f} para o instrumento {top_instrument['instrument_name']}.")
                return analysis
            else:
                return "Nenhum dado de volume de negociação foi retornado para análise."
            
    class cvd_data:
        def fetch_trades(self, pair='XXBTZUSD', interval=30, lookback_days=14):
            endpoint = 'https://api.kraken.com/0/public/OHLC'
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=lookback_days)
            start_time_ts = int(start_time.timestamp())

            params = {
                'pair': pair,
                'interval': interval,
                'since': start_time_ts
            }

            response = requests.get(endpoint, params=params)
            data = response.json()

            if 'result' not in data:
                raise ValueError("Não foi possível obter os dados da API.")

            ohlc_data = data['result'].get(pair, [])
            columns = ['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count']
            df = pd.DataFrame(ohlc_data, columns=columns)

            df['time'] = pd.to_datetime(df['time'], unit='s')
            df['time'] = df['time'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')
            df['time'] = df['time'].dt.tz_localize(None)

            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

            return df

        def calculate_cvd_30min(self, df):
            df.set_index('time', inplace=True)
            df = df.resample('30min').agg({'volume': 'sum'})

            df['cvd'] = df['volume']
            df.reset_index(inplace=True)

            return df[['time', 'cvd']]

        def analysis(self):
            df = self.fetch_trades()

            cvd_30min = self.calculate_cvd_30min(df)

            if not cvd_30min.empty:
                avg_cvd = cvd_30min['cvd'].mean()
                max_cvd = cvd_30min['cvd'].max()
                min_cvd = cvd_30min['cvd'].min()

                last_cvd = cvd_30min['cvd'].iloc[-1]

                analysis = (f"A média do CVD nos últimos 14 dias foi de {avg_cvd:.2f}. "
                            f"O maior CVD registrado foi de {max_cvd:.2f}, enquanto o menor CVD foi de {min_cvd:.2f}. "
                            f"O CVD mais recente é de {last_cvd:.2f}.")

                return analysis

            else:
                return "Nenhum dado de CVD encontrado para análise."

    class volume_change:   
        def puxar_dados(self):
            url = 'https://api.coingecko.com/api/v3/coins/bitcoin/market_chart'
            params = {
                'vs_currency': 'usd',
                'days': '14',
                'interval': 'daily'
            }
            response = requests.get(url, params=params)
            data = response.json()

            prices = data['prices']
            volumes = data['total_volumes']

            df_prices = pd.DataFrame(prices, columns=['timestamp', 'price'])
            df_prices['timestamp'] = pd.to_datetime(df_prices['timestamp'], unit='ms')

            df_volumes = pd.DataFrame(volumes, columns=['timestamp', 'volume'])
            df_volumes['timestamp'] = pd.to_datetime(df_volumes['timestamp'], unit='ms')

            df = pd.merge(df_prices, df_volumes, on='timestamp')

            return df
        
        def analysis(self):
            df = self.puxar_dados()

            df['change_in_volume'] = df['volume'].diff()

            mudanca_volume = df[['timestamp', 'change_in_volume']]

            if not mudanca_volume.empty:
                avg_change_volume = mudanca_volume['change_in_volume'].mean()
                max_change_volume = mudanca_volume['change_in_volume'].max()
                min_change_volume = mudanca_volume['change_in_volume'].min()

                last_change_volume = mudanca_volume['change_in_volume'].iloc[-1]

                analysis = (f"A média da mudança no volume nos últimos 14 dias foi de {avg_change_volume:.2e}. "
                            f"A maior mudança no volume foi de {max_change_volume:.2e}, enquanto a menor mudança foi de {min_change_volume:.2e}. "
                            f"A mudança de volume mais recente é de {last_change_volume:.2e}.")

                return analysis

            else:
                return "Nenhuma mudança de volume encontrada para análise."

    class skew:
        def calculate(self):
            url = 'https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option'
            response = requests.get(url)

            if response.status_code == 200:
                options_data = response.json().get('result', [])
                if not options_data:
                    print("Nenhum dado de opções foi retornado.")
                    return None

                df = pd.DataFrame(options_data)

                if 'ask_price' in df.columns and 'bid_price' in df.columns:
                    df['skew'] = (df['ask_price'] - df['bid_price']) / df['mid_price'] * 100
                    return df[['instrument_name', 'ask_price', 'bid_price', 'mid_price', 'skew']]
                else:
                    return "As colunas de preço (ask_price e bid_price) não estão disponíveis nos dados."

            else:
                return f"Erro ao obter dados de opções: {response.status_code} - {response.text}"

        def analysis(self):
            # Calcular o Skew
            skew_data = self.calculate()

            if skew_data is not None and not isinstance(skew_data, str) and not skew_data.empty:
                # Cálculo das estatísticas básicas
                avg_skew = skew_data['skew'].mean()
                max_skew = skew_data['skew'].max()
                min_skew = skew_data['skew'].min()

                # Último Skew registrado
                last_skew = skew_data['skew'].iloc[-1]

                # Gerando a análise sobre o Skew
                skew_anl = (f"A média do Skew das opções de Bitcoin foi de {avg_skew:.2f}%. "
                            f"O maior Skew registrado foi de {max_skew:.2f}%, enquanto o menor Skew foi de {min_skew:.2f}%. "
                            f"O Skew mais recente é de {last_skew:.2f}%.")

                return skew_anl

            elif isinstance(skew_data, str):
                return skew_data
            else:
                return "Nenhum dado de Skew foi retornado para análise."


    class iv:
        def get_options_iv(self):
            url = 'https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option'
            response = requests.get(url)

            if response.status_code == 200:
                options_data = response.json().get('result', [])
                if not options_data:
                    return "Nenhum dado de opções foi retornado."

                df = pd.DataFrame(options_data)

                if 'mark_iv' in df.columns:
                    df_iv = df[['instrument_name', 'mark_iv']]
                    return df_iv
                else:
                    print("O campo de volatilidade implícita (mark_iv) não está disponível nos dados.")
                    return None

            else:
                print("Erro ao obter dados de opções:", response.status_code, response.text)
                return None

        def analysis(self):
            iv = self.get_options_iv()

            if iv is not None and not iv.empty:
                iv['mark_iv'] = iv['mark_iv'].astype(float)

                avg_iv = iv['mark_iv'].mean()
                max_iv = iv['mark_iv'].max()
                min_iv = iv['mark_iv'].min()

                top_iv_instrument = iv.loc[iv['mark_iv'].idxmax()]
                low_iv_instrument = iv.loc[iv['mark_iv'].idxmin()]

                analysis = (f"A volatilidade implícita média para as opções de Bitcoin é de {avg_iv:.2f}%. "
                            f"A maior volatilidade implícita registrada foi de {max_iv:.2f}% para o instrumento {top_iv_instrument['instrument_name']}. "
                            f"A menor volatilidade implícita registrada foi de {min_iv:.2f}% para o instrumento {low_iv_instrument['instrument_name']}.")

                return analysis

            else:
                return "Nenhum dado de volatilidade implícita foi retornado para análise."


    class market_depth:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/orderbook/history"

        def get_order_book_depth(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": os.getenv('COINGLASS_KEY')  
            }

            params = {
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Erro na requisição, market_depth: {response.text}")
                return None

            data = response.json()
            if data.get("code") != "0":
                print(f"Erro na resposta da API, market_depth: {data.get('msg')}")
                return None

            return data

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_order_book_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data.get("data", []):
                bids_usd = item.get("bidsUsd", "N/A")
                bids_amount = item.get("bidsAmount", "N/A")
                asks_usd = item.get("asksUsd", "N/A")
                asks_amount = item.get("asksAmount", "N/A")
                timestamp = item.get("time", 0)
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Bids (USD)": bids_usd,
                    "Bids Amount": bids_amount,
                    "Asks (USD)": asks_usd,
                    "Asks Amount": asks_amount
                })
            df = pd.DataFrame(records)
            return df

        def fetch_order_book(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            data = self.get_order_book_depth(symbol=symbol, exchange=exchange, interval=interval)
            df = self.process_order_book_to_df(data)
            return df

        def analysis(self):
            profundidade = self.fetch_order_book()

            if not profundidade.empty:
                # Converter as colunas para float
                profundidade["Bids (USD)"] = profundidade["Bids (USD)"].astype(float)
                profundidade["Bids Amount"] = profundidade["Bids Amount"].astype(float)
                profundidade["Asks (USD)"] = profundidade["Asks (USD)"].astype(float)
                profundidade["Asks Amount"] = profundidade["Asks Amount"].astype(float)

                # Cálculo das estatísticas básicas para bids e asks
                avg_bids_usd = profundidade["Bids (USD)"].mean()
                max_bids_usd = profundidade["Bids (USD)"].max()
                avg_asks_usd = profundidade["Asks (USD)"].mean()
                max_asks_usd = profundidade["Asks (USD)"].max()

                # Cálculo das quantidades (amount) de bids e asks
                avg_bids_amount = profundidade["Bids Amount"].mean()
                avg_asks_amount = profundidade["Asks Amount"].mean()

                # Gerando a análise para a profundidade do mercado
                profundidade_anl = (
                    f"Durante o período analisado, o valor médio de Bids foi de {avg_bids_usd:.2f} USD, com um pico máximo de {max_bids_usd:.2f} USD. "
                    f"O valor médio de Asks foi de {avg_asks_usd:.2f} USD, com um pico máximo de {max_asks_usd:.2f} USD.\n"
                    f"A quantidade média de Bids foi de {avg_bids_amount:.2f}, enquanto a quantidade média de Asks foi de {avg_asks_amount:.2f}."
                )

                return profundidade_anl
            else:
                return "Nenhum dado foi retornado para análise."

    
    class Liquidations:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/liquidation/v2/history"

        def get_liquidation_history(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": '936395e1aa6943659c5ff7b729981532'
            }
            params = {
                "exchange": exchange,
                "symbol": symbol.upper(),
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Erro na requisição: {response.text}")
                return None

            data = response.json()

            # Verifique se o campo 'success' está presente e é verdadeiro
            if not data.get("success"):
                print(f"Erro na resposta da API: {data.get('msg', 'Unknown error')}")
                return None

            if not data.get("data"):
                print("Nenhum dado retornado pela API de liquidações.")
                return None

            return data["data"]

        def convert_to_brt(self, timestamp):
            if timestamp is None:
                return "N/A"  # Retorna "N/A" se o timestamp estiver ausente
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)  # Timestamps em milissegundos
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_liquidations_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data:
                long_liq = item.get("longLiquidationUsd", 0) or 0
                short_liq = item.get("shortLiquidationUsd", 0) or 0
                timestamp = item.get("t")  # Obtém o valor do timestamp
                brt_time = self.convert_to_brt(timestamp)  # Converte para o horário de Brasília
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Long Liquidation (USD)": long_liq,
                    "Short Liquidation (USD)": short_liq
                })
            df = pd.DataFrame(records)
            return df

        def fetch_liquidations(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            data = self.get_liquidation_history(symbol=symbol, exchange=exchange, interval=interval)
            if data:
                df = self.process_liquidations_to_df(data)
                return df
            else:
                return pd.DataFrame()

        def analysis(self):
            liquidacoes = self.fetch_liquidations()

            if not liquidacoes.empty:
                # Converter as colunas para float
                liquidacoes["Long Liquidation (USD)"] = pd.to_numeric(liquidacoes["Long Liquidation (USD)"], errors='coerce')
                liquidacoes["Short Liquidation (USD)"] = pd.to_numeric(liquidacoes["Short Liquidation (USD)"], errors='coerce')

                # Cálculo das estatísticas básicas
                avg_long_liq = liquidacoes["Long Liquidation (USD)"].mean() or 0.0
                max_long_liq = liquidacoes["Long Liquidation (USD)"].max() or 0.0
                last_long_liq = liquidacoes["Long Liquidation (USD)"].iloc[-1] or 0.0

                avg_short_liq = liquidacoes["Short Liquidation (USD)"].mean() or 0.0
                max_short_liq = liquidacoes["Short Liquidation (USD)"].max() or 0.0
                last_short_liq = liquidacoes["Short Liquidation (USD)"].iloc[-1] or 0.0

                # Gerando a análise
                liquidacoes_anl = (
                    f"Durante o período analisado, o valor médio de liquidações Long foi de {avg_long_liq:.2f} USD, "
                    f"com um pico máximo de {max_long_liq:.2f} USD. O valor de liquidação Long mais recente foi de {last_long_liq:.2f} USD.\n"
                    f"Para liquidações Short, o valor médio foi de {avg_short_liq:.2f} USD, "
                    f"com um pico máximo de {max_short_liq:.2f} USD. O valor de liquidação Short mais recente foi de {last_short_liq:.2f} USD."
                )

                return liquidacoes_anl
            else:
                return "Nenhum dado foi retornado para análise."
            
    class ls_ratio:
        BASE_URL = "https://open-api.coinglass.com/api/pro/v1/futures/long_short_chart"
        headers = {
            "accept": "application/json",
            "coinglassSecret": os.getenv('COINGLASS_KEY')
        }

        def get_long_short_ratio(self, symbol="BTC", interval=30, exchName="Binance"):
            params = {
                "symbol": symbol.upper(),
                "exchName": exchName,
                "type": f"{interval}min"
            }
            try:
                response = requests.get(self.BASE_URL, headers=self.headers, params=params)
                data = response.json()

                # Verifica se a resposta da API foi bem-sucedida
                if data.get("code") != 0:
                    print(f"Erro na API: {data.get('msg')}")
                    return None

                if not data.get("data"):
                    print("Nenhum dado retornado pela API de Long/Short Ratio.")
                    return None

                return data["data"]
            except Exception as e:
                print(f"Exceção ao chamar a API de Long/Short Ratio: {e}")
                return None

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)  # Timestamps em milissegundos
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_long_short_ratio_to_df(self, data):
            records = []
            for item in data:
                long_ratio = item.get("longRate", 0)
                short_ratio = item.get("shortRate", 0)
                timestamp = item.get("date")
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Long Account (%)": long_ratio,
                    "Short Account (%)": short_ratio,
                    "Long/Short Ratio": float(long_ratio) / float(short_ratio) if float(short_ratio) != 0 else None
                })
            df = pd.DataFrame(records)
            return df

        def fetch_long_short_ratio(self, symbol="BTC", interval=30, exchName="Binance"):
            data = self.get_long_short_ratio(symbol=symbol, interval=interval, exchName=exchName)
            if data:
                df = self.process_long_short_ratio_to_df(data)
                return df
            else:
                return pd.DataFrame()

        def analysis(self):
            long_short_ratio = self.fetch_long_short_ratio()

            if not long_short_ratio.empty:
                # Converter as colunas para float
                long_short_ratio["Long Account (%)"] = pd.to_numeric(long_short_ratio["Long Account (%)"], errors='coerce')
                long_short_ratio["Short Account (%)"] = pd.to_numeric(long_short_ratio["Short Account (%)"], errors='coerce')
                long_short_ratio["Long/Short Ratio"] = pd.to_numeric(long_short_ratio["Long/Short Ratio"], errors='coerce')

                # Cálculo das estatísticas básicas
                avg_ratio = long_short_ratio["Long/Short Ratio"].mean()
                max_ratio = long_short_ratio["Long/Short Ratio"].max()
                last_ratio = long_short_ratio["Long/Short Ratio"].iloc[-1]

                # Identificando a tendência
                trend = "acima da média" if last_ratio > avg_ratio else "abaixo da média"

                # Gerando a análise
                long_short_anl = (
                    f"A proporção média Long/Short para o Bitcoin no período analisado é de {avg_ratio:.4f}. "
                    f"O maior valor registrado foi de {max_ratio:.4f}. "
                    f"O valor mais recente está {trend}, indicando uma possível "
                    f"{'predominância de posições longas' if trend == 'acima da média' else 'predominância de posições curtas'}."
                )

                return long_short_anl
            else:
                return "Nenhum dado foi retornado para análise."
            
    class funding_rate_ohlc:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/fundingRate/ohlc-history"

        def get_funding_rate_ohlc(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": os.getenv('COINGLASS_KEY')  # Certifique-se de que sua chave de API está correta
            }

            params = {
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Erro na requisição funding_rate_ohlc: {response.text}")
                return None

            data = response.json()
            if data.get("code") != "0":
                print(f"Erro na resposta da API funding_rate_ohlc: {data.get('msg')}")
                return None

            return data

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_data_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data.get("data", []):
                open_price = item.get("o", "N/A")
                high_price = item.get("h", "N/A")
                low_price = item.get("l", "N/A")
                close_price = item.get("c", "N/A")
                timestamp = item.get("t", 0)
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Open": open_price,
                    "High": high_price,
                    "Low": low_price,
                    "Close": close_price
                })
            df = pd.DataFrame(records)
            return df

        def fetch_funding_rate(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            data = self.get_funding_rate_ohlc(symbol=symbol, exchange=exchange, interval=interval)
            df = self.process_data_to_df(data)
            return df

        def analysis(self):
            funding_rate_df = self.fetch_funding_rate()

            if not funding_rate_df.empty:
                # Converter a coluna 'Close' para float
                funding_rate_df['Close'] = funding_rate_df['Close'].astype(float)

                avg_close = funding_rate_df['Close'].mean()
                max_close = funding_rate_df['Close'].max()
                last_close = funding_rate_df['Close'].iloc[-1]

                if last_close > avg_close:
                    trend = "acima da média"
                else:
                    trend = "abaixo da média"

                funding_rate_anl = (
                    f"O funding rate médio para o Bitcoin é de {avg_close:.6f}. "
                    f"O maior valor de fechamento foi {max_close:.6f}. "
                    f"O fechamento mais recente está {trend}, indicando uma possível "
                    f"{'alta' if trend == 'acima da média' else 'queda'} em relação à média."
                )

                return funding_rate_anl
            else:
                return "Nenhum dado foi retornado para análise, funding_rate_ohlc"

            
    class oi_weight_ohlc:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/fundingRate/oi-weight-ohlc-history"

        def get_oi_weight_ohlc_history(self, symbol="BTC", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": os.getenv('COINGLASS_KEY')
            }

            params = {
                "symbol": symbol,
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Erro na requisição, oi_weight_ohlc: {response.text}")
                return None

            data = response.json()
            if data.get("code") != "0":
                print(f"Erro na resposta da API, oi_weight_ohlc: {data.get('msg')}")
                return None

            return data

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_data_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data.get("data", []):
                open_price = item.get("o", "N/A")
                high_price = item.get("h", "N/A")
                low_price = item.get("l", "N/A")
                close_price = item.get("c", "N/A")
                timestamp = item.get("t", 0)
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Open": open_price,
                    "High": high_price,
                    "Low": low_price,
                    "Close": close_price
                })
            df = pd.DataFrame(records)
            return df

        def fetch_oi_weight(self, symbol="BTC", interval="30m"):
            data = self.get_oi_weight_ohlc_history(symbol=symbol, interval=interval)
            df = self.process_data_to_df(data)
            return df

        def analysis(self):
            oi_weight_df = self.fetch_oi_weight()

            if not oi_weight_df.empty:
                # Converter a coluna 'Close' para float
                oi_weight_df['Close'] = oi_weight_df['Close'].astype(float)

                avg_close = oi_weight_df['Close'].mean()
                max_close = oi_weight_df['Close'].max()
                last_close = oi_weight_df['Close'].iloc[-1]

                if last_close > avg_close:
                    trend = "acima da média"
                else:
                    trend = "abaixo da média"

                # Gerando a análise
                analysis = (
                    f"O funding rate ponderado pelo open interest para o Bitcoin tem uma média de {avg_close:.6f}. "
                    f"O maior valor de fechamento foi {max_close:.6f}. "
                    f"O fechamento mais recente está {trend}, indicando uma possível "
                    f"{'alta' if trend == 'acima da média' else 'queda'} em relação à média."
                )

                return analysis

            else:
                return "Nenhum dado foi retornado para análise, oi_weight_ohlc"
                

    
    class fundingratevol:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/fundingRate/vol-weight-ohlc-history"

        def get_vol_weight_ohlc_history(self, symbol="BTC", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": os.getenv('COINGLASS_KEY')
            }

            params = {
                "symbol": symbol,
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Erro na requisição: {response.text}")
                return None

            data = response.json()

            if data.get("code") != "0":
                print(f"Erro na resposta da API, fundingratevol: {data.get('msg')}")
                return None

            return data

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_data_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data.get("data", []):
                open_price = item.get("o", "N/A")
                high_price = item.get("h", "N/A")
                low_price = item.get("l", "N/A")
                close_price = item.get("c", "N/A")
                timestamp = item.get("t", 0)
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Open": open_price,
                    "High": high_price,
                    "Low": low_price,
                    "Close": close_price
                })
            df = pd.DataFrame(records)
            return df

        def fetch_vol_weight(self, symbol="BTC", interval="30m"):
            data = self.get_vol_weight_ohlc_history(symbol=symbol, interval=interval)
            df = self.process_data_to_df(data)
            return df

        def analysis(self):
            vol_weight_df = self.fetch_vol_weight()

            if not vol_weight_df.empty:
                vol_weight_df['Close'] = vol_weight_df['Close'].astype(float)

                avg_close = vol_weight_df['Close'].mean()
                max_close = vol_weight_df['Close'].max()
                last_close = vol_weight_df['Close'].iloc[-1]

                if last_close > avg_close:
                    trend = "acima da média"
                else:
                    trend = "abaixo da média"

                funding_rate_vol = (
                    f"O funding rate ponderado pelo volume para o Bitcoin tem uma média de {avg_close:.6f}. "
                    f"O maior valor de fechamento foi {max_close:.6f}. "
                    f"O fechamento mais recente está {trend}, indicando uma possível "
                    f"{'alta' if trend == 'acima da média' else 'queda'} em relação à média."
                )

                return funding_rate_vol

            else:
                return "Nenhum dado foi retornado para análise."
            
    class oi_ohlc:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/openInterest/ohlc-history"

        def get_open_interest_ohlc_history(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": os.getenv('COINGLASS_KEY')
            }

            params = {
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Erro na requisição: {response.text}")
                return None

            data = response.json()

            if data.get("code") != "0":
                print(f"Erro na resposta da API, oi_ohlc: {data.get('msg')}")
                return None

            return data

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_data_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data.get("data", []):
                open_price = item.get("o", "N/A")
                high_price = item.get("h", "N/A")
                low_price = item.get("l", "N/A")
                close_price = item.get("c", "N/A")
                timestamp = item.get("t", 0)
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Open": open_price,
                    "High": high_price,
                    "Low": low_price,
                    "Close": close_price
                })

            df = pd.DataFrame(records)
            return df

        def fetch_open_interest(self, symbol="BTCUSDT", exchange="Binance", interval="30m"):
            data = self.get_open_interest_ohlc_history(symbol=symbol, exchange=exchange, interval=interval)
            df = self.process_data_to_df(data)
            return df

        def analysis(self):
            open_interest_df = self.fetch_open_interest()

            if not open_interest_df.empty:
                # Converter a coluna 'Close' para float
                open_interest_df['Close'] = open_interest_df['Close'].astype(float)

                avg_close = open_interest_df['Close'].mean()
                max_close = open_interest_df['Close'].max()
                last_close = open_interest_df['Close'].iloc[-1]

                if last_close > avg_close:
                    trend = "acima da média"
                else:
                    trend = "abaixo da média"

                open_interest_anl = (
                    f"O open interest médio para o Bitcoin é de {avg_close:.2f}. "
                    f"O maior valor de fechamento foi {max_close:.2f}. "
                    f"O fechamento mais recente está {trend}, indicando uma possível "
                    f"{'aumento' if trend == 'acima da média' else 'redução'} em relação à média."
                )

                return open_interest_anl

            else:
                return "Nenhum dado foi retornado para análise, oi_ohlc"
            
    class oi_ohlc_aggregated_history:
        BASE_URL = "https://open-api-v3.coinglass.com/api/futures/openInterest/ohlc-aggregated-history"

        def get_ohlc_aggregated_history(self, symbol="BTC", interval="30m"):
            headers = {
                "accept": "application/json",
                "CG-API-KEY": '936395e1aa6943659c5ff7b729981532' # Certifique-se de que a chave de API está correta
            }

            params = {
                "symbol": symbol.upper(),
                "interval": interval
            }

            response = requests.get(self.BASE_URL, headers=headers, params=params)

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

        def convert_to_brt(self, timestamp):
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            brt_tz = pytz.timezone('America/Sao_Paulo')
            dt_brt = dt.astimezone(brt_tz)
            return dt_brt.strftime('%Y-%m-%d %H:%M:%S')

        def process_data_to_df(self, data):
            if data is None:
                return pd.DataFrame()

            records = []
            for item in data:
                open_price = item.get("o", "N/A")
                high_price = item.get("h", "N/A")
                low_price = item.get("l", "N/A")
                close_price = item.get("c", "N/A")
                timestamp = item.get("t", 0)
                brt_time = self.convert_to_brt(timestamp)
                records.append({
                    "Data/Hora (São Paulo)": brt_time,
                    "Open": open_price,
                    "High": high_price,
                    "Low": low_price,
                    "Close": close_price
                })
            df = pd.DataFrame(records)
            return df

        def fetch_ohlc_history(self, symbol="BTC", interval="30m"):
            data = self.get_ohlc_aggregated_history(symbol=symbol, interval=interval)
            df = self.process_data_to_df(data)
            return df

        def analysis(self):
            ohlc_aggregated_history = self.fetch_ohlc_history()

            if not ohlc_aggregated_history.empty:
                # Converter a coluna 'Close' para float
                ohlc_aggregated_history["Close"] = ohlc_aggregated_history["Close"].astype(float)

                avg_close = ohlc_aggregated_history["Close"].mean()
                max_close = ohlc_aggregated_history["Close"].max()
                last_close = ohlc_aggregated_history["Close"].iloc[-1]

                trend = "acima da média" if last_close > avg_close else "abaixo da média"

                analysis = (
                    f"O valor médio de fechamento do Open Interest para o Bitcoin no período analisado é de {avg_close:.2f}. "
                    f"O valor máximo registrado foi de {max_close:.2f}. "
                    f"O valor de fechamento mais recente está {trend}, indicando uma possível "
                    f"{'alta' if trend == 'acima da média' else 'queda'}."
                )

                return analysis
            else:
                return "Nenhum dado foi retornado para análise."