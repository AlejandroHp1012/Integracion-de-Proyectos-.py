"""
==================================================================
  SIMULADOR ESP32-S3 — Mision Alpha-001  (v2 con uplink)
==================================================================
  Herramienta de TESTING para que los equipos puedan validar sus
  modulos sin tener un ESP32 fisico.

  CANALES:
    127.0.0.1:8080  UDP  downlink -> modulo_aterrizaje   (telemetria)
    127.0.0.1:8081  UDP  downlink -> modulo_recuperacion (telemetria)
    127.0.0.1:9090  UDP  uplink   <- cualquier modulo    (comandos)

  ESTADO INICIAL:
    El simulador arranca en WAITING. Solo emite paquetes de fondo
    con fase=STANDBY (altitud=0, velocidad=0). Para que el cohete
    despegue, hay que enviarle un comando de arranque por UDP 9090.

  COMANDOS RECONOCIDOS (todos como JSON: {"cmd": "..."}):

    Despegue / arranque:
      launch | start | arm | lanzar | despegar | go | fire | ignition

    Abortar:
      abort | cancel | stop | abortar | detener | halt | emergency

    Reset (volver a WAITING):
      reset | restart | reiniciar | standby

    Consulta de estado (responde al sender):
      status | ping | estado | query

  El simulador es PERMISIVO: si recibe un cmd desconocido, lo loguea
  pero no falla. Los equipos pueden adoptar cualquiera de los alias
  listados arriba, o avisar al docente si necesitan agregar uno.

  USO TIPICO:
    python simulador_esp32.py                  # espera comando de arranque
    python simulador_esp32.py --auto-start     # arranca solo (compat v1)
    python simulador_esp32.py --velocidad 4    # mision 4x mas rapida
    python simulador_esp32.py --loop           # se repite indefinidamente

  Ctrl+C para detener.
==================================================================
"""
import argparse
import json
import math
import random
import socket
import sys
import threading
import time
from datetime import datetime


# ─── Coordenadas base de la mision ───
BASE_LAT = 22.16100
BASE_LON = -102.26877


# ─── Perfil de mision: keyframes (t_seg, fase, altitud_m, vel_vert_ms) ───
MISION = [
    (  0.0, "STANDBY",       0.0,    0.0),
    (  4.0, "STANDBY",       0.0,    0.0),
    (  4.5, "ASCENSO",       5.0,   12.0),
    (  8.0, "ASCENSO",     180.0,   45.0),
    ( 12.0, "ASCENSO",     360.0,   18.0),
    ( 15.0, "APOGEO",      395.0,    0.5),
    ( 16.0, "APOGEO",      392.0,   -1.0),
    ( 17.0, "DESPLIEGUE",  385.0,   -3.0),
    ( 20.0, "DESCENSO",    320.0,   -6.5),
    ( 26.0, "DESCENSO",    150.0,   -6.0),
    ( 32.0, "ATERRIZAJE",    8.0,   -2.0),
    ( 34.0, "ATERRIZAJE",    0.0,    0.0),
    ( 36.0, "ATERRIZAJE",    0.0,    0.0),
]
DURACION_MISION = MISION[-1][0]


# ─── Aliases de comandos (todos en lowercase) ───
CMD_LAUNCH = {"launch", "start", "arm", "lanzar", "despegar", "go", "fire", "ignition"}
CMD_ABORT  = {"abort", "cancel", "stop", "abortar", "detener", "halt", "emergency"}
CMD_RESET  = {"reset", "restart", "reiniciar", "standby"}
CMD_STATUS = {"status", "ping", "estado", "query"}


