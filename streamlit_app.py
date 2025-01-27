import streamlit as st
import os
import pandas as pd
import pytz
from datetime import datetime, timedelta
import plotly.graph_objects as go
from database.database_setting import connect_to_db
#from exec_script import get_bitcoin_data
import streamlit.components.v1 as components
import plotly.graph_objects as go
import re
from sqlalchemy import create_engine
import pandas as pd
import logging
import numpy as np
import requests
import matplotlib.pyplot as plt
import hashlib

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
st.set_page_config(page_title="GPT_BTC", page_icon="🪙", layout="centered")
brazil_tz = pytz.timezone('America/Sao_Paulo')

def verify_login(email, password):
    connection = connect_to_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name FROM users WHERE email = %s AND password_hash = %s",
                (email, hashlib.sha256(password.encode()).hexdigest())
            )
            return cursor.fetchone()
    finally:
        connection.close()

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
    api_key = os.getenv('COINGEKO_KEY')
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": api_key
    }
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        current_price = data['market_data']['current_price']['usd']
        
        # Obter o preço do dia anterior
        url_previous = f"https://api.coingecko.com/api/v3/coins/bitcoin/history?date={previous_date_str}"
        api_key = os.getenv('COINGEKO_KEY')
        headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": api_key
        }
        response_previous = requests.get(url_previous, headers=headers, verify=False, timeout=10)
        
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
        recommendation
    FROM 
        chatbot_data
    WHERE 
        actual_date IS NOT NULL
        AND btc_close IS NOT NULL 
        AND btc_open IS NOT NULL
        AND btc_close > 0 
        AND btc_open > 0
    ORDER BY 
        prediction_date
    """
    df = pd.read_sql_query(query, connection)
    connection.close()
    
    # Limpa e valida os dados
    df['btc_close'] = pd.to_numeric(df['btc_close'], errors='coerce')
    df['btc_open'] = pd.to_numeric(df['btc_open'], errors='coerce')
    
    # Remove valores absurdos (variação maior que 20% em um dia)
    df['daily_variation'] = abs((df['btc_close'] - df['btc_open']) / df['btc_open'])
    df = df[df['daily_variation'] < 0.20]
    
    # Padroniza as recomendações
    df['recommendation'] = df['recommendation'].str.lower().str.strip()
    recommendation_mapping = {
        'comprar': 'compra',
        'compra': 'compra',
        'vender': 'venda',
        'venda': 'venda',
        'aguardar': 'aguardar'
    }
    df['recommendation'] = df['recommendation'].map(recommendation_mapping).fillna('aguardar')
    
    # Converte datas e ordena
    df['prediction_date'] = pd.to_datetime(df['prediction_date'])
    df = df.sort_values('prediction_date')
    
    # Inicializa variáveis
    trade_returns = []
    position = None
    prev_close = None
    daily_total_return = 0.0
    
    # Processa os retornos
    for idx, row in df.iterrows():
        current_date = row['prediction_date']
        open_price = row['btc_open']
        close = row['btc_close']
        recommendation = row['recommendation']
        
        # Calcula retorno do dia
        daily_return = 0.0
        
        # Atualiza posição se não for 'aguardar'
        if recommendation != 'aguardar':
            if position != recommendation:
                logging.info(f"Mudança de posição para: {recommendation} em {open_price}")
            position = recommendation
        
        # Se temos uma posição e preço anterior, calcula o retorno
        if position and prev_close is not None:
            if position == 'compra':
                daily_return = ((close - prev_close) / prev_close) * 100
            elif position == 'venda':
                daily_return = ((prev_close - close) / prev_close) * 100
                
            daily_total_return += daily_return
            
            logging.info(f"Processing Date: {current_date.date()} | "
                        f"Position: {position} | "
                        f"Open: {open_price:.2f} | "
                        f"Close: {close:.2f} | "
                        f"Daily Return: {daily_return:.2f}% | "
                        f"Total Return: {daily_total_return:.2f}%")
        
        # Guarda o preço de fechamento para o próximo dia
        prev_close = close
        
        # Registra os resultados
        trade_returns.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'open': open_price,
            'close': close,
            'position': position if position else 'sem posição',
            'daily_return': daily_return,
            'cumulative_return': daily_total_return
        })
    
    # Converte para DataFrame
    df_returns = pd.DataFrame(trade_returns)
    
    # Validação final dos resultados
    max_daily_return = df_returns['daily_return'].abs().max()
    if max_daily_return > 10:  # Se algum retorno diário for maior que 10%
        logging.warning(f"Detectado retorno diário suspeito: {max_daily_return:.2f}%")
        logging.warning("Verifique os dados de entrada!")
    
    return df_returns



def plot_cumulative_returns(df_returns):
    plt.figure(figsize=(15, 8))
    
    # Plot principal
    plt.plot(pd.to_datetime(df_returns['date']), 
            df_returns['cumulative_return'], 
            marker='.', 
            markersize=4, 
            label='Retorno Acumulado (%)')
    
    # Formatação
    plt.grid(True, alpha=0.3)
    plt.title('Retorno Acumulado das Operações')
    plt.xlabel('Data')
    plt.ylabel('Retorno Acumulado (%)')
    plt.legend()
    
    # Formatação do eixo Y
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: '{:.1f}%'.format(y)))
    
    # Rotação das datas
    plt.xticks(rotation=45)
    
    # Adiciona estatísticas
    stats_text = f"""
    Retorno Total: {df_returns['cumulative_return'].iloc[-1]:.2f}%
    Retorno Diário Médio: {df_returns['daily_return'].mean():.2f}%
    Maior Retorno Diário: {df_returns['daily_return'].max():.2f}%
    Menor Retorno Diário: {df_returns['daily_return'].min():.2f}%
    Dias Positivos: {(df_returns['daily_return'] > 0).sum()}
    Dias Negativos: {(df_returns['daily_return'] < 0).sum()}
    """
    
    plt.figtext(0.02, 0.02, stats_text, fontsize=10, 
                bbox=dict(facecolor='white', alpha=0.8))
    
    plt.tight_layout()
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
    # Preparar dados AI
    ai_df = pd.DataFrame(ai_returns)
    ai_df['date'] = pd.to_datetime(ai_df['date'])
    ai_df = ai_df.rename(columns={'date': 'prediction_date'})

    # Preparar dados BTC
    btc_df = pd.DataFrame(btc_returns)
    btc_df['date'] = pd.to_datetime(btc_df['date'])

    # Alinhar períodos
    start_date = max(ai_df['prediction_date'].min(), btc_df['date'].min())
    end_date = min(ai_df['prediction_date'].max(), btc_df['date'].max())

    ai_df = ai_df[(ai_df['prediction_date'] >= start_date) & (ai_df['prediction_date'] <= end_date)]
    btc_df = btc_df[(btc_df['date'] >= start_date) & (btc_df['date'] <= end_date)]

    return ai_df, btc_df

def display_comparison_graph(ai_returns, btc_returns):
    operation_data, btc_data = prepare_data_for_graph(ai_returns, btc_returns)

    fig = go.Figure()

    # Gráficos de linha principais
    if not operation_data.empty:
        fig.add_trace(go.Scatter(
            x=operation_data['prediction_date'],
            y=operation_data['cumulative_return'],
            name='Rentabilidade das Operações',
            line=dict(color='#00ff9f', width=2),
            hovertemplate='%{y:.2f}%<br>%{x}<extra></extra>'
        ))

    if not btc_data.empty:
        fig.add_trace(go.Scatter(
            x=btc_data['date'],
            y=btc_data['cumulative_return'],
            name='Rentabilidade do Bitcoin',
            line=dict(color='#f7931a', width=2),
            hovertemplate='%{y:.2f}%<br>%{x}<extra></extra>'
        ))

    # Layout do gráfico (mantido o mesmo estilo Trading View)
    fig.update_layout(
        plot_bgcolor='#131722',
        paper_bgcolor='#131722',
        title={
            'text': 'Comparação de Rentabilidade: Operações vs Bitcoin',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(color='#e1e1e1', size=20)
        },
        font=dict(color='#e1e1e1'),
        xaxis=dict(
            gridcolor='#1e222d',
            showgrid=True,
            zeroline=False,
            rangeslider=dict(visible=True),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1d", step="day", stepmode="backward"),
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ]),
                font=dict(color='#e1e1e1'),
                bgcolor='#131722',
                activecolor='#1e222d'
            )
        ),
        yaxis=dict(
            gridcolor='#1e222d',
            showgrid=True,
            zeroline=False,
            tickformat='.2f',
            title=dict(text='Retorno Cumulativo (%)', font=dict(color='#e1e1e1'))
        ),
        legend=dict(
            bgcolor='rgba(19,23,34,0.8)',
            bordercolor='#1e222d',
            font=dict(color='#e1e1e1')
        ),
        hovermode='x unified',
        margin=dict(l=10, r=10, t=40, b=10)
    )

    y_min = min(operation_data['cumulative_return'].min() if not operation_data.empty else 0,
                btc_data['cumulative_return'].min() if not btc_data.empty else 0)
    y_max = max(operation_data['cumulative_return'].max() if not operation_data.empty else 0,
                btc_data['cumulative_return'].max() if not btc_data.empty else 0)
    y_range = y_max - y_min
    fig.update_yaxes(range=[y_min - 0.1 * y_range, y_max + 0.1 * y_range])

    fig.update_xaxes(showspikes=True, spikecolor='#e1e1e1', spikesnap='cursor', spikemode='across')
    fig.update_yaxes(showspikes=True, spikecolor='#e1e1e1', spikesnap='cursor')
    
    return fig

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
    
def get_bitcoin_data_from_db():
    connection = connect_to_db()
    
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
    WHERE datetime IS NOT NULL
    ORDER BY datetime ASC;
    """

    df = pd.read_sql_query(query, connection)
    connection.close()

    # Padronização inicial
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Limpa e converte valores numéricos
    numeric_columns = ['btc_open', 'btc_close', 'Preço de entrada']
    for col in numeric_columns:
        # Converte para string primeiro para lidar com formatos diferentes
        df[col] = df[col].astype(str).str.replace(',', '').str.extract('(\d+\.?\d*)').astype(float)
    
    # Preenche valores faltantes com método forward fill e depois backward fill
    df['btc_open'] = df['btc_open'].fillna(method='ffill').fillna(method='bfill')
    df['btc_close'] = df['btc_close'].fillna(method='ffill').fillna(method='bfill')
    
    # Padroniza recomendações
    df['Recomendação'] = df['Recomendação'].str.lower().str.strip()
    recommendation_mapping = {
        'comprar': 'compra',
        'compra': 'compra',
        'vender': 'venda',
        'venda': 'venda',
        'aguardar': 'aguardar'
    }
    df['Recomendação'] = df['Recomendação'].map(recommendation_mapping).fillna('aguardar')

    # Inicialização de variáveis
    position = None
    prev_close = None
    daily_returns = []
    positions = []
    entry_prices = []
    last_valid_return = 0.0

    # Processa cada linha
    for i in range(len(df)):
        try:
            current_close = df.iloc[i]['btc_close']
            current_open = df.iloc[i]['btc_open']
            recommendation = df.iloc[i]['Recomendação']
            
            # Atualiza posição se não for aguardar
            if recommendation != 'aguardar':
                position = recommendation
            
            # Calcula retorno
            if position and prev_close is not None and pd.notna(current_close) and pd.notna(prev_close):
                if position == 'compra':
                    daily_return = ((current_close - prev_close) / prev_close) * 100
                elif position == 'venda':
                    daily_return = ((prev_close - current_close) / prev_close) * 100
                
                # Limita retornos absurdos
                daily_return = np.clip(daily_return, -10, 10)
                last_valid_return = daily_return
            else:
                daily_return = 0.0 if prev_close is None else last_valid_return
            
            daily_returns.append(daily_return)
            positions.append(position if position else 'sem posição')
            entry_prices.append(current_close if position else None)
            
            # Atualiza preço anterior
            if pd.notna(current_close):
                prev_close = current_close
                
        except Exception as e:
            logging.error(f"Erro processando linha {i}: {str(e)}")
            daily_returns.append(last_valid_return)
            positions.append(position if position else 'sem posição')
            entry_prices.append(prev_close if position else None)
    
    # Adiciona colunas calculadas
    df['Rentabilidade Diária (%)'] = daily_returns
    df['Posição'] = positions
    df['Preço de Entrada'] = entry_prices
    df['Rentabilidade Acumulada (%)'] = np.cumsum(daily_returns)

    # Organiza colunas
    columns = [
        'datetime',
        'Posição',
        'Recomendação',
        'Preço de Entrada',
        'btc_open',
        'btc_close',
        'Rentabilidade Diária (%)',
        'Rentabilidade Acumulada (%)',
        'Nível de Confiança (%)',
        'Stop Loss',
        'Take Profit',
        'Relação Risco/Recompensa'
    ]
    
    # Seleciona apenas colunas existentes
    existing_columns = [col for col in columns if col in df.columns]
    df = df[existing_columns]
    
    # Formata colunas numéricas
    for col in ['Rentabilidade Diária (%)', 'Rentabilidade Acumulada (%)', 'Nível de Confiança (%)']:
        if col in df.columns:
            df[col] = df[col].round(2)
    
    # Adiciona estatísticas
    df.attrs['total_return'] = df['Rentabilidade Acumulada (%)'].iloc[-1]
    df.attrs['positive_days'] = (df['Rentabilidade Diária (%)'] > 0).sum()
    df.attrs['negative_days'] = (df['Rentabilidade Diária (%)'] < 0).sum()
    df.attrs['max_daily_return'] = df['Rentabilidade Diária (%)'].max()
    df.attrs['min_daily_return'] = df['Rentabilidade Diária (%)'].min()

    return df

