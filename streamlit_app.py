import streamlit as st
import os
import pandas as pd
import pytz
from datetime import datetime, timedelta
import plotly.graph_objects as go
from database.database_setting import connect_to_db
#from exec_script import get_bitcoin_data
import re
from sqlalchemy import create_engine
import pandas as pd
import logging
import numpy as np
import requests
import matplotlib.pyplot as plt


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
st.set_page_config(page_title="GPT_BTC", page_icon="🪙", layout="centered")
brazil_tz = pytz.timezone('America/Sao_Paulo')

def format_time(dt):
    return dt.strftime('%H:%M:%S')

def get_bitcoin_data(limit):
    connection = connect_to_db()
    query = f"""
    SELECT 
        datetime as timestamp,
        value_btc as price
    FROM chatbot_data
    WHERE value_btc IS NOT NULL
    ORDER BY datetime DESC
    LIMIT {limit}
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    
    if not df.empty:
        return df
    return None


def get_bitcoin_returns(analysis_date):
    # Converter a data de análise para o formato necessário
    analysis_date_str = analysis_date.strftime("%d-%m-%Y")
    
    # Calcular a data do dia anterior
    previous_date = analysis_date - timedelta(days=1)
    previous_date_str = previous_date.strftime("%d-%m-%Y")
    
    # Fazer a chamada à API do CoinGecko
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={analysis_date_str}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        current_price = data['market_data']['current_price']['usd']
        
        # Obter o preço do dia anterior
        url_previous = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={previous_date_str}"
        response_previous = requests.get(url_previous)
        
        if response_previous.status_code == 200:
            data_previous = response_previous.json()
            previous_price = data_previous['market_data']['current_price']['usd']
            
            # Calcular o retorno
            daily_return = (current_price - previous_price) / previous_price
            
            return pd.DataFrame({
                'date': [analysis_date],
                'price': [current_price],
                'daily_return': [daily_return],
                'cumulative_return': [daily_return]  # Para um dia, é o mesmo que o retorno diário
            })
    
    # Se algo der errado, retornar um DataFrame vazio
    return pd.DataFrame(columns=['date', 'price', 'daily_return', 'cumulative_return'])


def calculate_trade_returns():
    connection = connect_to_db()
    query = """
    SELECT 
        prediction_date,
        btc_open,
        btc_close,
        recommendation,
        stop_loss,
        take_profit
    FROM 
        chatbot_data
    WHERE 
        actual_date IS NOT NULL
    ORDER BY 
        prediction_date
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    
    # Standardize the recommendation strings
    df['recommendation'] = df['recommendation'].str.lower().str.strip()
    recommendation_mapping = {
        'comprar': 'compra',
        'compra': 'compra',
        'vender': 'venda',
        'venda': 'venda',
        'aguardar': 'aguardar'
    }
    df['recommendation'] = df['recommendation'].map(recommendation_mapping).fillna('aguardar')
    
    # Convert prediction_date to datetime and sort
    df['prediction_date'] = pd.to_datetime(df['prediction_date'])
    df = df.sort_values('prediction_date')
    
    # Initialize variables
    trade_returns = []
    position = None
    entry_price = None
    stop_loss = None
    take_profit = None
    entry_date = None
    cumulative_return = 1.0  # Start with 1.0 for multiplicative returns
    
    # Create a date range from the minimum to the maximum prediction_date
    all_dates = pd.date_range(start=df['prediction_date'].min(), end=df['prediction_date'].max())
    
    for current_date in all_dates:
        daily_data = df[df['prediction_date'] == current_date]
        
        if not daily_data.empty:
            # Process all recommendations for the current date
            for _, row in daily_data.iterrows():
                close = row['btc_close']
                open_price = row['btc_open']
                recommendation = row['recommendation']
                sl = row['stop_loss']
                tp = row['take_profit']
    
                # Debugging: Print current processing information
                print(f"Processing Date: {current_date.date()} | Recommendation: {recommendation}")
    
                if position is None:
                    if recommendation in ['compra', 'venda']:
                        position = recommendation
                        entry_price = open_price
                        stop_loss = sl
                        take_profit = tp
                        entry_date = current_date
                        print(f"Entered Position: {position} at {entry_price}")
                else:
                    # Only close the position; do not open a new one until current is closed
                    if position == 'compra':
                        if pd.isna(close):
                            # Cannot close position, keep it open
                            print(f"Cannot close 'compra' position on {current_date.date()} due to NaN close price.")
                            continue
                        if close >= take_profit:
                            exit_price = take_profit
                            daily_return = (exit_price - entry_price) / entry_price
                            print(f"Take Profit hit for compra. Exit at {exit_price}")
                        elif close <= stop_loss:
                            exit_price = stop_loss
                            daily_return = (exit_price - entry_price) / entry_price
                            print(f"Stop Loss hit for compra. Exit at {exit_price}")
                        else:
                            exit_price = close
                            daily_return = (exit_price - entry_price) / entry_price
                            print(f"Position 'compra' closed at market price {exit_price}")
    
                        cumulative_return *= (1 + daily_return)
                        position = None
                        entry_price = None
                        stop_loss = None
                        take_profit = None
                        entry_date = None
                        print(f"Cumulative Return Updated: {(cumulative_return - 1) * 100:.6f}%")
    
                    elif position == 'venda':
                        if pd.isna(close):
                            # Cannot close position, keep it open
                            print(f"Cannot close 'venda' position on {current_date.date()} due to NaN close price.")
                            continue
                        if close <= take_profit:
                            exit_price = take_profit
                            daily_return = (entry_price - exit_price) / entry_price
                            print(f"Take Profit hit for venda. Exit at {exit_price}")
                        elif close >= stop_loss:
                            exit_price = stop_loss
                            daily_return = (entry_price - exit_price) / entry_price
                            print(f"Stop Loss hit for venda. Exit at {exit_price}")
                        else:
                            exit_price = close
                            daily_return = (entry_price - exit_price) / entry_price
                            print(f"Position 'venda' closed at market price {exit_price}")
    
                        cumulative_return *= (1 + daily_return)
                        position = None
                        entry_price = None
                        stop_loss = None
                        take_profit = None
                        entry_date = None
                        print(f"Cumulative Return Updated: {(cumulative_return - 1) * 100:.6f}%")
        
        # Append the cumulative return for the current date
        trade_returns.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'cumulative_return': (cumulative_return - 1) * 100  # Convert to percentage
        })
    
    # Convert to DataFrame
    df_returns = pd.DataFrame(trade_returns)
    
    return df_returns