# ═══════════════════════════════════════════════════════════════════
#  ESTADO COMPARTIDO ENTRE THREADS
# ═══════════════════════════════════════════════════════════════════
class Estado:
    WAITING  = "WAITING"
    ACTIVE   = "ACTIVE"
    ABORTED  = "ABORTED"
    COMPLETE = "COMPLETE"

    def __init__(self):
        self._lock = threading.Lock()
        self.fase = Estado.WAITING
        self.t_launch = None          # timestamp del launch
        self.t_abort  = None          # timestamp del abort
        self.alt_at_abort = 0.0       # altitud al momento del abort
        self.vel_at_abort = 0.0
        self.comandos_recibidos = 0
        self.ultimo_cmd = None
        self.ultimo_cmd_ts = None
        self.ultimo_sender = None

    def lanzar(self):
        with self._lock:
            self.fase = Estado.ACTIVE
            self.t_launch = time.time()
            self.t_abort = None

    def abortar(self, alt_actual: float, vel_actual: float):
        with self._lock:
            if self.fase != Estado.ACTIVE:
                return False
            self.fase = Estado.ABORTED
            self.t_abort = time.time()
            self.alt_at_abort = alt_actual
            self.vel_at_abort = vel_actual
            return True

    def resetear(self):
        with self._lock:
            self.fase = Estado.WAITING
            self.t_launch = None
            self.t_abort = None
            self.alt_at_abort = 0.0
            self.vel_at_abort = 0.0

    def completar(self):
        with self._lock:
            self.fase = Estado.COMPLETE

    def registrar_cmd(self, cmd: str, sender: tuple):
        with self._lock:
            self.comandos_recibidos += 1
            self.ultimo_cmd = cmd
            self.ultimo_cmd_ts = datetime.now().strftime("%H:%M:%S")
            self.ultimo_sender = f"{sender[0]}:{sender[1]}"

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "fase":               self.fase,
                "t_launch":           self.t_launch,
                "t_abort":            self.t_abort,
                "alt_at_abort":       self.alt_at_abort,
                "vel_at_abort":       self.vel_at_abort,
                "comandos_recibidos": self.comandos_recibidos,
                "ultimo_cmd":         self.ultimo_cmd,
                "ultimo_cmd_ts":      self.ultimo_cmd_ts,
                "ultimo_sender":      self.ultimo_sender,
            }


# ═══════════════════════════════════════════════════════════════════
#  GENERACION DE TELEMETRIA
# ═══════════════════════════════════════════════════════════════════
def interpolar_mision(t: float):
    """Interpola la mision en el instante t. Retorna (fase, alt, vel)."""
    if t <= MISION[0][0]:
        _, fase, alt, vel = MISION[0]
        return fase, alt, vel
    if t >= MISION[-1][0]:
        _, fase, alt, vel = MISION[-1]
        return fase, alt, vel
    for i in range(len(MISION) - 1):
        t1, fase1, alt1, vel1 = MISION[i]
        t2, _,     alt2, vel2 = MISION[i + 1]
        if t1 <= t <= t2:
            r = (t - t1) / (t2 - t1) if t2 != t1 else 0.0
            alt = alt1 + (alt2 - alt1) * r
            vel = vel1 + (vel2 - vel1) * r
            return fase1, alt, vel
    return MISION[-1][1], MISION[-1][2], MISION[-1][3]


def trayectoria_abort(snap: dict) -> tuple:
    """
    Perfil de aterrizaje de emergencia tras un abort.
    Desciende desde la altitud actual hasta 0 en ~5 segundos.
    """
    t_desde_abort = time.time() - snap["t_abort"]
    duracion = 5.0
    alt0 = snap["alt_at_abort"]
    if t_desde_abort >= duracion:
        return "ATERRIZAJE", 0.0, 0.0
    r = t_desde_abort / duracion
    alt = max(0.0, alt0 * (1 - r))
    vel = -alt0 / duracion
    fase = "ATERRIZAJE" if alt < 10 else "DESCENSO"
    return fase, alt, vel


