from derivatives2 import derivatives_data
from onchain_data import OnChain
from economic_data import economic_dt
import requests
from datetime import datetime, timedelta

def get_bitcoin_price_and_variation():
    # URL base da API do CoinGecko
    base_url = "https://api.coingecko.com/api/v3"

    # Endpoint para o preço atual do Bitcoin
    price_url = f"{base_url}/simple/price?ids=bitcoin&vs_currencies=usd"
    response = requests.get(price_url)
    data = response.json()
    
    # Preço atual do Bitcoin
    current_price = data['bitcoin']['usd']
    
    # Função auxiliar para calcular a variação de preço
    def get_variation(days):
        date = (datetime.now() - timedelta(days=days)).strftime('%d-%m-%Y')
        market_data_url = f"{base_url}/coins/bitcoin/history?date={date}"
        response = requests.get(market_data_url)
        historical_data = response.json()
        historical_price = historical_data['market_data']['current_price']['usd']
        variation = ((current_price - historical_price) / historical_price) * 100
        return variation
    
    # Cálculo das variações
    variation_30d = get_variation(30)
    variation_14d = get_variation(14)
    variation_7d = get_variation(7)

    # Formatação e retorno do texto
    return (
        f"Preço atual do Bitcoin: ${current_price:.2f}\n"
        f"Variação nos últimos 30 dias: {variation_30d:.2f}%\n"
        f"Variação nos últimos 14 dias: {variation_14d:.2f}%\n"
        f"Variação nos últimos 7 dias: {variation_7d:.2f}%"
    )
    
def run_all_analyses():
    results = {}

    try:
        # Obtém o preço e variação do Bitcoin
        bitcoin_analysis = get_bitcoin_price_and_variation()
        results["Bitcoin Analysis"] = bitcoin_analysis
        print("Bitcoin Analysis:", bitcoin_analysis)  # Debug
    except Exception as e:
        print(f"Erro em Bitcoin Analysis: {e}")

    try:
        # Funções da classe de dados derivativos
        deriv_data = derivatives_data()

        # Profundidade do mercado
        results["Market Depth Analysis"] = deriv_data.market_depth().analysis()
        print("Market Depth Analysis:", results["Market Depth Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Market Depth Analysis: {e}")

    try:
        # Liquidações
        results["Liquidations Analysis"] = deriv_data.liquidations().analysis()
        print("Liquidations Analysis:", results["Liquidations Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Liquidations Analysis: {e}")

    try:
        # Long/Short Ratio
        results["Long/Short Ratio Analysis"] = deriv_data.ls_ratio().analysis()
        print("Long/Short Ratio Analysis:", results["Long/Short Ratio Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Long/Short Ratio Analysis: {e}")

    try:
        # Funding rate vol
        results["Funding Rate Volume Analysis"] = deriv_data.fundingratevol().analysis()
        print("Funding Rate Volume Analysis:", results["Funding Rate Volume Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Funding Rate Volume Analysis: {e}")

    try:
        # Funding rate ohlc
        results["Funding Rate OHLC Analysis"] = deriv_data.funding_rate_ohlc().analysis()
        print("Funding Rate OHLC Analysis:", results["Funding Rate OHLC Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Funding Rate OHLC Analysis: {e}")

    try:
        # oi_weight_ohlc
        results["OI Weight OHLC Analysis"] = deriv_data.oi_weight_ohlc().analysis()
        print("OI Weight OHLC Analysis:", results["OI Weight OHLC Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em OI Weight OHLC Analysis: {e}")

    try:
        # oi_ohlc
        results["OI OHLC Analysis"] = deriv_data.oi_ohlc().analysis()
        print("OI OHLC Analysis:", results["OI OHLC Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em OI OHLC Analysis: {e}")

    try:
        # oi_ohlc history
        results["OI OHLC History Analysis"] = deriv_data.oi_ohlc_history().analysis()
        print("OI OHLC History Analysis:", results["OI OHLC History Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em OI OHLC History Analysis: {e}")

    try:
        # Volume de opções
        options_vol = derivatives_data.options_volume()
        results["Options Volume Analysis"] = options_vol.analysis()
        print("Options Volume Analysis:", results["Options Volume Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Options Volume Analysis: {e}")

    try:
        # CVD
        cvd = derivatives_data.cvd_data()
        results["CVD Analysis"] = cvd.analysis()
        print("CVD Analysis:", results["CVD Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em CVD Analysis: {e}")

    try:
        # Volume change
        vol_change = derivatives_data.volume_change()
        results["Volume Change Analysis"] = vol_change.analysis()
        print("Volume Change Analysis:", results["Volume Change Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Volume Change Analysis: {e}")

    try:
        # Skew
        skew = derivatives_data.skew()
        results["Skew Analysis"] = skew.analysis()
        print("Skew Analysis:", results["Skew Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Skew Analysis: {e}")

    try:
        # IV
        iv = derivatives_data.iv()
        results["IV Analysis"] = iv.analysis()
        print("IV Analysis:", results["IV Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em IV Analysis: {e}")

    try:
        # Funções da classe de dados on chain
        on_chain_volume = OnChain.on_chain_volume()
        results["On-Chain Volume Analysis"] = on_chain_volume.analysis()
        print("On-Chain Volume Analysis:", results["On-Chain Volume Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em On-Chain Volume Analysis: {e}")

    try:
        blockchain_data = OnChain.BlockchainData()
        results["Blockchain Data Analysis"] = blockchain_data.analysis()
        print("Blockchain Data Analysis:", results["Blockchain Data Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Blockchain Data Analysis: {e}")

    try:
        exchange_flow = OnChain.ExchangeFlow()
        results["Exchange Flow Analysis"] = exchange_flow.analysis()
        print("Exchange Flow Analysis:", results["Exchange Flow Analysis"])  # Debug
    except Exception as e:
        print(f"Erro em Exchange Flow Analysis: {e}")

    try:
        # Dados econômicos
        news_analyzer = economic_dt.economic_news()
        econ_data = economic_dt()

        results["CPI Data"] = econ_data.cpi_data()
        print("CPI Data:", results["CPI Data"])  # Debug

        results["PCE Data"] = econ_data.pce_data()
        print("PCE Data:", results["PCE Data"])  # Debug

        results["PIB Data"] = econ_data.pib_data()
        print("PIB Data:", results["PIB Data"])  # Debug

        results["S&P 500 and Nasdaq Indices Analysis"] = econ_data.analyze_indice()
        print("S&P 500 and Nasdaq Indices Analysis:", results["S&P 500 and Nasdaq Indices Analysis"])  # Debug

        results["Top 8 Bitcoin News"] = news_analyzer.get_top_news_of_month_with_sentiment('Bitcoin')
        print("Top 8 Bitcoin News:", results["Top 8 Bitcoin News"])  # Debug

        results["Top 8 Global Economy News"] = news_analyzer.get_top_news_of_month_with_sentiment('Global Economy')
        print("Top 8 Global Economy News:", results["Top 8 Global Economy News"])  # Debug

        results["Bitcoin-Gold Correlation"] = econ_data.gold_correlation()
        print("Bitcoin-Gold Correlation:", results["Bitcoin-Gold Correlation"])  # Debug
    except Exception as e:
        print(f"Erro em Economic Data Analysis: {e}")

    return results