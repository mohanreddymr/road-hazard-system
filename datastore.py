import threading

class DataStore:
    """Thread‑safe container for the shared ADAS data.

    The original implementation used a global dict ``latest_data`` protected by a
    ``threading.Lock``.  This class encapsulates that pattern and provides a clean
    API for ``update`` and ``get`` operations.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            "status": "NORMAL",
            "motor_speed": 100,
            "confidence": "97.0%",
            "imu_z": 1.0,
            "motion_score": 0.05,
            "vert_disp": 0.0,
            "imu_spike": False,
            "camera_high": False,
            "readings": 0,
            "hazards": 0,
            "cautions": 0,
            "normals": 0,
            "session_time": "00:00:00",
        }

    def update(self, new_data: dict):
        """Merge ``new_data`` into the internal store in a thread‑safe way."""
        with self._lock:
            self._data.update(new_data)

    def get(self) -> dict:
        """Return a shallow copy of the current data snapshot."""
        with self._lock:
            return dict(self._data)