def plot_cumulative_returns():
    df_returns = calculate_trade_returns()
    print(df_returns)

    plt.figure(figsize=(12, 6))
    plt.plot(df_returns['date'], df_returns['cumulative_return'], marker='o', label='Retorno Acumulado das Operações')
    plt.xlabel('Data')
    plt.ylabel('Retorno Acumulado (%)')
    plt.title('Retorno Acumulado Diário das Operações')
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid()
    plt.show()

    return df_returns

def calculate_btc_cumulative_return():
    connection = connect_to_db()
    query = """
    SELECT 
        DATE(datetime) as date, 
        MAX(value_btc) as price
    FROM chatbot_data
    WHERE value_btc IS NOT NULL
    GROUP BY DATE(datetime)
    ORDER BY DATE(datetime)
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    
    # Calcular o retorno cumulativo
    cumulative_return = 0
    results = []
    previous_price = None

    for i, row in df.iterrows():
        current_price = row['price']
        date = row['date']

        if previous_price is not None:
            daily_return = (current_price - previous_price) / previous_price * 100
            cumulative_return += daily_return
        else:
            daily_return = 0  # No primeiro dia, não há retorno

        results.append({
            'date': date.strftime('%Y-%m-%d'),
            'cumulative_return': cumulative_return
        })

        previous_price = current_price

    return results





def prepare_data_for_graph(ai_returns, btc_returns):
    ai_df = pd.DataFrame(ai_returns)
    ai_df['date'] = pd.to_datetime(ai_df['date'])
    ai_df = ai_df.rename(columns={'date': 'prediction_date'})

    btc_df = pd.DataFrame(btc_returns)
    btc_df['date'] = pd.to_datetime(btc_df['date'])

    # Ensure both dataframes cover the same date range
    start_date = max(ai_df['prediction_date'].min(), btc_df['date'].min())
    end_date = min(ai_df['prediction_date'].max(), btc_df['date'].max())

    ai_df = ai_df[(ai_df['prediction_date'] >= start_date) & (ai_df['prediction_date'] <= end_date)]
    btc_df = btc_df[(btc_df['date'] >= start_date) & (btc_df['date'] <= end_date)]

    return ai_df, btc_df


def display_comparison_graph(ai_returns, btc_returns):
    operation_data, btc_data = prepare_data_for_graph(ai_returns, btc_returns)

    st.header("Comparação de Rentabilidade")
    
    fig = go.Figure()

    # Gráfico de rentabilidade das operações
    if not operation_data.empty:
        fig.add_trace(go.Scatter(
            x=operation_data['prediction_date'], 
            y=operation_data['cumulative_return'], 
            mode='lines+markers',  # Linha contínua com marcadores
            name='Rentabilidade das Operações'
        ))

    # Gráfico de rentabilidade do Bitcoin (com marcadores)
    if not btc_data.empty:
        fig.add_trace(go.Scatter(
            x=btc_data['date'], 
            y=btc_data['cumulative_return'], 
            mode='lines+markers',  # Adicionando os marcadores
            name='Rentabilidade do Bitcoin'
        ))

    # Configurações de layout do gráfico
    fig.update_layout(
        title='Comparação de Rentabilidade: Operações vs Bitcoin',
        xaxis_title='Data',
        yaxis_title='Retorno Cumulativo (%)',
        showlegend=True
    )

    # Ajuste de limites do eixo Y
    y_min = min(operation_data['cumulative_return'].min() if not operation_data.empty else 0,
                btc_data['cumulative_return'].min() if not btc_data.empty else 0)
    y_max = max(operation_data['cumulative_return'].max() if not operation_data.empty else 0,
                btc_data['cumulative_return'].max() if not btc_data.empty else 0)
    y_range = y_max - y_min
    fig.update_yaxes(range=[y_min - 0.1 * y_range, y_max + 0.1 * y_range])

    st.plotly_chart(fig)


def get_gpt_analysis():
    connection = connect_to_db()
    query = """
    SELECT 
        datetime,
        response,
        recommendation,
        trust_rate,
        stop_loss,
        take_profit,
        risk_return,
        value_btc
    FROM 
        chatbot_data
    WHERE 
        recommendation IS NOT NULL
        AND trust_rate IS NOT NULL
        AND stop_loss IS NOT NULL
        AND take_profit IS NOT NULL
        AND risk_return IS NOT NULL
    ORDER BY 
        datetime DESC 
    LIMIT 1
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    
    if not df.empty:
        result = df.iloc[0].to_dict()
        # Converter valores para float, se possível
        for col in ['trust_rate', 'stop_loss', 'take_profit']:
            if pd.notna(result[col]):
                try:
                    result[col] = float(result[col])
                except ValueError:
                    result[col] = 0.0  # ou outro valor padrão
        return result
    else:
        return None