def display_bitcoin_data():
    # Fetch Bitcoin data from CoinGecko API
    url = "https://api.coingecko.com/api/v3/coins/bitcoin"
    api_key = os.getenv('COINGEKO_KEY')
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": api_key
    }
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    print(f"DISPLAY BTC DATA {response.json}")
    
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
        api_key = os.getenv('COINGEKO_KEY')
        headers = {
            "accept": "application/json",
            "x-cg-demo-api-key": api_key
        }
        historical_response = requests.get(historical_url, headers=headers, verify=False, timeout=10)
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
        
        st.subheader("Informações Adicionais")
        col1, col2 = st.columns(2)
        col1.write(f"Máxima Histórica: ${data['market_data']['ath']['usd']:,.2f}")
        
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
    
def get_latest_4h_analysis():
    """Obtém a análise mais recente do bot 4h do banco de dados"""
    try:
        connection = connect_to_db()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT analysis_datetime, recommended_action, justification,
                       stop_loss, take_profit, attention_points
                FROM bot_4h_analysis
                ORDER BY analysis_datetime DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                return {
                    'datetime': result[0],
                    'action': result[1],
                    'justification': result[2],
                    'stop_loss': result[3],
                    'take_profit': result[4],
                    'attention_points': result[5]
                }
            return None
    except Exception as e:
        print(f"Erro ao obter análise 4h: {e}")
        return None
    finally:
        if connection:
            connection.close()
            