def gps_desde_base(altitud: float, t: float):
    """Coordenadas GPS que se alejan de la base segun la altitud."""
    desplazamiento_m = (altitud / 400.0) * 100.0 + math.sin(t * 0.3) * 5.0
    bearing_deg = 45.0 + math.sin(t * 0.1) * 20.0
    bearing_rad = math.radians(bearing_deg)
    dlat = (desplazamiento_m * math.cos(bearing_rad)) / 111000.0
    dlon = (desplazamiento_m * math.sin(bearing_rad)) / (111000.0 * math.cos(math.radians(BASE_LAT)))
    return BASE_LAT + dlat, BASE_LON + dlon


def hacer_payload_telemetria(t_real: float, mision_t: float, estado: Estado) -> dict:
    """Payload unificado que satisface aterrizaje + recuperacion."""
    snap = estado.snapshot()

    if snap["fase"] == Estado.WAITING:
        fase, altitud, vel_vert = "STANDBY", 0.0, 0.0
    elif snap["fase"] == Estado.ABORTED:
        fase, altitud, vel_vert = trayectoria_abort(snap)
    elif snap["fase"] == Estado.ACTIVE:
        fase, altitud, vel_vert = interpolar_mision(mision_t)
    else:  # COMPLETE
        fase, altitud, vel_vert = "ATERRIZAJE", 0.0, 0.0

    lat, lon = gps_desde_base(altitud, t_real)

    # IMU segun fase
    if fase == "STANDBY":
        ax, ay, az = 0.01, -0.01, 1.00
        gx, gy, gz = 0.1, -0.2, 0.0
        magnitud = 9.81
    elif fase == "ASCENSO":
        ax = random.uniform(-0.05, 0.05)
        ay = random.uniform(-0.05, 0.05)
        az = 2.8 + random.uniform(-0.3, 0.3)
        gx = random.uniform(-2.0, 2.0)
        gy = random.uniform(-2.0, 2.0)
        gz = random.uniform(-1.0, 1.0)
        magnitud = abs(az) * 9.80665
    elif fase == "APOGEO":
        ax, ay, az = 0.02, -0.02, 0.05
        gx = random.uniform(-5.0, 5.0)
        gy = random.uniform(-5.0, 5.0)
        gz = random.uniform(-3.0, 3.0)
        magnitud = 0.5
    elif fase == "DESPLIEGUE":
        ax = random.uniform(-0.3, 0.3)
        ay = random.uniform(-0.3, 0.3)
        az = -1.5 + random.uniform(-0.5, 0.5)
        gx = random.uniform(-8.0, 8.0)
        gy = random.uniform(-8.0, 8.0)
        gz = random.uniform(-2.0, 2.0)
        magnitud = abs(az) * 9.80665
    elif fase == "DESCENSO":
        ax = random.uniform(-0.1, 0.1)
        ay = random.uniform(-0.1, 0.1)
        az = -0.6 + random.uniform(-0.1, 0.1)
        gx = random.uniform(-1.5, 1.5)
        gy = random.uniform(-1.5, 1.5)
        gz = random.uniform(-0.5, 0.5)
        magnitud = abs(az) * 9.80665
    else:  # ATERRIZAJE
        ax, ay, az = 0.0, 0.0, 1.0
        gx, gy, gz = 0.0, 0.0, 0.0
        magnitud = 9.81

    temp_externa = 22.0 - (altitud / 1000.0) * 6.5 + random.uniform(-0.3, 0.3)
    temp_interna = 28.0 + (altitud / 400.0) * 4.0 + random.uniform(-0.2, 0.2)
    presion = 1013.25 - (altitud / 100.0) * 12.0 + random.uniform(-0.5, 0.5)

    distancia_aprox = math.hypot(altitud, (altitud / 400.0) * 100.0)
    rssi_pct = max(20, int(100 - distancia_aprox / 8.0))

    # Distancia horizontal real (Haversine)
    R = 6371000.0
    phi1 = math.radians(BASE_LAT)
    phi2 = math.radians(lat)
    dphi = math.radians(lat - BASE_LAT)
    dlmb = math.radians(lon - BASE_LON)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    dist_m = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Bateria: se descarga solo durante ACTIVE / ABORTED
    if snap["t_launch"]:
        bat_t = time.time() - snap["t_launch"]
        bateria = max(20.0, 85.0 - bat_t * 0.5)
    else:
        bateria = 85.0

    return {
        "type":         "telemetria",
        # MPU6050 + BMP180 + DS18B20
        "ax":           round(ax, 4),
        "ay":           round(ay, 4),
        "az":           round(az, 4),
        "gx":           round(gx, 3),
        "gy":           round(gy, 3),
        "gz":           round(gz, 3),
        "magnitud":     round(magnitud, 3),
        "temp_int":     round(temp_interna, 2),
        "temp_ext":     round(temp_externa, 2),
        "altitud":      round(altitud, 2),
        "presion":      round(presion, 2),
        # GPS / telemetria de vuelo
        "latitud":      round(lat, 6),
        "longitud":     round(lon, 6),
        "velocidad":    round(abs(vel_vert), 2),
        "vel_vert":     round(vel_vert, 2),
        "hora_gps":     datetime.now().strftime("%H:%M:%S"),
        "rssi":         rssi_pct,
        "distancia":    round(dist_m, 1),
        "fase":         fase,
        "bateria":      round(bateria, 1),
        # Estado del simulador (util para debug del equipo)
        "sim_estado":   snap["fase"],
    }