def display_bitcoin_data():
    # Fetch Bitcoin data from CoinGecko API
    url = "https://api.coingecko.com/api/v3/coins/bitcoin"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        
        # Extract relevant information
        current_price = data['market_data']['current_price']['usd']
        market_cap = data['market_data']['market_cap']['usd']
        total_volume = data['market_data']['total_volume']['usd']
        price_change_24h = data['market_data']['price_change_percentage_24h']
        price_change_7d = data['market_data']['price_change_percentage_7d']
        price_change_30d = data['market_data']['price_change_percentage_30d']
        
        # Helper function to create color-coded delta strings with arrows
        def format_delta(value):
            color = "green" if value > 0 else "red"
            arrow = "↑" if value > 0 else "↓"
            return f"<span style='color: {color};'>{value:.2f}% {arrow}</span>"
        
        # Display data
        col1, col2 = st.columns(2)
        
        col1.metric(label="Preço Atual", value=f"${current_price:,.2f}", 
                    delta=price_change_24h,
                    delta_color="normal")
        col2.metric(label="Capitalização de Mercado", value=f"${market_cap:,.0f}")
        
        col1, col2, col3 = st.columns(3)
        
        col1.markdown(f"*Variação 24h*\n{format_delta(price_change_24h)}", unsafe_allow_html=True)
        col2.markdown(f"*Variação 7d*\n{format_delta(price_change_7d)}", unsafe_allow_html=True)
        col3.markdown(f"*Variação 30d*\n{format_delta(price_change_30d)}", unsafe_allow_html=True)
        
        # Fetch historical data to calculate median volume
        historical_url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30&interval=daily"
        historical_response = requests.get(historical_url)
        if historical_response.status_code == 200:
            historical_data = historical_response.json()
            volumes = [v[1] for v in historical_data['total_volumes']]
            median_volume = sorted(volumes)[len(volumes)//2]
        
            volume_color = "red" if total_volume < median_volume else "green"
            volume_arrow = "↓" if total_volume < median_volume else "↑"
        
            st.markdown("*Volume de Negociação 24h*")
            st.markdown(f"${total_volume:,.0f}")
            st.markdown(
                f"<span style='color: {volume_color};'>Mediana 30d: ${median_volume:,.0f} {volume_arrow}</span>",
                unsafe_allow_html=True
            )
        else:
            st.metric(label="Volume de Negociação 24h", value=f"${total_volume:,.0f}")
            st.warning("Não foi possível calcular o volume médio.")
        
        # Additional data
        st.subheader("Informações Adicionais")
        col1, col2 = st.columns(2)
        col1.write(f"Máxima Histórica: ${data['market_data']['ath']['usd']:,.2f}")
        
        # Last updated timestamp
        last_updated = datetime.fromisoformat(data['last_updated'].replace('Z', '+00:00'))
        st.write(f"Última Atualização: {last_updated.strftime('%d/%m/%Y %H:%M:%S')} UTC")
    else:
        st.error("Falha ao obter dados do Bitcoin da API CoinGecko.")

def display_next_updates():
    st.header("Próximas Atualizações")
    col1, col2, col3, col4 = st.columns(4)
    now = datetime.now(brazil_tz)
    
    col1.metric("Próxima Análise GPT", 
                format_time(now.replace(hour=21, minute=0, second=0, microsecond=0) + timedelta(days=1 if now.hour >= 21 else 0)))
    col2.metric("Próxima Inserção de Dados BTC", 
                format_time(now.replace(hour=21, minute=5, second=0, microsecond=0) + timedelta(days=1 if now.hour >= 21 else 0)))
    col3.metric("Próxima Atualização de Operações", 
                format_time((now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)))
    col4.metric("Próxima Atualização de Dados BTC", 
                format_time((now + timedelta(minutes=1)).replace(second=0, microsecond=0)))

def display_chart(operation_data, btc_data):
    st.header("Comparação de Rentabilidade")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=operation_data['prediction_date'], y=operation_data['avg_risk_return'], 
                             mode='lines', name='Rentabilidade das Operações'))
    fig.add_trace(go.Scatter(x=btc_data['date'], y=btc_data['cumulative_return'], 
                             mode='lines', name='Rentabilidade do Bitcoin'))
    fig.update_layout(title='Comparação de Rentabilidade: Operações vs Bitcoin',
                      xaxis_title='Data', yaxis_title='Retorno Cumulativo')
    st.plotly_chart(fig)

