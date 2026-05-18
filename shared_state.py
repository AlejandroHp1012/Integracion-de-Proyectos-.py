"""
shared_state.py — Bus de datos compartido entre módulos
=======================================================
Despegue escribe aquí → Recuperación (y otros módulos) leen aquí.

Funciona tanto en modo simulación como con ESP32 real:
  - Simulación: los valores se actualizan desde los loops de cada módulo
  - ESP32 real: cuando llegan datos por serial, se parsean y se escriben aquí
    y automáticamente aparecen en todas las pantallas que los leen.
"""
import threading

_lock = threading.Lock()

# ── Estado general del sistema ─────────────────────────────────────
_state = {
    # -- Despegue --------------------------------------------------
    "system_on":        False,
    "rocket_connected": False,
    "signal_verified":  False,
    "link_confirmed":   False,
    "launch_active":    False,
    "launch_state":     "STANDBY",   # STANDBY / ACTIVO / ARMADO / LANZAMIENTO / ABORTADO

    # -- Señal / comunicación --------------------------------------
    "wifi_strength":    0,       # 0-100 %
    "signal_quality":   0,       # 0-100 %

    # -- Condiciones ambientales -----------------------------------
    "wind_speed":       0.0,     # km/h

    # -- Telemetría del cohete (comunes) ---------------------------
    "altitud":          0.0,     # metros
    "velocidad":        0.0,     # m/s
    "latitud":          22.16100,
    "longitud":         -102.26877,
    "distancia":        0.0,  # metros desde base
    "bateria":          85.0,    # %
    "hora_gps":         "--:--:--",

    # -- Subsistemas -----------------------------------------------
    "bateria_cohete":   "N/A",
    "gps_estado":       "N/A",
    "giroscopio":       "N/A",
    "altimetro":        "N/A",
    "propulsion":       "N/A",
    "telemetria":       "N/A",
}


def get(key, default=None):
    """Lee un valor del bus."""
    with _lock:
        return _state.get(key, default)


def set(key, value):
    """Escribe un valor en el bus (thread-safe)."""
    with _lock:
        _state[key] = value


def update(mapping: dict):
    """Escribe varios valores a la vez."""
    with _lock:
        _state.update(mapping)


def snapshot() -> dict:
    """Devuelve una copia completa del estado actual."""
    with _lock:
        return dict(_state)
