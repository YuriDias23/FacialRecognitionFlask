from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
import os
import sqlite3
from werkzeug.utils import secure_filename
from db_script import add_face_to_db
from camera_script import generate_frames
from send_to_webhook import monitor_detections
import subprocess
import threading
import sys
import cv2
from threading import Lock, Event
from threading import Thread
from shared import frame_queues, active_streams
import time
from queue import Queue



buffer_lock = Lock()
app = Flask(__name__)
app.secret_key = 'supersecretkey'

rtsp_url = None
frame_queue_lock = Lock()

# Configuração das pastas de upload
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Variáveis de controle para processos
streaming_process = None

webhook_process = None

streaming_thread = None

# Variáveis de controle de streaming
streaming = False

# Configuração do banco de dados
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    filename TEXT
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    username TEXT,
                    password TEXT,
                    url TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS webhook (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT
                )''')
    
    conn.commit()
    conn.close()

init_db()

# Função para iniciar o streaming e o webhook
'''def start_processes(rtsp_url):
    global streaming_process, webhook_process

    # Iniciar o processo de streaming
    if streaming_process is None:
        streaming_process = subprocess.Popen([sys.executable, "camera_script.py", rtsp_url])
        print("[INFO] Processo de streaming iniciado.")

    # Iniciar o processo de webhook
    if webhook_process is None:
        webhook_process = subprocess.Popen([sys.executable, "send_to_webhook.py"])
        print("[INFO] Processo de webhook iniciado.")'''

# Função para parar os processos de streaming e webhook
'''def stop_processes():
    global streaming_process, webhook_process

    if streaming_process:
        streaming_process.terminate()
        streaming_process = None
        print("[INFO] Processo de streaming interrompido.")

    if webhook_process:
        webhook_process.terminate()
        webhook_process = None
        print("[INFO] Processo de webhook interrompido.")