st.image("image_btc.jpg", use_column_width=True)
st.title("📈 GPT Analista de BTC")

# Descrição com markdown e CSS
st.markdown("""
<style>
    .main-description {
        font-size: 18px;
        font-weight: 500;
        line-height: 1.6;
    }
</style>
<div class="main-description">
    Um chatbot inteligente especializado em análise de Bitcoin para operações de swing trading. 
    Ele utiliza dados em tempo real de derivativos, on-chain, análise técnica e macroeconômica para fornecer previsões dinâmicas e recomendações ajustadas conforme as condições do mercado.
</div>
""", unsafe_allow_html=True)

bitcoin_data = get_bitcoin_data(30)

st.write("## Dados do Bitcoin")
if bitcoin_data is not None:
    display_bitcoin_data()
else:
    st.error("Dados do Bitcoin não disponíveis no momento.")

display_next_updates()

ai_returns = plot_cumulative_returns()
btc_returns = calculate_btc_cumulative_return()
display_comparison_graph(ai_returns, btc_returns)

st.header("Última Análise GPT")
gpt_analysis = get_gpt_analysis()

if gpt_analysis is not None:
    st.text(f"Última análise realizada em: {gpt_analysis['datetime']}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Recomendação", gpt_analysis['recommendation'].strip())
    col2.metric("Taxa de Confiança", f"{gpt_analysis['trust_rate']:.2f}%")
    col3.metric("Valor de Entrada", f"${gpt_analysis['value_btc']:.2f}")  # Novo campo Valor de Entrada
    
    col4, col5, col6 = st.columns(3)
    col4.metric("Stop Loss", f"{gpt_analysis['stop_loss']:.2f}")
    col5.metric("Take Profit", f"{gpt_analysis['take_profit']:.2f}")
    col6.metric("Retorno de Risco", gpt_analysis['risk_return'])  # Exibindo como string
    
    response_content = gpt_analysis['response']

    st.chat_message("ai").write(response_content)
    # Explicação adicional do Retorno de Risco
    risk_return_parts = gpt_analysis['risk_return'].split(':')

