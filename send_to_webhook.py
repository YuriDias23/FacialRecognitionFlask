import json
import time
import os
import requests

# URL do webhook
#WEBHOOK_URL = "http://192.168.88.158:90/api/webhook/facialteste"  # Substitua pelo seu webhook real

# Intervalo de envio para o webhook (em segundos)
SEND_INTERVAL = 5
LAST_SEND_TIME = 0
delay = 10  # Variável para configurar delay entre envios e detecções

def load_recent_detections():
    """Lê as identificações recentes do arquivo JSON e limpa o arquivo."""
    if not os.path.exists("recent_detections.json"):
        return []

    detections = []
    with open("recent_detections.json", "r") as file:
        for line in file:
            try:
                detection = json.loads(line)
                detections.append(detection)
            except json.JSONDecodeError:
                continue
    
    # Limpa o arquivo após a leitura
    open("recent_detections.json", "w").close()
    return detections

def send_to_webhook(detections, webhook_url):
    """Envia os dados das identificações ao webhook."""
    payload = {"identified_names": [d["name"] for d in detections]}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print("Dados enviados ao webhook:", payload)
    except requests.exceptions.RequestException as e:
        print("Erro ao enviar ao webhook:", e)

def monitor_detections(webhook_url):
    """Monitora o arquivo de detecções e envia ao webhook em intervalos definidos."""
    global LAST_SEND_TIME
    print("[INFO] Iniciando monitoramento de detecções...")
    while True:
        # Verifica se o intervalo de envio foi atingido
        current_time = time.time()
        if current_time - LAST_SEND_TIME >= SEND_INTERVAL:
            # Carrega as detecções e envia se houver novas detecções
            detections = load_recent_detections()
            if detections:
                time.sleep(5)
                send_to_webhook(detections, webhook_url)
                LAST_SEND_TIME = current_time
        time.sleep(1)  # Aguarda um segundo antes de verificar novamente

if __name__ == "__main__":
    try:
        monitor_detections()
    except KeyboardInterrupt:
        print("\n[INFO] Monitoramento encerrado pelo usuário.")
