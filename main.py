import subprocess
import sys
import os
import time
import signal
import psutil
from datetime import datetime, timedelta, timezone

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
    return subprocess.Popen([sys.executable, "task_server.py"])

def run_streamlit_app():
    print("Iniciando o aplicativo Streamlit...")
    return subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"])

def run_fastapi_server():
    print("Iniciando o servidor FastAPI na porta 8001...")
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"])

def terminate_process(process):
    if process and process.poll() is None:
        print(f"Terminando processo {process.pid}")
        try:
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            process.wait(timeout=10)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            pass

def signal_handler(signum, frame):
    print("Sinal de interrupção recebido. Iniciando o desligamento gracioso...")
    create_stop_file()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    remove_stop_file()

    processes = [
        run_task_server(),
        run_streamlit_app(),
        run_fastapi_server()
    ]

    print("Todos os processos foram iniciados. Para interromper, use SIGTERM ou crie o arquivo /tmp/stop_gpt_btc_analyzer")

    try:
        while not should_stop():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupção de teclado recebida.")
    finally:
        print("Iniciando processo de desligamento...")
        for process in processes:
            terminate_process(process)
        remove_stop_file()