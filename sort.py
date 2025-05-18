import numpy as np
from scipy.optimize import linear_sum_assignment

class KalmanFilter:
    def __init__(self, bbox):
        self.bbox = bbox
        self.id = None
        self.age = 0

class Sort:
    def __init__(self):
        self.trackers = []
        self.frame_count = 0
        self.next_id = 1

    def update(self, detections):
        self.frame_count += 1

        # Se não houver detecções, envelhecer os rastreadores existentes
        if len(detections) == 0:
            return np.empty((0, 5))

        # Atualizar os rastreadores existentes
        for tracker in self.trackers:
            tracker.age += 1

        # Criar novos rastreadores para detecções novas
        new_trackers = []
        for det in detections:
            tracker = KalmanFilter(det)
            tracker.id = self.next_id
            self.next_id += 1
            new_trackers.append(tracker)

        self.trackers = new_trackers
        return np.array([[t.bbox[0], t.bbox[1], t.bbox[2], t.bbox[3], t.id] for t in self.trackers])