def hacer_payload_despliegue(mision_t: float, estado: Estado) -> dict:
    """Trama tipo despliegue (para validar modulo_despliegue standalone)."""
    snap = estado.snapshot()
    if snap["fase"] == Estado.WAITING:
        fase, altitud, vel_vert = "STANDBY", 0.0, 0.0
    elif snap["fase"] == Estado.ABORTED:
        fase, altitud, vel_vert = trayectoria_abort(snap)
    elif snap["fase"] == Estado.ACTIVE:
        fase, altitud, vel_vert = interpolar_mision(mision_t)
    else:
        fase, altitud, vel_vert = "ATERRIZAJE", 0.0, 0.0

    desplegado = fase in ("DESPLIEGUE", "DESCENSO", "ATERRIZAJE")
    return {
        "type":       "despliegue",
        "altitud":    round(altitud, 2),
        "velocidad":  round(vel_vert, 2),
        "bateria":    85.0,
        "desplegado": desplegado,
        "fase":       fase,
    }


# ═══════════════════════════════════════════════════════════════════
#  LISTENER UPLINK (puerto comandos)
# ═══════════════════════════════════════════════════════════════════
def listener_comandos(estado: Estado, args, sock_envio: socket.socket,
                      alt_actual_ref: list, vel_actual_ref: list):
    """
    Thread que escucha comandos JSON entrantes en args.cmd_port.
    Mensajes esperados: {"cmd": "launch"} y variantes.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((args.cmd_bind, args.cmd_port))
    except OSError as e:
        print(f"[CMD] ERROR no se pudo bindear {args.cmd_bind}:{args.cmd_port} -> {e}")
        return

    print(f"[CMD] Escuchando comandos en {args.cmd_bind}:{args.cmd_port}")
    sock.settimeout(1.0)

    while True:
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        except OSError:
            break

        ts = datetime.now().strftime("%H:%M:%S")
        try:
            raw = data.decode("utf-8", errors="replace").strip()
            msg = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[{ts}] [CMD] <- {addr[0]}:{addr[1]}  JSON invalido: {raw[:80]!r}")
            continue
        except Exception as e:
            print(f"[{ts}] [CMD] <- {addr[0]}:{addr[1]}  error parse: {e}")
            continue

        if not isinstance(msg, dict):
            print(f"[{ts}] [CMD] <- {addr[0]}:{addr[1]}  esperaba dict, recibi {type(msg).__name__}")
            continue

        cmd_raw = msg.get("cmd") or msg.get("command") or msg.get("comando")
        if cmd_raw is None:
            print(f"[{ts}] [CMD] <- {addr[0]}:{addr[1]}  sin campo cmd. Recibido: {msg}")
            continue

        cmd = str(cmd_raw).strip().lower()
        estado.registrar_cmd(cmd, addr)

        if cmd in CMD_LAUNCH:
            snap = estado.snapshot()
            if snap["fase"] == Estado.ACTIVE:
                print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' ignorado (ya ACTIVE)")
            else:
                estado.lanzar()
                print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' -> LANZAMIENTO. Mision iniciada.")

        elif cmd in CMD_ABORT:
            ok = estado.abortar(alt_actual_ref[0], vel_actual_ref[0])
            if ok:
                print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' -> ABORT desde alt={alt_actual_ref[0]:.1f}m")
            else:
                print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' ignorado (no estaba ACTIVE)")

        elif cmd in CMD_RESET:
            estado.resetear()
            print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' -> RESET a WAITING")

        elif cmd in CMD_STATUS:
            snap = estado.snapshot()
            respuesta = {
                "type":               "status_reply",
                "sim_estado":         snap["fase"],
                "alt_actual":         round(alt_actual_ref[0], 2),
                "vel_actual":         round(vel_actual_ref[0], 2),
                "comandos_recibidos": snap["comandos_recibidos"],
                "ultimo_cmd":         snap["ultimo_cmd"],
                "t_launch":           snap["t_launch"],
            }
            try:
                sock_envio.sendto(json.dumps(respuesta).encode("utf-8"), addr)
                print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' -> reply enviado ({snap['fase']})")
            except Exception as e:
                print(f"[{ts}] [CMD] error al responder: {e}")

        else:
            print(f"[{ts}] [CMD] <- {addr[0]}  '{cmd}' DESCONOCIDO. "
                  f"Validos: {sorted(CMD_LAUNCH | CMD_ABORT | CMD_RESET | CMD_STATUS)}")


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="Simulador ESP32-S3 (v2 con uplink de comandos)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1",
                   help="IP destino para telemetria (default 127.0.0.1)")
    p.add_argument("--puerto-aterrizaje", type=int, default=8080,
                   help="Puerto UDP de modulo_aterrizaje (default 8080)")
    p.add_argument("--puerto-recuperacion", type=int, default=8081,
                   help="Puerto UDP de modulo_recuperacion (default 8081)")
    p.add_argument("--puerto-despegue", type=int, default=9091,
                   help="Puerto UDP de modulo_despegue (default 9091)")
    p.add_argument("--cmd-port", type=int, default=9090,
                   help="Puerto UDP donde escuchar comandos (default 9090)")
    p.add_argument("--cmd-bind", default="0.0.0.0",
                   help="IP donde bindear el puerto de comandos (default 0.0.0.0)")
    p.add_argument("--hz", type=float, default=10.0,
                   help="Frecuencia de envio telemetria en Hz (default 10)")
    p.add_argument("--velocidad", type=float, default=1.0,
                   help="Factor de aceleracion del tiempo de mision (default 1.0)")
    p.add_argument("--modo", choices=["telemetria", "despliegue", "ambos"],
                   default="ambos",
                   help="Tipo de tramas a emitir (default ambos)")
    p.add_argument("--loop", action="store_true",
                   help="Volver a WAITING al terminar (en lugar de COMPLETE final)")
    p.add_argument("--auto-start", action="store_true",
                   help="No esperar comando — arrancar la mision al ejecutar (compat v1)")
    p.add_argument("--quiet", action="store_true",
                   help="No imprimir cada paquete (solo cambios de fase y comandos)")
    args = p.parse_args()

    estado = Estado()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Refs mutables para que el listener sepa la altitud/vel actuales (uso para abort)
    alt_actual_ref = [0.0]
    vel_actual_ref = [0.0]

    # Levantar listener de comandos (siempre, aunque haya --auto-start)
    hilo_cmd = threading.Thread(
        target=listener_comandos,
        args=(estado, args, sock, alt_actual_ref, vel_actual_ref),
        daemon=True)
    hilo_cmd.start()

    if args.auto_start:
        estado.lanzar()
        print("[SIM] --auto-start: misión iniciada inmediatamente (sin esperar comando)")

    intervalo = 1.0 / args.hz
    paquetes = 0
    fase_anterior = None

    print("== Simulador ESP32-S3 (v2) ==")
    print(f"   telemetria -> {args.host}:{args.puerto_aterrizaje} (aterrizaje)")
    print(f"                 {args.host}:{args.puerto_recuperacion} (recuperacion)")
    print(f"                 {args.host}:{args.puerto_despegue} (despegue)")
    print(f"   comandos   <- {args.cmd_bind}:{args.cmd_port}")
    print(f"   modo:       {args.modo}")
    print(f"   frecuencia: {args.hz} Hz")
    print(f"   velocidad:  {args.velocidad}x")
    print(f"   duracion:   {DURACION_MISION:.1f}s por mision")
    print(f"   loop:       {'si' if args.loop else 'no'}")
    print(f"   estado:     {estado.snapshot()['fase']}")
    print("--")
    print("Para iniciar la mision, enviar:  echo '{\"cmd\":\"launch\"}' | nc -u -w1 127.0.0.1 9090")
    print("(o desde Python: sock.sendto(b'{\"cmd\":\"launch\"}', ('127.0.0.1', 9090)))")
    print("Ctrl+C para detener.")
    print()

    try:
        while True:
            t_real = time.time()
            snap = estado.snapshot()

            # Calcular tiempo de mision (relativo al lanzamiento)
            if snap["fase"] == Estado.ACTIVE and snap["t_launch"]:
                mision_t = (t_real - snap["t_launch"]) * args.velocidad
                if mision_t >= DURACION_MISION:
                    if args.loop:
                        estado.resetear()
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Mision completa, vuelvo a WAITING (loop)")
                    else:
                        estado.completar()
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Mision COMPLETA. {paquetes} paquetes enviados.")
            else:
                mision_t = 0.0

            # Generar y enviar
            if args.modo in ("telemetria", "ambos"):
                payload = hacer_payload_telemetria(t_real, mision_t, estado)
                data = json.dumps(payload).encode("utf-8")
                sock.sendto(data, (args.host, args.puerto_aterrizaje))
                sock.sendto(data, (args.host, args.puerto_recuperacion))
                sock.sendto(data, (args.host, args.puerto_despegue))
                fase = payload["fase"]
                altitud = payload["altitud"]
                vel = payload["vel_vert"]
                alt_actual_ref[0] = altitud
                vel_actual_ref[0] = vel
            if args.modo in ("despliegue", "ambos"):
                payload_dep = hacer_payload_despliegue(mision_t, estado)
                data_dep = json.dumps(payload_dep).encode("utf-8")
                sock.sendto(data_dep, (args.host, args.puerto_aterrizaje))
                if args.modo == "despliegue":
                    fase = payload_dep["fase"]
                    altitud = payload_dep["altitud"]
                    vel = payload_dep["velocidad"]
                    alt_actual_ref[0] = altitud
                    vel_actual_ref[0] = vel

            paquetes += 1

            # Log
            cambio_fase = fase != fase_anterior
            if cambio_fase:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f">>> FASE: {fase_anterior or '---':>12} -> {fase}  "
                      f"(sim={snap['fase']})")
                fase_anterior = fase
            elif not args.quiet and paquetes % max(1, int(args.hz)) == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"sim={snap['fase']:<8}  fase={fase:>11}  "
                      f"alt={altitud:6.1f}m  vel={vel:+6.2f}m/s  "
                      f"paq={paquetes}  cmds={snap['comandos_recibidos']}")

            time.sleep(intervalo)

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> Detenido por usuario. "
              f"{paquetes} paquetes enviados, "
              f"{estado.snapshot()['comandos_recibidos']} comandos recibidos.")
        sys.exit(0)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