def get_all_4h_analysis():
    """Obtém todas as análises do bot 4h do banco de dados"""
    try:
        connection = connect_to_db()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT analysis_datetime, recommended_action, justification,
                       stop_loss, take_profit, attention_points
                FROM bot_4h_analysis
                ORDER BY analysis_datetime DESC
            """)
            results = cursor.fetchall()
            
            if results:
                analysis_list = []
                for result in results:
                    analysis = {
                        'datetime': result[0],
                        'action': result[1],
                        'justification': result[2],
                        'stop_loss': result[3],
                        'take_profit': result[4],
                        'attention_points': result[5]
                    }
                    analysis_list.append(analysis)
                return analysis_list
            return []
    except Exception as e:
        print(f"Erro ao obter análises 4h: {e}")
        return []
    finally:
        if connection:
            connection.close()

def display_4h_analysis():
    st.header("🤖 Análise Bot 4 Horas")
    
    analysis = get_latest_4h_analysis()
    
    if analysis:
        # Estilização CSS
        st.markdown("""
            <style>
                .analysis-box {
                    padding: 20px;
                    border-radius: 10px;
                    background-color: #f0f2f6;
                    margin-bottom: 20px;
                }
                .timestamp {
                    color: #666;
                    font-size: 0.9em;
                }
                .action-label {
                    font-weight: bold;
                    color: #1e88e5;
                }
            </style>
        """, unsafe_allow_html=True)
        
        # Timestamp da análise
        st.markdown(f"<p class='timestamp'>Última atualização: {analysis['datetime'].strftime('%d/%m/%Y %H:%M:%S UTC')}</p>", 
                   unsafe_allow_html=True)
        
        # Ação Recomendada e Justificativa
        col1, col2, col3 = st.columns([1,1,1])
        
        with col1:
            st.metric("Ação Recomendada", analysis['action'])
        
        with col2:
            st.metric("Stop Loss", f"${analysis['stop_loss']:,.2f}")
            
        with col3:
            st.metric("Take Profit", f"${analysis['take_profit']:,.2f}")
        
        # Justificativa em um box destacado
        st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
        st.markdown("#### 📝 Justificativa")
        st.write(analysis['justification'])
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Pontos de Atenção
        st.markdown("#### 🎯 Pontos de Atenção")
        for point in analysis['attention_points']:
            st.markdown(f"- {point}")
            
    else:
        st.error("Não foi possível carregar a análise mais recente do bot 4h.")

def normalize_btc_value(value):
    """
    Normaliza valores do BTC para diferentes casos.
    Garante que os valores fiquem no range esperado (próximo a 69000).
    """
    if pd.isna(value):
        return None
    
    # Converte para float se for string
    if isinstance(value, str):
        value = float(value.replace(',', ''))
    
    # Se o valor for muito baixo (como 69.20)
    if value < 100:
        return value * 1000
    # Se o valor for muito alto (como 691962)
    elif value > 200000:
        return value / 10
    
    return value

def display_btc_price_signals(btc_data, trade_signals):
    # Pegar dados OHLC do banco
    connection = connect_to_db()
    query = """
    SELECT 
        DATE(datetime) as date,
        btc_open,
        btc_high,
        btc_low,
        btc_close,
        value_btc
    FROM chatbot_data
    WHERE btc_open IS NOT NULL 
    GROUP BY DATE(datetime), btc_open, btc_high, btc_low, btc_close, value_btc
    ORDER BY DATE(datetime)
    """
    candlestick_df = pd.read_sql_query(query, connection)
    connection.close()

    # Normalizar todos os valores
    for col in ['btc_open', 'btc_high', 'btc_low', 'btc_close', 'value_btc']:
        candlestick_df[col] = candlestick_df[col].apply(normalize_btc_value)

    # Converter para DataFrame os dados recebidos
    trade_df = pd.DataFrame(trade_signals)
    
    # Converter datas
    candlestick_df['date'] = pd.to_datetime(candlestick_df['date'])
    trade_df['date'] = pd.to_datetime(trade_df['date'])

    fig = go.Figure()

    # Adicionar candlesticks
    fig.add_trace(go.Candlestick(
        x=candlestick_df['date'],
        open=candlestick_df['btc_open'],
        high=candlestick_df['btc_high'],
        low=candlestick_df['btc_low'],
        close=candlestick_df['btc_close'],
        name='BTC/USD',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a',
        decreasing_fillcolor='#ef5350'
    ))

    # Filtrar apenas mudanças de posição
    position_changes = trade_df[trade_df['position'].shift() != trade_df['position']]
    position_changes = position_changes.merge(
        candlestick_df[['date', 'value_btc']], 
        on='date', 
        how='left'
    )
    
    # Sinais de compra
    buy_signals = position_changes[position_changes['position'] == 'compra']
    if not buy_signals.empty:
        fig.add_trace(go.Scatter(
            x=buy_signals['date'],
            y=buy_signals['value_btc'],
            mode='markers',
            marker=dict(
                symbol='triangle-up',
                size=15,
                color='#00ff9f',
                line=dict(color='#000000', width=1)
            ),
            name='Entrada Compra',
            hovertemplate='Compra<br>$%{y:,.2f}<br>%{x}<extra></extra>'
        ))

    # Sinais de venda
    sell_signals = position_changes[position_changes['position'] == 'venda']
    if not sell_signals.empty:
        fig.add_trace(go.Scatter(
            x=sell_signals['date'],
            y=sell_signals['value_btc'],
            mode='markers',
            marker=dict(
                symbol='triangle-down',
                size=15,
                color='#ff4444',
                line=dict(color='#000000', width=1)
            ),
            name='Entrada Venda',
            hovertemplate='Venda<br>$%{y:,.2f}<br>%{x}<extra></extra>'
        ))

    fig.update_layout(
        plot_bgcolor='#131722',
        paper_bgcolor='#131722',
        title={
            'text': 'Preço Bitcoin com sinais da IA',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(color='#e1e1e1', size=20)
        },
        font=dict(color='#e1e1e1'),
        xaxis=dict(
            gridcolor='#1e222d',
            showgrid=True,
            zeroline=False,
            rangeslider=dict(visible=False),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1d", step="day", stepmode="backward"),
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ]),
                font=dict(color='#e1e1e1'),
                bgcolor='#131722',
                activecolor='#1e222d'
            )
        ),
        yaxis=dict(
            gridcolor='#1e222d',
            showgrid=True,
            zeroline=False,
            tickformat=',.2f',
            title=dict(text='Preço USD', font=dict(color='#e1e1e1')),
            side='right'
        ),
        legend=dict(
            bgcolor='rgba(19,23,34,0.8)',
            bordercolor='#1e222d',
            font=dict(color='#e1e1e1'),
            x=0,
            y=1,
        ),
        hovermode='x unified',
        margin=dict(l=10, r=50, t=40, b=10)
    )

    fig.update_xaxes(
        showspikes=True,
        spikecolor='#e1e1e1',
        spikesnap='cursor',
        spikemode='across',
        spikethickness=1
    )
    fig.update_yaxes(
        showspikes=True,
        spikecolor='#e1e1e1',
        spikesnap='cursor',
        spikethickness=1
    )

    st.plotly_chart(fig, use_container_width=True)

def trading_view_btc_price_signals(trade_signals=None, custom_chart=None):
    """
    Exibe gráfico TradingView
    
    Args:
        custom_chart (str): Código HTML do gráfico personalizado do TradingView
    """
    if custom_chart:
        components.html(custom_chart, height=750)
    else:
        default_chart = """
            <div class="tradingview-widget-container">
                <div id="tradingview_chart"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                    new TradingView.widget({
                        "width": "100%",
                        "height": 700,
                        "symbol": "BINANCE:BTCUSDT",
                        "interval": "D",
                        "timezone": "Etc/UTC",
                        "theme": "dark",
                        "style": "1",
                        "locale": "br",
                        "toolbar_bg": "#131722",
                        "enable_publishing": false,
                        "hide_side_toolbar": false,
                        "allow_symbol_change": true,
                        "details": true,
                        "studies": [
                            "Volume@tv-basicstudies"
                        ],
                        "container_id": "tradingview_chart",
                        "fullscreen": true,
                        "show_popup_button": true
                    });
                </script>
            </div>
        """
        components.html(default_chart, height=750)

def get_trade_summary(df):
    """
    Processa o DataFrame para mostrar um resumo das operações completas e em andamento.
    """
    # Cria uma cópia do DataFrame para não modificar o original
    df = df.copy()
    
    trades = []
    current_trade = None
    entry_price = None
    entry_date = None

    for index, row in df.iterrows():
        if row['Recomendação'] in ['compra', 'venda']:
            if current_trade is None:
                current_trade = row['Recomendação']
                entry_price = row['Preço de Entrada']
                entry_date = row['datetime']

            elif row['Recomendação'] != current_trade:

                exit_price = row['btc_close']
                if current_trade == 'compra':
                    return_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    return_pct = ((entry_price - exit_price) / entry_price) * 100
                

                trades.append({
                    'Data Entrada': entry_date,
                    'Data Saída': row['datetime'],
                    'Tipo': current_trade.capitalize(),
                    'Preço Entrada': entry_price,
                    'Preço Saída': exit_price,
                    'Retorno (%)': round(return_pct, 2),
                    'Status': 'Fechada'
                })

                current_trade = row['Recomendação']
                entry_price = row['Preço de Entrada']
                entry_date = row['datetime']
    

    if current_trade is not None:
        last_price = df['btc_close'].iloc[-1]
        if current_trade == 'compra':
            return_pct = ((last_price - entry_price) / entry_price) * 100
        else:
            return_pct = ((entry_price - last_price) / entry_price) * 100
        
        trades.append({
            'Data Entrada': entry_date,
            'Data Saída': df['datetime'].iloc[-1],
            'Tipo': current_trade.capitalize(),
            'Preço Entrada': entry_price,
            'Preço Saída': last_price,
            'Retorno (%)': round(return_pct, 2),
            'Status': 'Em Andamento'
        })
    
    trades_df = pd.DataFrame(trades)
    
    if not trades_df.empty:
        trades_df['Data Entrada'] = pd.to_datetime(trades_df['Data Entrada']).dt.strftime('%Y-%m-%d %H:%M')
        trades_df['Data Saída'] = pd.to_datetime(trades_df['Data Saída']).dt.strftime('%Y-%m-%d %H:%M')
        trades_df['Preço Entrada'] = trades_df['Preço Entrada'].round(2)
        trades_df['Preço Saída'] = trades_df['Preço Saída'].round(2)
        
        trades_df['Retorno (%)'] = trades_df['Retorno (%)'].apply(
            lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%"
        )
    
    return trades_df

# Uso:
def display_trade_summary(df):
    trades_df = get_trade_summary(df)
    
    # Estiliza o DataFrame
    st.markdown("### Resumo das Operações")
    
    # Calcula estatísticas
    if not trades_df.empty:
        total_trades = len(trades_df)
        closed_trades = len(trades_df[trades_df['Status'] == 'Fechada'])
        returns = pd.to_numeric(trades_df['Retorno (%)'].str.rstrip('%'))
        avg_return = returns.mean()
        
        # Mostra métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Operações", total_trades)
        with col2:
            st.metric("Operações Fechadas", closed_trades)
        with col3:
            st.metric("Retorno Médio", f"{avg_return:.2f}%")
    
    # Mostra a tabela
    st.dataframe(
        trades_df,
        hide_index=True,
        use_container_width=True
    )
    

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    st.sidebar.title("Bem-vindo!")
    
    if not st.session_state.logged_in:
        email = st.sidebar.text_input("Email")
        password = st.sidebar.text_input("Senha", type="password")
        login_button = st.sidebar.button('Login')
        
        st.markdown("""
            <style>
            .centralize { text-align: center; }
            .spacer { margin-bottom: 20px; }
            </style>
            <div class='centralize spacer'>
                <h2>Faça Login na sua conta e aproveite a melhor IA de análise de crypto do MUNDO!</h2>
            </div>
            <div class='centralize'>
                <p>🚀 Não se esqueça de ficar de olho no discord!</p>
            </div>
        """, unsafe_allow_html=True)
        
        if login_button:
            user = verify_login(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.user_name = user[1]
                st.rerun()
            else:
                st.sidebar.error("Credenciais inválidas")
    else:
        if st.sidebar.button('Logout'):
            st.session_state.logged_in = False
            st.experimental_rerun()
        
        st.image("image_btc.jpg", use_column_width=True)
        st.title("📈 GPT Analista de BTC")
        
        st.markdown("""
            <style>
            .main-description {
                font-size: 18px;
                font-weight: 500;
                line-height: 1.6;
            }
            .discord-section {
                background-color: #1e1f22;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }
            .discord-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 15px;
            }
            .discord-logo {
                width: 24px;
                height: 24px;
            }
            .discord-button {
                display: inline-flex;
                align-items: center;
                padding: 8px 16px;
                background-color: #5865F2;
                color: white !important;
                text-decoration: none;
                border-radius: 3px;
                font-size: 14px;
                font-weight: 500;
                transition: background-color 0.2s;
            }
            .discord-button:hover {
                background-color: #4752C4;
            }
            </style>
            
            <div class="main-description">
                Um chatbot inteligente especializado em análise de Bitcoin para operações de swing trading.
                Ele utiliza dados em tempo real de derivativos, on-chain, análise técnica e macroeconômica para fornecer previsões dinâmicas e recomendações ajustadas conforme as condições do mercado.
            </div>
            
            <div class="discord-section">
                <div class="discord-header">
                    <svg class="discord-logo" viewBox="0 0 71 55" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M60.1045 4.8978C55.5792 2.8214 50.7265 1.2916 45.6527 0.41542C45.5603 0.39851 45.468 0.440769 45.4204 0.525289C44.7963 1.6353 44.105 3.0834 43.6209 4.2216C38.1637 3.4046 32.7345 3.4046 27.3892 4.2216C26.905 3.0581 26.1886 1.6353 25.5617 0.525289C25.5141 0.443589 25.4218 0.40133 25.3294 0.41542C20.2584 1.2888 15.4057 2.8186 10.8776 4.8978C10.8384 4.9147 10.8048 4.9429 10.7825 4.9795C1.57795 18.7309 -0.943561 32.1443 0.293408 45.3914C0.299005 45.4562 0.335386 45.5182 0.385761 45.5576C6.45866 50.0174 12.3413 52.7249 18.1147 54.5195C18.2071 54.5477 18.305 54.5139 18.3638 54.4378C19.7295 52.5728 20.9469 50.6063 21.9907 48.5383C22.0523 48.4172 21.9935 48.2735 21.8676 48.2256C19.9366 47.4931 18.0979 46.6 16.3292 45.5858C16.1893 45.5041 16.1781 45.304 16.3068 45.2082C16.679 44.9293 17.0513 44.6391 17.4067 44.3461C17.471 44.2926 17.5606 44.2813 17.6362 44.3151C29.2558 49.6202 41.8354 49.6202 53.3179 44.3151C53.3935 44.2785 53.4831 44.2898 53.5502 44.3433C53.9057 44.6363 54.2779 44.9293 54.6529 45.2082C54.7816 45.304 54.7732 45.5041 54.6333 45.5858C52.8646 46.6197 51.0259 47.4931 49.0921 48.2228C48.9662 48.2707 48.9102 48.4172 48.9718 48.5383C50.038 50.6034 51.2554 52.5699 52.5959 54.435C52.6519 54.5139 52.7526 54.5477 52.845 54.5195C58.6464 52.7249 64.529 50.0174 70.6019 45.5576C70.6551 45.5182 70.6887 45.459 70.6943 45.3942C72.1747 30.0791 68.2147 16.7757 60.1968 4.9823C60.1772 4.9429 60.1437 4.9147 60.1045 4.8978Z" fill="white"/>
                    </svg>
                    <h2 style="color: white; margin: 0;">Comunidade Discord</h2>
                </div>
                <p style="color: #B9BBBE; margin-bottom: 20px;">Entre no nosso servidor do Discord para receber atualizações em tempo real!</p>
                <a href="https://discord.gg/uQFb4Az8us" target="_blank" class="discord-button">
                    Entrar no Discord
                </a>
            </div>
        """, unsafe_allow_html=True)
        
        bitcoin_data = get_bitcoin_data(30)

        st.write("## Dados do Bitcoin")
        if bitcoin_data is not None:
            display_bitcoin_data()
        else:
            st.error("Dados do Bitcoin não disponíveis no momento.")

        display_next_updates()

        df_returns = calculate_trade_returns()
        ai_returns = plot_cumulative_returns(df_returns)
        btc_returns = calculate_btc_cumulative_return()
        fig = display_comparison_graph(ai_returns, btc_returns)
        st.plotly_chart(fig, use_container_width=True)
        display_btc_price_signals(btc_data=btc_returns, trade_signals=df_returns)
        trading_view_btc_price_signals()

        st.header("Última Análise GPT")
        gpt_analysis = get_gpt_analysis()

        if gpt_analysis is not None:
            st.text(f"Última análise realizada em: {gpt_analysis['datetime']}")
    
            col1, col2, col3 = st.columns(3)
            col1.metric("Recomendação", gpt_analysis['recommendation'].strip())
            col2.metric("Taxa de Confiança", f"{gpt_analysis['trust_rate']:.2f}%")
            col3.metric("Valor de Entrada", f"${gpt_analysis['value_btc']:.2f}")
    
            col4, col5, col6 = st.columns(3)
            col4.metric("Stop Loss", f"{gpt_analysis['stop_loss']:.2f}")
            col5.metric("Take Profit", f"{gpt_analysis['take_profit']:.2f}")
            col6.metric("Retorno de Risco", gpt_analysis['risk_return'])
    
            response_content = gpt_analysis['response']
            st.chat_message("ai").write(response_content)
            risk_return_parts = gpt_analysis['risk_return'].split(':')
        else:
            st.write("Nenhuma análise disponível com todos os dados necessários.")

        display_4h_analysis()
        st.write('## Histórico de recomendações BOT intradiário')
        df_4h = get_all_4h_analysis()
        st.dataframe(df_4h, height=400)
        
        st.write("Tabela com histórico")
        df = get_bitcoin_data_from_db()
        display_trade_summary(df)
        
        st.write('## Histórico de Operações')
        st.dataframe(df, height=200)
        
        if 'update_counter' not in st.session_state:
            st.session_state.update_counter = 0

        st.session_state.update_counter += 1

        if st.session_state.update_counter >= 60:
            st.session_state.update_counter = 0
            st.rerun()

        st.empty().text(f"Próxima atualização em {60 - st.session_state.update_counter} segundos")

if __name__ == "__main__":
    main()