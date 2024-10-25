from analysis.derivatives import derivatives_data
from analysis.onchain_data import OnChain
from analysis.economic_data import economic_dt
import requests
from datetime import datetime, timedelta

def get_bitcoin_price_and_variation():
    base_url = "https://api.coingecko.com/api/v3"

    price_url = f"{base_url}/simple/price?ids=bitcoin&vs_currencies=usd"
    response = requests.get(price_url)
    data = response.json()

    current_price = data['bitcoin']['usd']
    
    def get_variation(days):
        date = (datetime.now() - timedelta(days=days)).strftime('%d-%m-%Y')
        market_data_url = f"{base_url}/coins/bitcoin/history?date={date}"
        response = requests.get(market_data_url)
        historical_data = response.json()
        historical_price = historical_data['market_data']['current_price']['usd']
        variation = ((current_price - historical_price) / historical_price) * 100
        return variation
    
    variation_30d = get_variation(30)
    variation_14d = get_variation(14)
    variation_7d = get_variation(7)

    return (
        f"Preço atual do Bitcoin: ${current_price:.2f}\n"
        f"Variação nos últimos 30 dias: {variation_30d:.2f}%\n"
        f"Variação nos últimos 14 dias: {variation_14d:.2f}%\n"
        f"Variação nos últimos 7 dias: {variation_7d:.2f}%"
    )
    
def run_all_analyses():
    results = {}
    deriv_data = derivatives_data()
    onchain = OnChain()
    errors = {}

    try:
        bitcoin_analysis = get_bitcoin_price_and_variation()
        results["Bitcoin Analysis"] = bitcoin_analysis
    except Exception as e:
        print(e)
        errors["Bitcoin Analysis"] = f"Erro: {e}"

    try:
        results["Market Depth Analysis"] = deriv_data.market_depth.analysis()
    except Exception as e:
        errors["Market Depth Analysis"] = f"Erro: {e}"

    try:
        results["Liquidations Analysis"] = deriv_data.liquidations_instance.analysis()
    except Exception as e:
        print(e)
        errors["Liquidations Analysis"] = f"Erro: {e}"

    try:
        results["Funding Rate Volume Analysis"] = deriv_data.fundingratevol.analysis()
    except Exception as e:
        print(e)
        errors["Funding Rate Volume Analysis"] = f"Erro: {e}"

    try:
        results["Funding Rate OHLC Analysis"] = deriv_data.funding_rate_ohlc.analysis()
    except Exception as e:
        print(e)
        errors["Funding Rate OHLC Analysis"] = f"Erro: {e}"

    try:
        results["OI Weight OHLC Analysis"] = deriv_data.oi_weight_ohlc.analysis()
    except Exception as e:
        print(e)
        errors["OI Weight OHLC Analysis"] = f"Erro: {e}"

    try:
        results["OI OHLC Analysis"] = deriv_data.oi_ohlc.analysis()
    except Exception as e:
        print(e)
        errors["OI OHLC Analysis"] = f"Erro: {e}"

    try:
        results["OI OHLC History Analysis"] = deriv_data.oi_ohlc_aggregated_history.analysis()
    except Exception as e:
        print(e)
        errors["OI OHLC History Analysis"] = f"Erro: {e}"

    try:
        results["Options Volume Analysis"] = deriv_data.options_volume.analysis()
    except Exception as e:
        print(e)
        errors["Options Volume Analysis"] = f"Erro: {e}"

    try:
        cvd = derivatives_data.cvd_data()
        results["CVD Analysis"] = cvd.analysis()
    except Exception as e:
        print(e)
        errors["CVD Analysis"] = f"Erro: {e}"

    try:
        vol_change = derivatives_data.volume_change()
        results["Volume Change Analysis"] = vol_change.analysis()
    except Exception as e:
        print(e)
        errors["Volume Change Analysis"] = f"Erro: {e}"

    try:
        skew = derivatives_data.skew()
        results["Skew Analysis"] = skew.analysis()
    except Exception as e:
        print(e)
        errors["Skew Analysis"] = f"Erro: {e}"

    try:
        iv = derivatives_data.iv()
        results["IV Analysis"] = iv.analysis()
    except Exception as e:
        print(e)
        errors["IV Analysis"] = f"Erro: {e}"

    try:
        results["On-Chain Volume Analysis"] = onchain.on_chain_volume.analysis()
    except Exception as e:
        print(e)
        errors["On-Chain Volume Analysis"] = f"Erro: {e}"

    try:
        results["Blockchain Data Analysis"] = onchain.blockchain_data.analysis()
    except Exception as e:
        print(e)
        errors["Blockchain Data Analysis"] = f"Erro: {e}"

    try:
        results["Exchange Flow Analysis"] = onchain.exchange_analysis.analysis()
    except Exception as e:
        print(e)
        errors["Exchange Flow Analysis"] = f"Erro: {e}"

    try:
        news_analyzer = economic_dt.economic_news()
        econ_data = economic_dt()

        results["CPI Data"] = econ_data.cpi_data()
        results["PCE Data"] = econ_data.pce_data()
        results["PIB Data"] = econ_data.pib_data()
        results["S&P 500 and Nasdaq Indices Analysis"] = econ_data.analyze_indice()
        results["Top 8 Bitcoin News"] = news_analyzer.get_top_news_of_month_with_sentiment('Bitcoin')
        results["Top 8 Global Economy News"] = news_analyzer.get_top_news_of_month_with_sentiment('Global Economy')
        results["Bitcoin-Gold Correlation"] = econ_data.gold_correlation()
    except Exception as e:
        errors["Economic Data Analysis"] = f"Erro: {e}"

    # Retorna resultados e erros
    return {"results": results, "errors": errors}
