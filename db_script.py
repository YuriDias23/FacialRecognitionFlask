import sqlite3
import json
from deepface import DeepFace
import os

# Escolha o modelo de embeddings
MODEL_NAME = "ArcFace"  # Você pode usar "ArcFace", "Facenet", etc.

# Função para inicializar o banco de dados
def init_db():
    conn = sqlite3.connect("face_database.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            image_path TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Função para adicionar uma imagem de rosto ao banco de dados
def add_face_to_db(name, image_path):
    try:
        # Gera o embedding da imagem
        embedding = DeepFace.represent(img_path=image_path, model_name=MODEL_NAME, enforce_detection=False)[0]["embedding"]
        embedding_str = json.dumps(embedding)  # Converte para string JSON

        # Salva o nome, o caminho da imagem e embedding no banco de dados
        conn = sqlite3.connect("face_database.db")
        c = conn.cursor()
        c.execute("INSERT INTO faces (name, image_path, embedding) VALUES (?, ?, ?)", (name, image_path, embedding_str))
        conn.commit()
        conn.close()
        print(f"Rosto de {name} adicionado ao banco de dados com sucesso.")
        
    except Exception as e:
        print(f"Erro ao processar a imagem {image_path}: {e}")

# Inicialize o banco de dados
init_db()


