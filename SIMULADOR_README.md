# Simulador ESP32-S3 — Guía para Equipos

> **Para qué sirve:** Como no tenemos un ESP32 físico durante esta etapa, este script reemplaza al hardware. Emite por UDP los mismos paquetes que mandaría un ESP32 real con MPU-6050, BMP180, DS18B20 y GPS, y además **escucha comandos** del Centro de Control para arrancar, abortar o reiniciar la misión.
>
> Usen este simulador para probar su módulo localmente antes de la re-entrega.

---

## Quick start (2 terminales)

**Terminal 1 — la aplicación:**
```powershell
python main.py
```

**Terminal 2 — el ESP32 simulado:**
```powershell
python simulador_esp32.py
```

Al arrancar, el simulador queda en estado **WAITING**. Hasta que **alguno de los módulos le mande la señal de arranque**, solo emite paquetes en STANDBY (altitud=0, fase=STANDBY). El cohete no se va a mover hasta que el botón de despegue mande el comando correcto.

Para arrancar la misión sin tocar la app (debug rápido):
```powershell
python -c "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'{\"cmd\":\"launch\"}', ('127.0.0.1', 9090))"
```

---

## Canales de comunicación

| Dirección | Puerto | Quién escucha | Para qué |
|---|---:|---|---|
| ⬇️ Telemetría | UDP **8080** | `modulo_aterrizaje` | Sensores (MPU-6050, BMP180, DS18B20) |
| ⬇️ Telemetría | UDP **8081** | `modulo_recuperacion` | GPS y telemetría de vuelo |
| ⬆️ Comandos | UDP **9090** | el **simulador** | Cualquier módulo manda: launch, abort, reset, status |

> **Nota importante para Equipo 4 (Recuperación):** En la versión original ustedes escuchaban en 8080 igual que aterrizaje. El docente cambió su listener a 8081 antes de la evaluación (cambio menor de 2 líneas). Asegúrense de mantener 8081 en su código.

---

## Formato del payload de telemetría (lo que el simulador les manda)

Cada paquete que sale por UDP a 8080 y 8081 es un JSON unificado. Cada módulo toma con `.get()` los campos que le interesan:

```json
{
  "type": "telemetria",

  "ax": 0.02, "ay": -0.01, "az": 2.81,
  "gx": 1.23, "gy": -0.45, "gz": 0.12,
  "magnitud": 27.59,
  "temp_int": 32.4,
  "temp_ext": 15.7,
  "altitud": 245.3,
  "presion": 983.5,

  "latitud": 22.161045,
  "longitud": -102.268652,
  "velocidad": 22.5,
  "vel_vert": 22.5,
  "hora_gps": "14:32:18",
  "rssi": 78,
  "distancia": 95.2,

  "fase": "ASCENSO",
  "bateria": 84.5,
  "sim_estado": "ACTIVE"
}
```

| Campo | Origen real (cuando haya ESP32) | Quién lo usa |
|---|---|---|
| `ax`, `ay`, `az` | MPU-6050 acelerómetro (g) | Aterrizaje |
| `gx`, `gy`, `gz` | MPU-6050 giroscopio (°) — interpretados como pitch/roll/yaw | Aterrizaje |
| `magnitud` | módulo del vector aceleración (m/s²) | Aterrizaje |
| `temp_int` | BMP180 | Aterrizaje |
| `temp_ext` | DS18B20 | Aterrizaje |
| `altitud` | BMP180 (m sobre nivel base) | Aterrizaje, Recuperación, Despliegue |
| `presion` | BMP180 (hPa) | Aterrizaje |
| `latitud`, `longitud` | GPS (grados decimales) | Recuperación |
| `velocidad`, `vel_vert` | derivada de altitud (m/s) | Recuperación, Despliegue |
| `hora_gps` | GPS (HH:MM:SS) | Recuperación |
| `rssi` | calidad de señal WiFi (0-100) | Recuperación, Despegue |
| `distancia` | calculada con Haversine (m) | Recuperación |
| `fase` | STANDBY / ASCENSO / APOGEO / DESPLIEGUE / DESCENSO / ATERRIZAJE | Despliegue |
| `bateria` | % | todos |
| `sim_estado` | estado interno del simulador (WAITING/ACTIVE/ABORTED/COMPLETE) — solo para debug | — |

---

## API de comandos (lo que **ustedes** mandan al simulador)

El simulador escucha en `UDP 127.0.0.1:9090` y acepta JSON con un campo `cmd`. Es **permisivo**: reconoce varios sinónimos.

| Acción | Aliases reconocidos | Efecto |
|---|---|---|
| **Despegue** | `launch`, `start`, `arm`, `lanzar`, `despegar`, `go`, `fire`, `ignition` | Arranca cronómetro y empieza el perfil de misión completo |
| **Abortar** | `abort`, `cancel`, `stop`, `abortar`, `detener`, `halt`, `emergency` | Desciende rápido desde la altitud actual hasta 0 en ~5s |
| **Reset** | `reset`, `restart`, `reiniciar`, `standby` | Vuelve a WAITING (listo para otro launch) |
| **Status** | `status`, `ping`, `estado`, `query` | Responde con JSON al remitente (estado actual, altitud, último cmd) |

