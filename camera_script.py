import cv2
from deepface import DeepFace
import sqlite3
import json
import numpy as np
import time
import sys
from threading import Lock
from shared import frame_queues, buffer_lock, active_streams, frame_queue_lock
import os
from queue import Queue
from mtcnn import MTCNN  # Mantendo o MTCNN

# Configurações e constantes
MODEL_NAME = "ArcFace"
THRESHOLD = 0.7
CHECK_INTERVAL = 3
FRAME_CHECK_INTERVAL = 3
MAX_RETRIES = 5
RETRY_DELAY = 5
DB_PATH = r"your-db-local"
DEEPFACE_THRESHOLD = 0.9
CACHE_EXPIRATION = 5  # Tempo de cache em segundos

# Cache para evitar reprocessamento de rostos recentes
face_cache = {}

# Função para carregar os embeddings do banco de dados
def load_embeddings_from_db():
    print("[INFO] Carregando embeddings do banco de dados...")
    conn = sqlite3.connect("face_database.db")
    c = conn.cursor()
    c.execute("SELECT name, embedding FROM faces")
    rows = c.fetchall()
    conn.close()
    face_database = []
    for name, embedding_str in rows:
        if embedding_str:
            try:
                embedding = np.array(json.loads(embedding_str))
                face_database.append((name, embedding))
                print(f"[INFO] Embedding carregado para {name}.")
            except json.JSONDecodeError as e:
                print(f"[ERROR] Falha ao decodificar embedding para {name}: {e}")
        else:
            print(f"[WARNING] Embedding vazio para {name}. Entrada ignorada.")
    print("[INFO] Embeddings carregados com sucesso.")
    return face_database

# Função para salvar a detecção recente no arquivo JSON
def save_identification(name):
    data = {"name": name, "timestamp": time.time()}
    with open("recent_detections.json", "a") as file:
        json.dump(data, file)
        file.write("\n")

# Função para processar rosto sem salvar no disco
def process_face(face_cropped):
    try:
        # Converte a imagem para bytes e depois para array NumPy
        _, img_encoded = cv2.imencode(".jpg", face_cropped)
        img_bytes = img_encoded.tobytes()
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)  # Decodifica a imagem

        # Chama o DeepFace.find()
        results = DeepFace.find(
            img_path=img,
            db_path=DB_PATH,
            model_name=MODEL_NAME,
            enforce_detection=False,
            distance_metric="cosine",
            threshold=DEEPFACE_THRESHOLD
        )

        # Verifica se o retorno é válido
        if isinstance(results, list) and len(results) > 0:
            result_df = results[0]
            if not result_df.empty and "identity" in result_df.columns:
                best_match = result_df.iloc[0]
                detected_name = os.path.basename(best_match["identity"])
                return detected_name  # Retorna apenas o nome identificado
            else:
                print("[WARNING] DeepFace retornou um DataFrame sem 'identity'.")
                return "Desconhecido"
        else:
            print("[INFO] Nenhum rosto detectado pelo DeepFace.")
            return "Desconhecido"
    except Exception as e:
        print(f"[ERROR] Erro ao processar face: {e}")
        return "Erro"

# Função para conectar ao stream RTSP com tentativas de reconexão
def connect_to_rtsp(url, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    for attempt in range(max_retries):
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            print("[INFO] Conectado ao stream RTSP.")
            return cap
        else:
            print(f"[WARNING] Tentativa {attempt + 1}/{max_retries} falhou. Retentando em {retry_delay} segundos...")
            time.sleep(retry_delay)
    print("[ERROR] Falha ao conectar ao stream RTSP após várias tentativas.")
    return None

# Função principal para capturar e processar os frames
def generate_frames(rtsp_url, camera_id):
    cap = connect_to_rtsp(rtsp_url)
    if not cap:
        print("[ERROR] Não foi possível estabelecer conexão com o stream RTSP.")
        return

    print(f"[INFO] Iniciando captura de vídeo para câmera {camera_id}.")
    last_frame_check = time.time()
    face_display_cache = {}
    stop_event = active_streams[camera_id]["stop_event"]

    # Inicializa o detector MTCNN
    detector = MTCNN()

    while cap.isOpened() and not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Falha ao capturar quadro. Tentando reconectar...")
            cap.release()
            cap = connect_to_rtsp(rtsp_url)
            if not cap:
                break
            continue

        current_time = time.time()
        if current_time - last_frame_check >= FRAME_CHECK_INTERVAL:
            face_display_cache.clear()
            faces = detector.detect_faces(frame)

            print(f"[INFO] {len(faces)} rosto(s) detectado(s) para câmera {camera_id}.")
            last_frame_check = current_time

            for face in faces:
                try:
                    x, y, w, h = face['box']
                    face_cropped = frame[y:y+h, x:x+w]

                    # Verifica se já processamos esse rosto recentemente
                    if (x, y, w, h) in face_cache and (time.time() - face_cache[(x, y, w, h)]["timestamp"]) < CACHE_EXPIRATION:
                        detected_name = face_cache[(x, y, w, h)]["name"]
                    else:
                        # Processa a imagem diretamente na memória
                        detected_name = process_face(face_cropped)
                        face_cache[(x, y, w, h)] = {"name": detected_name, "timestamp": time.time()}  # Atualiza cache

                    print(f"[INFO] Nome identificado: {detected_name}")
                    if detected_name != "Desconhecido":
                        save_identification(detected_name)

                    face_display_cache[(x, y, w, h)] = {"name": detected_name, "coords": (x, y, w, h)}
                except Exception as e:
                    print(f"[ERROR] Erro ao processar rosto: {e}")
                    face_display_cache[(x, y, w, h)] = {"name": "Erro", "coords": (x, y, w, h)}

        # Desenha retângulos e nomes no frame
        for face_id, info in face_display_cache.items():
            (x, y, w, h) = info["coords"]
            detected_name = info["name"]
            color = (0, 255, 0) if detected_name != "Desconhecido" else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.putText(frame, detected_name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Codifica o frame e insere na fila
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            with frame_queue_lock:
                if camera_id in frame_queues:
                    if frame_queues[camera_id].full():
                        discarded_frame = frame_queues[camera_id].get_nowait()
                        print(f"[WARNING] Frame descartado para câmera {camera_id}.")
                    frame_queues[camera_id].put(buffer.tobytes(), timeout=0.1)
                else:
                    print(f"[INFO] Streaming finalizado, fila removida para câmera {camera_id}.")
                    break
        else:
            print(f"[ERROR] Falha ao codificar frame para câmera {camera_id}.")

    cap.release()
    print(f"[INFO] Streaming finalizado para câmera {camera_id}.")