'''
# Rota para iniciar o streaming
# Rota para exibir a página de cadastro
# Função para salvar dados no banco de dados
def save_to_database(table, data):
    conn = sqlite3.connect("database.db")  # Substitua pelo nome do seu banco
    c = conn.cursor()

    if table == "cameras":
        c.execute("INSERT INTO cameras (name, username, password, url) VALUES (?, ?, ?, ?)", data)
    elif table == "webhook":
        c.execute("INSERT INTO webhook (name, url) VALUES (?, ?)", data)

    conn.commit()
    conn.close()

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        form_type = request.form.get("form_type")  # Identifica o formulário (câmera ou webhook)

        if form_type == "camera":
            name = request.form['camera_name']
            username = request.form['camera_username']
            password = request.form['camera_password']
            url = request.form['camera_url']
            save_to_database("cameras", (name, username, password, url))
            flash("Câmera cadastrada com sucesso!")

        elif form_type == "webhook":
            name = request.form['webhook_name']
            url = request.form['webhook_url']
            save_to_database("webhook", (name, url))
            flash("Webhook cadastrado com sucesso!")

        return redirect(url_for('config'))
 # Consulta os dados do banco de dados para câmeras e webhooks
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM cameras")
    cameras = c.fetchall()
    c.execute("SELECT id, name FROM webhook")
    webhooks = c.fetchall()
    conn.close()

    # Renderiza o template com os dados
    return render_template('config.html', cameras=cameras, webhooks=webhooks)

# @app.route('/start_stream', methods=['POST'])
# def start_stream():
#     global active_streams

#     # Obtém os valores do formulário
#     rtsp_url = request.form.get("rtsp_url")
#     camera_id = int(request.form.get("camera_id"))

#     if not rtsp_url or not camera_id:
#         flash("Erro: URL RTSP ou ID da câmera não fornecido.")
#         return redirect(url_for('stream'))

#     # Verifica se o stream já está ativo
#     if camera_id in active_streams and active_streams[camera_id]["thread"].is_alive():
#         flash(f"Streaming já está ativo para a câmera {camera_id}.")
#         return redirect(url_for('stream'))

#     # Configura o evento de parada e a thread
#     stop_event = threading.Event()
#     streaming_thread = threading.Thread(
#         target=start_streaming,
#         args=(rtsp_url, None, camera_id),  # None para webhook_url
#         daemon=True
#     )
#     streaming_thread.start()

#     # Adiciona o stream ao dicionário ativo
#     active_streams[camera_id] = {
#         "camera_name": f"Câmera {camera_id}",
#         "rtsp_url": rtsp_url,
#         "webhook_url": None,  # Pode ser configurado posteriormente
#         "stop_event": stop_event,
#         "thread": [streaming_thread]
#     }

#     flash(f"Streaming iniciado para a câmera {camera_id}.")
#     print(f"[INFO] Streaming iniciado para câmera {camera_id}.")
#     return redirect(url_for('stream'))

# Rota para iniciar o webhook

@app.route('/start_webhook', methods=['POST'])
def start_webhook():
    webhook_url = request.json.get("webhook_url")

    threading.Thread(target=monitor_detections, args=(webhook_url,), daemon=True).start()
    return {'status': 'Webhook iniciado com sucesso'}

# Rota para upload de fotos
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Adiciona a imagem ao banco de dados de reconhecimento facial
            add_face_to_db(filename, file_path)
            flash(f'Imagem {filename} adicionada ao banco de dados.')
            return redirect(url_for('upload'))
    
    # Consulta todas as fotos no banco para exibição
    conn = sqlite3.connect('face_database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM faces")
    photos = c.fetchall()
    conn.close()

    return render_template('upload.html', photos=photos)

# Rota para excluir fotos
@app.route('/delete/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    # Remove do banco de dados e sistema de arquivos
    conn = sqlite3.connect('face_database.db')
    c = conn.cursor()

    # Obtém o caminho da imagem a ser excluída
    c.execute("SELECT image_path FROM faces WHERE id = ?", (photo_id,))
    result = c.fetchone()
    
    if result:
        image_path = result[0]

        # Remove o arquivo de imagem se ele existir
        if os.path.exists(image_path):
            os.remove(image_path)
            print(f"Imagem {image_path} removida com sucesso.")
        
        # Exclui o registro do banco de dados
        c.execute("DELETE FROM faces WHERE id = ?", (photo_id,))
        conn.commit()
        print(f"Registro com ID {photo_id} excluído com sucesso.")

    conn.close()
    flash("Foto excluída com sucesso.")
    return redirect(url_for('upload'))

#Editar registro de DB da página CONFIG
@app.route('/edit', methods=['POST'])
def edit_record():
    record_type = request.form.get("type")  # 'camera' ou 'webhook'
    record_id = request.form.get("id")
    name = request.form.get("name")
    url = request.form.get("url")
    username = request.form.get("username", None)  # Somente para câmeras
    password = request.form.get("password", None)  # Somente para câmeras
    
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if record_type == "camera":
        c.execute("UPDATE cameras SET name = ?, username = ?, password = ?, url = ? WHERE id = ?",
                  (name, username, password, url, record_id))
    elif record_type == "webhook":
        c.execute("UPDATE webhook SET name = ?, url = ? WHERE id = ?", (name, url, record_id))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Registro atualizado com sucesso."})

#Deletar registro de DB na pagina CONFIG
@app.route('/delete', methods=['POST'])
def delete_record():
    record_type = request.form.get("type")  # 'camera' ou 'webhook'
    record_id = request.form.get("id")
    
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    
    if record_type == "camera":
        c.execute("DELETE FROM cameras WHERE id = ?", (record_id,))
    elif record_type == "webhook":
        c.execute("DELETE FROM webhook WHERE id = ?", (record_id,))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Registro excluído com sucesso."})

@app.route('/stream', methods=['GET', 'POST'])
def stream():
    global active_streams
    if request.method == 'POST':
        try:
            # Obtém os valores do formulário
            camera_id = request.form.get("camera_id")
            webhook_id = request.form.get("webhook_id")

            if not camera_id or not webhook_id:
                flash("Erro: Câmera ou Webhook não selecionados.")
                return redirect(url_for('stream'))

            # Converte os IDs para int, se necessário
            camera_id = int(camera_id)
            webhook_id = int(webhook_id)

            # Conecta ao banco de dados para obter informações da câmera e do webhook
            conn = sqlite3.connect("database.db")
            c = conn.cursor()
            c.execute("SELECT username, password, url FROM cameras WHERE id = ?", (camera_id,))
            camera = c.fetchone()
            c.execute("SELECT url FROM webhook WHERE id = ?", (webhook_id,))
            webhook = c.fetchone()
            conn.close()

            if not camera:
                flash(f"Erro: Câmera com ID {camera_id} não encontrada.")
                return redirect(url_for('stream'))

            if not webhook:
                flash(f"Erro: Webhook com ID {webhook_id} não encontrado.")
                return redirect(url_for('stream'))

            # Extrai os dados da câmera e do webhook
            username, password, base_url = camera
            rtsp_url = f"rtsp://{username}:{password}@{base_url}"
            webhook_url = webhook[0]

            # Chama a função centralizada para iniciar o streaming
            success = start_streaming(rtsp_url, webhook_url, camera_id)
            if success:
                flash(f"Streaming iniciado para {camera[0]}.")
            else:
                flash(f"Erro: Streaming já está ativo para a câmera {camera_id}.")
        except Exception as e:
            print(f"[ERROR] Falha ao iniciar streaming: {e}")
            flash("Erro ao iniciar o streaming. Verifique os logs para mais detalhes.")

        return redirect(url_for('stream'))

    # Para o método GET, renderiza a página com os streams ativos
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT id, name FROM cameras")
        cameras = c.fetchall()
        c.execute("SELECT id, name FROM webhook")
        webhooks = c.fetchall()
        conn.close()

        return render_template('stream.html', cameras=cameras, webhooks=webhooks, active_streams=active_streams)

    except Exception as e:
        print(f"[ERROR] Falha ao carregar dados do banco: {e}")
        flash("Erro ao carregar as informações do banco de dados.")
        return render_template('stream.html', cameras=[], webhooks=[], active_streams=active_streams)


def start_streaming(rtsp_url, webhook_url, camera_id):
    """Inicia o streaming para uma câmera específica."""
    global active_streams

    # Verifica se o streaming já está ativo
    if camera_id in active_streams and active_streams[camera_id]["thread"][0].is_alive():
        print(f"[INFO] Streaming já ativo para câmera {camera_id}.")
        return False

    try:
        # Garante que a fila de frames está associada corretamente ao camera_id
        with frame_queue_lock:
            if camera_id not in frame_queues:
                frame_queues[camera_id] = Queue(maxsize=2)
                print(f"[INFO] Fila criada para câmera {camera_id}")

        # Inicializa a thread de streaming
        stop_event = threading.Event()
        streaming_thread = threading.Thread(
            target=generate_frames, args=(rtsp_url, camera_id), daemon=True
        )
        streaming_thread.start()

        # Inicializa a thread de monitoramento de detecção facial
        monitoring_thread = threading.Thread(
            target=monitor_detections, args=(webhook_url,), daemon=True
        )
        monitoring_thread.start()

        # Atualiza o dicionário de streams ativos
        active_streams[camera_id] = {
            "camera_name": f"Câmera {camera_id}",
            "rtsp_url": rtsp_url,
            "webhook_url": webhook_url,
            "stop_event": stop_event,
            "threads": [streaming_thread, monitoring_thread],
        }

        print(f"[INFO] Streaming iniciado para câmera {camera_id}.")
        return True

    except Exception as e:
        print(f"[ERROR] Falha ao iniciar streaming para câmera {camera_id}: {e}")
        return False
    
@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    camera_id = request.form.get("camera_id")
    if not camera_id:
        print("[ERROR] Nenhum camera_id fornecido.")
        flash("Erro: Nenhuma câmera foi especificada.")
        return redirect(url_for('stream'))

    camera_id = int(camera_id)
    print(f"[DEBUG] Recebido stop_stream para camera_id: {camera_id}")
    print(f"[DEBUG] Streams ativos: {list(active_streams.keys())}")

    if camera_id in active_streams:
        stream_data = active_streams[camera_id]
        threads = stream_data["threads"]
        stop_event = stream_data.get("stop_event")

        if not stop_event:
            print(f"[ERROR] stop_event é None para câmera {camera_id}.")
            flash(f"Erro: Evento de parada não configurado para câmera {camera_id}.")
            return redirect(url_for('stream'))

        # Sinaliza o evento de parada
        stop_event.set()
        # Aguarda a finalização de todas as threads
        for thread in threads:
            if not isinstance(thread, threading.Thread):
                print(f"[ERROR] Thread inválida encontrada para câmera {camera_id}: {thread}")
                continue  # Pule para a próxima thread
            if thread.is_alive():
                thread.join(timeout=2)
                print(f"[DEBUG] Thread finalizada: {thread}")
            else:
                print(f"[DEBUG] Thread já estava finalizada: {thread}")

        # Remove a fila de frames
        with frame_queue_lock:
            if camera_id in frame_queues:
                del frame_queues[camera_id]
                print(f"[INFO] Fila removida para câmera {camera_id}")
            else:
                print(f"[WARNING] Tentativa de remover fila inexistente para câmera {camera_id}")

        # Remove a entrada do dicionário active_streams
        del active_streams[camera_id]

        print(f"[INFO] Streaming da câmera {camera_id} interrompido com sucesso.")
        flash(f"Streaming da câmera {camera_id} interrompido com sucesso.")
    else:
        print(f"[ERROR] Streaming não encontrado para câmera {camera_id}.")
        flash(f"Erro: Streaming não encontrado para câmera {camera_id}.")

    return redirect(url_for('stream'))

@app.route('/stream_status', methods=['GET'])
def stream_status():
    """Retorna o status atual do streaming."""
    global streaming_process  # Verifica se o processo do streaming ainda está ativo
    if streaming_process is not None and streaming_process.poll() is None:
        return {'status': 'running', 'video_feed': '/video_feed'}
    return {'status': 'stopped'}


@app.route('/video_feed')
def video_feed():
    """Gera frames do streaming para uma câmera específica."""
    camera_id = request.args.get("camera_id")
    if not camera_id or int(camera_id) not in frame_queues:
        print(f"[ERROR] Streaming não encontrado para câmera {camera_id}.")
        return "Streaming não encontrado", 404

    camera_id = int(camera_id)
    frame_queue = frame_queues[camera_id]

    def generate():
        while True:
            # Verifica se a fila ainda existe e o streaming está ativo
            if camera_id not in frame_queues:
                print(f"[INFO] Streaming finalizado para câmera {camera_id}. Interrompendo feed de vídeo.")
                break

            try:
                # Consome frame da fila
                frame = frame_queue.get(timeout=1)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception as e:
                print(f"[WARNING] Erro ao consumir frame para câmera {camera_id}: {e}")
                time.sleep(0.5)  # Evita loops excessivos

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


# Sua rota de visualização principal
# Rota para a página inicial
@app.route('/')
def default_page():
    return render_template('home.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

if __name__ == '__main__':
    # Inicia o aplicativo Flask
    app.run(debug=True)
