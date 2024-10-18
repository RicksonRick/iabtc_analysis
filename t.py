import requests
import pandas as pd
from datetime import datetime, timezone
import pytz

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

    def fetch_liquidations(self, symbol="BTCUSDT", exchange="Binance", interval="1d"):
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

# Exemplo de uso:
if __name__ == "__main__":
    liq = Liquidations()
    resultado = liq.analysis()
    print(resultado)