> Si mandan otro alias y creen que debería reconocerse (por ejemplo `inicio` o `liftoff`), avisen al docente para agregarlo. **Lo importante:** el simulador imprime en consola **cada comando recibido**, así que si mandan algo y no pasa nada, miren la terminal del simulador para ver qué llegó.

### Ejemplo de respuesta a `status`

```json
{
  "type": "status_reply",
  "sim_estado": "ACTIVE",
  "alt_actual": 245.3,
  "vel_actual": 22.5,
  "comandos_recibidos": 3,
  "ultimo_cmd": "status",
  "t_launch": 1716045600.123
}
```

---

## Snippets de Python (copy-paste por módulo)

### Despegue — mandar señal de lanzamiento al pulsar el botón

En `_do_launch` (línea ~516), después de la confirmación del `messagebox`, **antes** de empezar la cuenta regresiva:

```python
import socket
import json

def _enviar_comando(cmd: str, host="127.0.0.1", port=9090):
    """Envia un comando JSON al ESP32 (o al simulador)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = json.dumps({"cmd": cmd}).encode("utf-8")
        sock.sendto(msg, (host, port))
        sock.close()
        return True
    except Exception as e:
        print(f"[ESP32] Error al enviar '{cmd}': {e}")
        return False

# Ejemplo de uso en _do_launch:
def _do_launch(self):
    ok = messagebox.askyesno("CONFIRMAR LANZAMIENTO",
                             "¿Activar despegue?", icon="warning")
    if not ok:
        return
    if not _enviar_comando("launch"):
        messagebox.showerror("Error", "No se pudo contactar al ESP32")
        return
    # ... el resto de la cuenta regresiva
```

Análogamente, `_do_abort` debería mandar `_enviar_comando("abort")`.

### Despegue — leer telemetría real en lugar de inventarla con `random`

En vez de `_start_wifi_sim` (que usa `random.randint`), abrir un listener UDP:

```python
import socket, json, threading

class TelemetriaReader:
    def __init__(self, port=8080):
        self.port = port
        self.datos = {}
        self.conectado = False
        self._sock = None

    def iniciar(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Atención: si aterrizaje ya tomó 8080, usen otro puerto o
        # acuerden un puerto exclusivo de despegue con el equipo 3.
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.settimeout(1.0)
        self.conectado = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.conectado:
            try:
                data, _ = self._sock.recvfrom(2048)
                self.datos = json.loads(data.decode("utf-8"))
            except socket.timeout:
                continue
            except Exception:
                pass
```

> **Tip de arquitectura:** Pueden delegar a Aterrizaje (que ya tiene el listener) y leer desde `shared_state.py` para no abrir un socket nuevo. Ver sección "Bus compartido" más abajo.

### Despliegue — sacar el listener UDP del bloque `if __name__ == "__main__"`

Su listener actual (línea ~1380) funciona, pero está dentro de `__main__` así que **solo corre cuando ejecutan `python modulo_despliegue.py` solo**. Cuando `main.py` los importa, ese bloque no se ejecuta y su cuadrante no recibe datos de telemetría.

**Solución:** Mover el listener a un método de la clase `ModuloDespliegue` y arrancarlo desde `__init__`:

```python
def __init__(self, parent_frame):
    # ... el resto del __init__ existente ...
    self._iniciar_listener_udp()

def _iniciar_listener_udp(self, port=8082):
    """Listener propio del módulo despliegue."""
    import socket, threading
    def _hilo():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(1.0)
        while True:
            try:
                data, _ = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                # Ejecutar en el hilo de Tk
                self.parent.after(0, lambda d=msg: self.recibir_datos(d))
            except socket.timeout:
                continue
            except Exception:
                pass
    threading.Thread(target=_hilo, daemon=True).start()
```

> Como aterrizaje toma 8080 y recuperación toma 8081, **pídanle al docente que el simulador emita también a 8082** (o pongan a alguno de sus compañeros como bus principal y lean del `shared_state`).

### Aterrizaje — ya está OK, limpiezas menores sugeridas

- Borrar imports duplicados de las líneas 22-25.
- Reducir 3 métodos (`leer_datos`, `obtener`, `read`) a uno solo.
- Cambiar `d["gy"]` → `d.get("gy", 0.0)` en `_leer_sensores` (línea 818-832) para tolerar paquetes incompletos.
- Borrar la línea 989 (multiplica por 0).

### Recuperación — ya está OK con el fix de puerto

- Confirmar que su `_escuchar_udp` usa `UDP_PORT = 8081`.
- Borrar el comentario `# <--- CAMBIA ESTO POR TU LONGITUD` de la línea 770 (la base ya está hardcodeada arriba, no hace falta cambiar nada).
- Sacar el `import shared_state as SS` que tienen adentro del método `_escuchar_udp` (ya está al top del archivo).

---

## Bus compartido (`shared_state.py`)