else:
    st.write("Nenhuma análise disponível com todos os dados necessários.")

def get_bitcoin_data_from_db():
    # Conexão com o banco de dados
    connection = connect_to_db()
    
    # Consulta SQL para obter os dados necessários
    query = """
    SELECT 
        datetime,
        btc_open,
        btc_close,
        value_btc AS "Preço de entrada",
        recommendation AS "Recomendação",
        trust_rate AS "Nível de Confiança (%)",
        stop_loss AS "Stop Loss",
        take_profit AS "Take Profit",
        risk_return AS "Relação Risco/Recompensa"
    FROM chatbot_data
    WHERE value_btc IS NOT NULL
    ORDER BY datetime ASC
    LIMIT 100;
    """

    df = pd.read_sql_query(query, connection)
    connection.close()

    # Ordenar o DataFrame por datetime
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)

    # Adicionar colunas para armazenar o preço de entrada e o estado da posição
    df['Preço de entrada anterior'] = None
    df['Rentabilidade Diária (%)'] = 0.0

    # Variáveis para controlar a posição
    position = None
    entry_price = None
    stop_loss = None
    take_profit = None

    for i, row in df.iterrows():
        recommendation = row['Recomendação'].lower()
        open_price = row['btc_open']
        close_price = row['btc_close']
        sl = row['Stop Loss']
        tp = row['Take Profit']

        # Se não temos uma posição aberta
        if position is None:
            df.at[i, 'Preço de entrada anterior'] = entry_price
            if recommendation in ['compra', 'venda']:
                # Abrimos uma posição
                position = recommendation
                entry_price = open_price
                stop_loss = sl
                take_profit = tp
                # Rentabilidade diária é zero, pois acabamos de abrir a posição
                daily_return = 0.0
            else:
                # Sem posição e a recomendação é "aguardar"
                daily_return = 0.0
        else:
            # Temos uma posição aberta
            df.at[i, 'Preço de entrada anterior'] = entry_price
            if position == 'compra':
                # Verifica se atingiu Take Profit ou Stop Loss
                if close_price >= take_profit:
                    # Pegou Take Profit
                    daily_return = (take_profit - entry_price) / entry_price * 100
                    position = None  # Fecha a posição
                elif close_price <= stop_loss:
                    # Pegou Stop Loss
                    daily_return = (stop_loss - entry_price) / entry_price * 100
                    position = None  # Fecha a posição
                else:
                    # Nenhum dos dois foi atingido
                    daily_return = (close_price - entry_price) / entry_price * 100
                    # Posição continua aberta
            elif position == 'venda':
                # Verifica se atingiu Take Profit ou Stop Loss
                if close_price <= take_profit:
                    # Pegou Take Profit (preço caiu)
                    daily_return = (entry_price - take_profit) / entry_price * 100
                    position = None  # Fecha a posição
                elif close_price >= stop_loss:
                    # Pegou Stop Loss (preço subiu)
                    daily_return = (entry_price - stop_loss) / entry_price * 100
                    position = None  # Fecha a posição
                else:
                    # Nenhum dos dois foi atingido
                    daily_return = (entry_price - close_price) / entry_price * 100
                    # Posição continua aberta

            # Atualiza o preço de entrada anterior
            entry_price = entry_price if position else None

        df.at[i, 'Rentabilidade Diária (%)'] = daily_return

    # Selecionar as colunas relevantes para exibição
    df = df[['datetime', 'Preço de entrada', 'Recomendação', 'Nível de Confiança (%)', 'Stop Loss', 'Take Profit', 'Relação Risco/Recompensa', 'Rentabilidade Diária (%)']]

    return df


# Obtenha os dados do banco
df = get_bitcoin_data_from_db()

# Exiba o DataFrame no Streamlit com navegação
st.write("Tabela com histórico")
st.dataframe(df, height=400)  # Define a altura para permitir rolagem

if 'update_counter' not in st.session_state:
    st.session_state.update_counter = 0

st.session_state.update_counter += 1

if st.session_state.update_counter >= 60:
    st.session_state.update_counter = 0
    st.rerun()

st.empty().text(f"Próxima atualização em {60 - st.session_state.update_counter} segundos")