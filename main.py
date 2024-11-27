import subprocess
import sys
import os
import time
import signal
import psutil
from datetime import datetime, timedelta, timezone
from task_server import run_conversation

STOP_FILE = '/tmp/stop_gpt_btc_analyzer'

def create_stop_file():
    with open(STOP_FILE, 'w') as f:
        f.write('stop')

def remove_stop_file():
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

def should_stop():
    return os.path.exists(STOP_FILE)

def run_task_server():
    print("Iniciando o servidor de tarefas...")
    while not should_stop():
        process = subprocess.Popen([sys.executable, "task_server.py"])
        process.wait()
        if not should_stop():
            print("Task server parou inesperadamente. Reiniciando em 5 segundos...")
            time.sleep(5)
    return process

def run_streamlit_app():
    print("Iniciando o aplicativo Streamlit...")
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"])

def run_fastapi_server():
    print("Iniciando o servidor FastAPI na porta 8001...")
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"])

def terminate_process(process):
    if process.poll() is None:
        print(f"Terminando processo {process.pid}")
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        process.wait(timeout=10)

def signal_handler(signum, frame):
    print("Sinal de interrupção recebido. Iniciando o desligamento gracioso...")
    create_stop_file()

if __name__ == "__main__":

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    remove_stop_file()

    task_server_process = run_task_server()
    time.sleep(5)
    streamlit_process = run_streamlit_app()
    fastapi_process = run_fastapi_server()

    print("Todos os processos foram iniciados. Para interromper, use SIGTERM ou crie o arquivo /tmp/stop_gpt_btc_analyzer")

    try:
        while not should_stop():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupção de teclado recebida.")
    finally:
        print("Iniciando processo de desligamento...")
        terminate_process(streamlit_process)
        terminate_process(task_server_process)
        terminate_process(fastapi_process)
        remove_stop_file()
