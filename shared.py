from multiprocessing import Lock
from queue import Queue

active_streams = {}
# Dicionário de filas para armazenar os frames por câmera
frame_queues = {}
buffer_lock = Lock()  # Lock para sincronização (opcional)
frame_queue_lock = Lock()