El equipo 4 creó `shared_state.py` como un diccionario thread-safe accesible desde todos los módulos. Si lo usan en serio, pueden evitar abrir múltiples listeners UDP:

```python
import shared_state as SS

# Leer
estado = SS.snapshot()
altitud = estado.get("altitud", 0.0)

# Escribir (típicamente desde un módulo "publisher")
SS.update({
    "altitud": 245.3,
    "velocidad": 22.5,
    "launch_state": "LANZAMIENTO",
})
```

**Sugerencia arquitectónica:** Acuerden entre los 4 equipos **un solo "publisher"** que escuche el UDP del ESP32 y publique a `shared_state`. Los otros 3 módulos solo leen. Eso elimina los conflictos de puerto.

---

## Opciones del simulador

```text
python simulador_esp32.py [opciones]

--host HOST                  IP destino (default 127.0.0.1)
--puerto-aterrizaje N        UDP para aterrizaje (default 8080)
--puerto-recuperacion N      UDP para recuperación (default 8081)
--cmd-port N                 UDP donde el sim escucha comandos (default 9090)
--cmd-bind IP                IP donde bindear (default 0.0.0.0)
--hz N                       Frecuencia de envío telemetría (default 10)
--velocidad N                Acelerar la misión (default 1.0, ej: 4 = 4x rápido)
--modo {telemetria,despliegue,ambos}
                             Tipo de tramas (default ambos)
--loop                       Al completar misión, volver a WAITING
--auto-start                 No esperar comando, lanzar la misión enseguida
--quiet                      No imprimir cada paquete
```

### Casos de uso típicos

**Probar la app completa (esperando comando de despegue):**
```powershell
python simulador_esp32.py
```

**Modo demo continuo (no espera comando, misión en loop):**
```powershell
python simulador_esp32.py --auto-start --loop --velocidad 4
```

**Solo telemetría de despliegue (para validar modulo_despliegue standalone):**
```powershell
python simulador_esp32.py --modo despliegue --auto-start
```

**Probar el listener de comandos manualmente:**
```powershell
python -c "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'{\"cmd\":\"status\"}', ('127.0.0.1', 9090))"
```

---

## Perfil de misión (lo que verán en pantalla)

| t (seg) | Fase | Altitud (m) | Vel. vertical (m/s) |
|---:|---|---:|---:|
| 0 – 4 | STANDBY | 0 | 0 |
| 4 – 12 | ASCENSO | 0 → 360 | +12 → +45 → +18 |
| 12 – 17 | APOGEO | ~395 | 0 |
| 17 – 20 | DESPLIEGUE | 385 → 320 | -3 → -6.5 |
| 20 – 32 | DESCENSO | 320 → 8 | ~-6.0 |
| 32 – 36 | ATERRIZAJE | 8 → 0 | -2 → 0 |

Duración total: ~36 segundos a velocidad 1×. Pueden acelerar con `--velocidad 4` para no esperar tanto.

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `OSError: [Errno 10048]` al arrancar | Puerto 8080 o 8081 ya ocupado | Cerrar otra instancia: `taskkill /F /IM python.exe` |
| Aterrizaje no recibe datos | Sensores marcan ERROR | Pulsar ACTIVAR — necesita validación previa |
| Recuperación no muestra movimiento | Pulsar el botón ACTIVAR (esquina superior derecha) | El módulo solo procesa datos si está ACTIVO |
| Despliegue queda en STANDBY siempre | Su listener UDP está adentro de `__main__` | Mover a `__init__` (ver snippet arriba) |
| El simulador no recibe mi `launch` | El simulador escucha en 9090, no 8080 | `port=9090` en el `sendto` |
| El simulador imprime "cmd DESCONOCIDO" | Alias no reconocido | Usar uno de los aliases listados, o avisar al docente |
| La app se cierra y queda zombie | Tkinter no terminó limpio | `taskkill /F /IM python.exe` |

---

## Lo que el docente busca ver en la re-entrega

1. **Ningún `random.*` para inventar datos.** Si su módulo necesita un dato, debe venir del UDP (del simulador o del ESP32 real).
2. **El botón de despegue manda un comando real al ESP32** (o al simulador). Lo verifican en la terminal del simulador: tiene que aparecer `[CMD] <- ... 'launch' -> LANZAMIENTO`.
3. **Los módulos siguen funcionando integrados en `main.py`**, no solo standalone. Si tienen un listener UDP dentro de `if __name__ == "__main__"`, sáquenlo.
4. **El cuadrante actualiza valores visibles** cuando llega telemetría (altitud, velocidad, fase, etc.).
5. **La integración entre módulos funciona vía `shared_state.py`** (opcional pero recomendado).

---

## Plazo de re-entrega

Tienen **2 días** para mejorar su módulo. La evaluación previa queda como referencia; los puntos sobre lo que ya entregaron no cambian, **pero pueden recuperar terreno** mostrando que ahora cumplen los puntos críticos (sobre todo la **Integración ESP32**).

Pregunten al docente cualquier duda sobre la API del simulador antes de implementar.
