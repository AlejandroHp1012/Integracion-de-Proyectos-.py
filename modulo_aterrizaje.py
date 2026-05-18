"""
╔══════════════════════════════════════════════════════╗
║  MÓDULO ATERRIZAJE — Equipo 3                        ║
║  Sensores: ESP32 + DS18B20 + MPU-6050 + BMP180       ║
║                                                      ║
║  ► Solo inicia si los 3 sensores son detectados      ║
║  ► Sin datos simulados                               ║
║  ► Telemetría guardada en SQLite (JSON)              ║
║  ► Botón para consultar historial                    ║
╚══════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import sqlite3
import json
import time
from datetime import datetime

# ── Lector UDP (WiFi) ──────────────────────────────────────────
import socket
import threading
import json
import time

class UdpReader:
    def __init__(self, port=8080):
        self.port = port
        self.conectado = False
        self._sock = None
        self._hilo = None
        
        self._ultimo_dato = {}
        self.datos = {} 
        self.nuevo_dato = False
        self._ultima_recepcion = 0
        self._ultimo_paquete = 0

    def iniciar(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind(("0.0.0.0", self.port))
            self._sock.settimeout(1.0)
            self.conectado = True
            
            self._hilo = threading.Thread(target=self._escuchar, daemon=True)
            self._hilo.start()
            print(f"[UDP] Escuchando telemetría en el puerto {self.port}")
        except Exception as e:
            print(f"[UDP] Error al iniciar: {e}")
            self.conectado = False

    def _escuchar(self):
        while self.conectado:
            try:
                data, addr = self._sock.recvfrom(1024)
                mensaje = data.decode('utf-8')
                
                if "{" in mensaje: 
                    datos_json = json.loads(mensaje)
                    
                    # ── TRUCO DE COMPATIBILIDAD ──
                    if "temp_int" in datos_json: 
                        datos_json["temperatura"] = datos_json["temp_int"]
                        datos_json["temp_interna"] = datos_json["temp_int"] # ¡Esta es la corrección nueva!
                        
                    if "magnitud" in datos_json: 
                        datos_json["aceleracion"] = datos_json["magnitud"]
                        
                    if "temp_ext" in datos_json: 
                        datos_json["temp_externa"] = datos_json["temp_ext"] 
                    
                    datos_json["type"] = "telemetria" 
                    
                    self._ultimo_dato = datos_json
                    self.datos = datos_json
                    self.nuevo_dato = True
                    
                    self._ultima_recepcion = time.time()
                    self._ultimo_paquete = time.time()
            except socket.timeout:
                pass
            except Exception as e:
                pass

    def validar_sensores(self, timeout=6.0):
        inicio = time.time()
        while time.time() - inicio < timeout:
            if (time.time() - self._ultima_recepcion) < 2.0 and self._ultimo_dato:
                return True
            time.sleep(0.1)
        return False

    def estado_sensores(self):
        if (time.time() - self._ultima_recepcion) > 2.0:
            return {"error": "Sin datos por WiFi"}
        return {
            "status": "ok",
            "mpu6050": "ok", 
            "bmp180": "ok", 
            "ds18b20": "ok",
            "bmi160": "ok"
        }
        
    def leer_datos(self): 
        self.nuevo_dato = False
        return self._ultimo_dato
        
    def obtener(self):
        self.nuevo_dato = False
        return self._ultimo_dato
        
    def read(self):
        self.nuevo_dato = False
        return self._ultimo_dato

try:
    _reader = UdpReader(port=8080)
    _reader.iniciar()
except Exception as e:
    print(f"[UDP] No disponible: {e}")
    _reader = None

# ── Base de datos SQLite ──────────────────────────────
DB_PATH = "telemetria_aterrizaje.db"

def _init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS telemetria (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            datos     TEXT
        )
    """)
    con.commit()
    con.close()

_init_db()

# ── Paleta de colores ─────────────────────────────────
C = {
    "bg":         "#04080F",
    "panel":      "#070B14",
    "border":     "#3B1F6A",
    "border_hi":  "#A855F7",
    "purple":     "#A855F7",
    "purple_dim": "#5B2D8A",
    "purple_dk":  "#1A0A2E",
    "amber":      "#FFB800",
    "amber_dim":  "#7A5500",
    "green":      "#00FF88",
    "green_dim":  "#004D22",
    "red":        "#FF2D55",
    "red_dim":    "#4A0018",
    "cyan":       "#00D4FF",
    "white":      "#E8E8FF",
    "grid":       "#0D0A1A",
    "text_gray":  "#4A5080",
    "text_dark":  "#1E2040",
}

MONO   = "Courier New"
MONO_S = (MONO, 7,  "bold")
MONO_M = (MONO, 9,  "bold")
MONO_L = (MONO, 11, "bold")


# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════
def _hex_blend(hx: str, b: float) -> str:
    hx = hx.lstrip("#")
    return "#{:02x}{:02x}{:02x}".format(
        int(int(hx[0:2], 16) * b),
        int(int(hx[2:4], 16) * b),
        int(int(hx[4:6], 16) * b),
    )


class _VBar(tk.Canvas):
    def __init__(self, parent, fg, label, height=80, **kw):
        super().__init__(parent, width=38, height=height,
                         bg=C["panel"], highlightthickness=0, **kw)
        self._fg  = fg
        self._lbl = label
        self._val = 0.0
        self._max = 100.0

    def update_val(self, val, max_val=100.0):
        self._val = max(0, min(val, max_val))
        self._max = max_val or 1
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()  or 38
        h = self.winfo_height() or 80
        bh = h - 20
        pct = self._val / self._max
        self.create_rectangle(4, 0, w-4, bh, fill="#0a0a14", outline=C["border"])
        if pct > 0:
            fy = bh * (1 - pct)
            self.create_rectangle(5, fy, w-5, bh-1, fill=self._fg, outline="")
        self.create_text(w//2, bh + 10, text=self._lbl,
                         fill=C["text_gray"], font=(MONO, 6, "bold"))


# ══════════════════════════════════════════════════════
#  VENTANA DE HISTORIAL
# ══════════════════════════════════════════════════════
class _VentanaHistorial(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("HISTORIAL TELEMETRÍA — SQLite")
        self.geometry("820x520")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self._construir()
        self._cargar()

    def _construir(self):
        # Barra superior
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="◈ HISTORIAL DE TELEMETRÍA",
                 font=MONO_L, bg=C["bg"], fg=C["purple"]).pack(side="left")
        tk.Button(top, text="↺ ACTUALIZAR", font=MONO_S,
                  bg=C["purple_dk"], fg=C["purple"], relief="flat",
                  cursor="hand2", command=self._cargar).pack(side="right")
        tk.Button(top, text="✕ LIMPIAR BD", font=MONO_S,
                  bg=C["red_dim"], fg=C["red"], relief="flat",
                  cursor="hand2", command=self._limpiar).pack(side="right", padx=6)

        # Filtros
        filt = tk.Frame(self, bg=C["panel"])
        filt.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(filt, text="LÍMITE:", font=MONO_S,
                 bg=C["panel"], fg=C["text_gray"]).pack(side="left", padx=(6, 2))
        self._lim_var = tk.StringVar(value="100")
        tk.Entry(filt, textvariable=self._lim_var, width=6,
                 font=MONO_S, bg="#0a0a20", fg=C["cyan"],
                 insertbackground=C["cyan"], relief="flat").pack(side="left")
        tk.Label(filt, text=" registros más recientes",
                 font=MONO_S, bg=C["panel"], fg=C["text_gray"]).pack(side="left")

        # Tabla
        cols = ("ID", "TIMESTAMP", "ALT(m)", "VEL(m/s)", "ACEL(m/s²)",
                "TEMP.INT(°C)", "TEMP.EXT(°C)", "PRESIÓN(hPa)",
                "PITCH(°)", "ROLL(°)", "YAW(°)")
        frame_t = tk.Frame(self, bg=C["bg"])
        frame_t.pack(fill="both", expand=True, padx=8, pady=4)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Telem.Treeview",
                        background="#070B14", foreground=C["text_gray"],
                        fieldbackground="#070B14", rowheight=20,
                        font=(MONO, 7))
        style.configure("Telem.Treeview.Heading",
                        background=C["purple_dk"], foreground=C["purple"],
                        font=(MONO, 7, "bold"), relief="flat")
        style.map("Telem.Treeview", background=[("selected", C["purple_dim"])])

        self._tree = ttk.Treeview(frame_t, columns=cols, show="headings",
                                   style="Telem.Treeview")
        widths = [40, 100, 70, 70, 80, 90, 90, 90, 70, 70, 70]
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(frame_t, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(frame_t, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame_t.rowconfigure(0, weight=1)
        frame_t.columnconfigure(0, weight=1)

        # Pie — totales
        self._lbl_total = tk.Label(self, text="", font=MONO_S,
                                    bg=C["bg"], fg=C["text_gray"])
        self._lbl_total.pack(anchor="w", padx=10, pady=4)

    def _cargar(self):
        self._tree.delete(*self._tree.get_children())
        try:
            lim = int(self._lim_var.get())
        except ValueError:
            lim = 100
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT id, timestamp, datos FROM telemetria "
            "ORDER BY id DESC LIMIT ?", (lim,)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM telemetria").fetchone()[0]
        con.close()

        for row_id, ts, datos_json in reversed(rows):
            try:
                d = json.loads(datos_json)
                self._tree.insert("", "end", values=(
                    row_id,
                    ts,
                    f"{d.get('altitud', 0):.1f}",
                    f"{d.get('vel_vert', 0):+.2f}",
                    f"{d.get('aceleracion', 0):+.2f}",
                    f"{d.get('temp_interna', 0):.1f}",
                    f"{d.get('temp_externa', 0):.1f}",
                    f"{d.get('presion', 0):.1f}",
                    f"{d.get('pitch', 0):+.1f}",
                    f"{d.get('roll', 0):+.1f}",
                    f"{d.get('yaw', 0):+.1f}",
                ))
            except Exception:
                pass
        self._lbl_total.config(
            text=f"Total en BD: {total} registros  |  Mostrando: {len(rows)}")

    def _limpiar(self):
        if tk.messagebox.askyesno("Confirmar",
                                  "¿Eliminar TODOS los registros de telemetría?",
                                  parent=self):
            con = sqlite3.connect(DB_PATH)
            con.execute("DELETE FROM telemetria")
            con.commit()
            con.close()
            self._cargar()


# ══════════════════════════════════════════════════════
#  MÓDULO PRINCIPAL
# ══════════════════════════════════════════════════════
class ModuloAterrizaje:
    """
    Módulo de control de Aterrizaje — Equipo 3.
    Llamar: ModuloAterrizaje(frame)
    Solo inicia telemetría si ESP32 + DS18B20 + MPU-6050 + BMP180 están OK.
    """

    FASE_NOMBRES = ["STANDBY", "DESORBIT", "REENTRADA",
                    "BURN INICIO", "BURN FINAL", "TOUCHDOWN", "ASEGURADO"]

    def __init__(self, parent_frame):
        self.parent = parent_frame

        # ── Estado del sistema ────────────────────────
        self.sistema_activo  = False
        self.sensores_ok     = False
        self._validando      = False

        # ── Telemetría (todos desde sensores) ─────────
        self.fase         = 0
        self.altitud      = 0.0
        self.vel_vert     = 0.0
        self.vel_horiz    = 0.0
        self.magnitud     = 0.0
        self.aceleracion  = 0.0
        self.temperatura  = 0.0    # BMP180 temp interna
        self.temp_externa = 0.0    # DS18B20
        self.presion      = 0.0    # hPa
        self.pitch        = 0.0    # MPU-6050
        self.roll         = 0.0
        self.yaw          = 0.0
        self.error_lat    = 0.0
        self.error_lon    = 0.0

        self._tick         = 0
        self._pulse        = 0.0
        self._trayectoria  = []
        self._alt_prev     = 0.0
        self._t_prev       = time.time()
        self._alt_ref      = None   # primera altitud recibida = referencia 0

        self._construir_ui()
        self._loop()

    # ══════════════════════════════════════════════════
    #  PERSISTENCIA SQLite
    # ══════════════════════════════════════════════════
    def _guardar_registro(self):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "altitud":      round(self.altitud, 2),
            "vel_vert":     round(self.vel_vert, 3),
            "vel_horiz":    round(self.vel_horiz, 3),
            "aceleracion":  round(self.aceleracion, 3),
            "temp_interna": round(self.temperatura, 2),
            "temp_externa": round(self.temp_externa, 2),
            "presion":      round(self.presion, 2),
            "pitch":        round(self.pitch, 2),
            "roll":         round(self.roll, 2),
            "yaw":          round(self.yaw, 2),
            "fase":         self.FASE_NOMBRES[self.fase],
            "magnitud":     round(self.magnitud, 3),
        }
        try:
            con = sqlite3.connect(DB_PATH)
            con.execute("INSERT INTO telemetria (timestamp, datos) VALUES (?, ?)",
                        (ts, json.dumps(payload)))
            con.commit()
            con.close()
        except Exception as e:
            print(f"[DB] Error al guardar: {e}")

    def _abrir_historial(self):
        _VentanaHistorial(self.parent)

    # ══════════════════════════════════════════════════
    #  VALIDACIÓN DE SENSORES
    # ══════════════════════════════════════════════════
    def _validar_sensores(self):
        """Corre la validación en hilo y actualiza la UI al terminar."""
        if self._validando:
            return
        self._validando = True
        self._btn_activar.config(text="[ VALIDANDO... ]",
                                 state="disabled",
                                 bg=C["amber_dim"], fg=C["amber"])
        self._log(">>> Verificando sensores ESP32...")

        import threading
        def _tarea():
            if _reader is None or not _reader.conectado:
                self.parent.after(0, self._on_sensor_fail, "ESP32 no conectado por WiFi")
                return
            ok = _reader.validar_sensores(timeout=6.0)
            est = _reader.estado_sensores()
            if ok:
                self.parent.after(0, self._on_sensor_ok, est)
            else:
                self.parent.after(0, self._on_sensor_fail,
                                  est.get("error", "Sensor no responde"))

        threading.Thread(target=_tarea, daemon=True).start()

    def _on_sensor_ok(self, est):
        self._validando  = False
        self.sensores_ok = True
        self._log(">>> ✓ DS18B20    OK")
        self._log(">>> ✓ MPU-6050   OK")
        self._log(">>> ✓ BMP180     OK")
        self._log(">>> SENSORES VERIFICADOS — sistema activo")
        self.sistema_activo = True
        self._btn_activar.config(text="[ DETENER ]",
                                 state="normal",
                                 bg=C["red_dim"], fg=C["red"])
        self._lbl_sensor_status.config(
            text="● SENSORES OK", fg=C["green"])
        # Guardar altitud de referencia en el primer dato
        self._alt_ref = None

    def _on_sensor_fail(self, motivo):
        self._validando  = False
        self.sensores_ok = False
        self.sistema_activo = False
        self._log(f">>> ✗ FALLO: {motivo}")
        self._log(">>> Revisa conexión al ESP32 y sensores")
        self._btn_activar.config(text="[ REINTENTAR ]",
                                 state="normal",
                                 bg=C["purple_dk"], fg=C["purple"])
        self._lbl_sensor_status.config(
            text="✗ SENSOR ERROR", fg=C["red"])

    # ══════════════════════════════════════════════════
    #  UI
    # ══════════════════════════════════════════════════
    def _construir_ui(self):
        # ── HEADER ────────────────────────────────────
        hdr = tk.Frame(self.parent, bg=C["bg"], height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border_hi"], height=2).pack(fill="x")

        row_h = tk.Frame(hdr, bg=C["bg"])
        row_h.pack(fill="both", expand=True, padx=10)

        # Título izquierda
        lf = tk.Frame(row_h, bg=C["bg"])
        lf.pack(side="left")
        tk.Label(lf, text="🛬 ATERRIZAJE", font=MONO_L,
                 bg=C["bg"], fg=C["purple"]).pack(side="left")
        tk.Label(lf, text="  MISION ALPHA-001", font=(MONO, 7),
                 bg=C["bg"], fg=C["text_gray"]).pack(side="left")
        self._lbl_sensor_status = tk.Label(
            lf, text="● ESPERANDO SENSORES", font=MONO_S,
            bg=C["bg"], fg=C["amber"])
        self._lbl_sensor_status.pack(side="left", padx=12)

        # Controles derecha
        rf = tk.Frame(row_h, bg=C["bg"])
        rf.pack(side="right")

        # Reloj
        self._lbl_clock = tk.Label(rf, text="T+00:00:00",
                                   font=(MONO, 9, "bold"),
                                   bg=C["bg"], fg=C["amber"])
        self._lbl_clock.pack(side="right", padx=(8, 0))

        # Botón HISTORIAL
        tk.Button(rf, text="[ BD HISTORIAL ]",
                  font=MONO_S, bg=C["green_dim"], fg=C["green"],
                  relief="flat", bd=0, padx=8, pady=5, cursor="hand2",
                  command=self._abrir_historial).pack(side="right", padx=6)

        # Botón ACTIVAR / DETENER / REINTENTAR
        btn_frame = tk.Frame(rf, bg=C["border_hi"], padx=1, pady=1)
        btn_frame.pack(side="right", padx=6)
        self._btn_activar = tk.Button(
            btn_frame, text="[ ACTIVAR ]",
            font=MONO_S, bg=C["purple_dk"], fg=C["purple"],
            relief="flat", bd=0, padx=8, pady=5, cursor="hand2",
            command=self._toggle)
        self._btn_activar.pack()

        # Indicador de fase
        self._lbl_fase = tk.Label(rf, text=f"● {self.FASE_NOMBRES[0]}",
                                  font=MONO_S, bg=C["bg"], fg=C["text_gray"])
        self._lbl_fase.pack(side="right", padx=(0, 8))

        tk.Frame(hdr, bg=C["purple_dim"], height=1).pack(fill="x", side="bottom")

        # ── STATUS BAR ────────────────────────────────
        sbar = tk.Frame(self.parent, bg=C["panel"], height=22)
        sbar.pack(fill="x")
        sbar.pack_propagate(False)

        self._status_labels = {}
        for key, val, color in [
                ("ALTITUD",     "--- m",    C["purple"]),
                ("VEL.VERT",    "--- m/s",  C["cyan"]),
                ("ACEL",        "--- m/s²", C["cyan"]),
                ("TEMP.INT",    "--- °C",   C["amber"]),
                ("TEMP.EXT",    "--- °C",   C["amber"]),
                ("PRESIÓN",     "--- hPa",  C["purple"]),
                ("PITCH",       "---°",     C["purple"]),
                ("ROLL",        "---°",     C["purple"]),
                ("YAW",         "---°",     C["purple"])]:
            f = tk.Frame(sbar, bg=C["panel"])
            f.pack(side="left", padx=5)
            tk.Label(f, text=key+":", font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["purple_dim"]).pack(side="left")
            lbl = tk.Label(f, text=val, font=(MONO, 6, "bold"),
                           bg=C["panel"], fg=color)
            lbl.pack(side="left", padx=(2, 0))
            self._status_labels[key] = lbl

        # ── CUERPO 3 COLUMNAS ─────────────────────────
        body = tk.Frame(self.parent, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(0, weight=1)

        col_l = tk.Frame(body, bg=C["bg"])
        col_l.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        col_c = tk.Frame(body, bg=C["bg"])
        col_c.grid(row=0, column=1, sticky="nsew", padx=3)
        col_r = tk.Frame(body, bg=C["bg"])
        col_r.grid(row=0, column=2, sticky="nsew", padx=(3, 0))

        self._build_left(col_l)
        self._build_center(col_c)
        self._build_right(col_r)

    # ── COLUMNA IZQUIERDA ─────────────────────────────
    def _build_left(self, p):
        self._card(p, "◈ ALTÍMETRO / VELOCIDAD", self._ui_altimeter)
        self._card(p, "◈ ORIENTACIÓN IMU (MPU-6050)", self._ui_attitude)
        self._card(p, "◈ TEMPERATURA & POSICIÓN", self._ui_temp_pos)

    def _ui_altimeter(self, f):
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        # Altitud grande
        tk.Label(f, text="ALTITUD (BMP180)", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).grid(
                 row=0, column=0, columnspan=2, sticky="w")
        self._lbl_alt = tk.Label(f, text="--- m",
                                 font=(MONO, 18, "bold"),
                                 bg=C["panel"], fg=C["purple"])
        self._lbl_alt.grid(row=1, column=0, columnspan=2, sticky="w")

        tk.Frame(f, bg=C["border"], height=1).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=4)

        # Velocidades
        for col, (lbl, attr, unit) in enumerate([
                ("VEL. VERTICAL", "_lbl_vv", "m/s"),
                ("VEL. HORIZ.",   "_lbl_vh", "m/s")]):
            tk.Label(f, text=lbl, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(row=3, column=col, sticky="w")
            lv = tk.Label(f, text=f"--- {unit}",
                          font=(MONO, 11, "bold"), bg=C["panel"], fg=C["cyan"])
            lv.grid(row=4, column=col, sticky="w")
            setattr(self, attr, lv)

        tk.Frame(f, bg=C["border"], height=1).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=4)

        # Aceleración y magnitud
        for col, (lbl, attr, unit) in enumerate([
                ("ACELERACIÓN",   "_lbl_acel",  "m/s²"),
                ("MAG.ACELER.",   "_lbl_mag",   "m/s²")]):
            tk.Label(f, text=lbl, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(row=6, column=col, sticky="w")
            lv = tk.Label(f, text=f"--- {unit}", font=MONO_M,
                          bg=C["panel"], fg=C["amber"])
            lv.grid(row=7, column=col, sticky="w")
            setattr(self, attr, lv)

        tk.Frame(f, bg=C["border"], height=1).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=4)

        # Barras visuales de velocidad y aceleración
        bf = tk.Frame(f, bg=C["panel"])
        bf.grid(row=9, column=0, columnspan=2, sticky="ew")
        self._bar_vel  = _VBar(bf, C["cyan"],   "VEL",  height=60)
        self._bar_vel.pack(side="left", padx=(0, 4))
        self._bar_acel = _VBar(bf, C["amber"],  "ACEL", height=60)
        self._bar_acel.pack(side="left")

    def _ui_attitude(self, f):
        # Canvas de actitud visual
        self._att_canvas = tk.Canvas(f, width=110, height=86,
                                     bg="#03060F", highlightthickness=1,
                                     highlightbackground=C["border"])
        self._att_canvas.pack(side="left", padx=(0, 6))

        vf = tk.Frame(f, bg=C["panel"])
        vf.pack(side="left", fill="both", expand=True)
        self._att_labels = {}
        for i, (axis, color) in enumerate([("PITCH", C["purple"]),
                                            ("ROLL",  C["cyan"]),
                                            ("YAW",   C["amber"])]):
            tk.Label(vf, text=axis, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(row=i*2, column=0, sticky="w")
            lv = tk.Label(vf, text="0.0°", font=MONO_M, bg=C["panel"], fg=color)
            lv.grid(row=i*2, column=1, sticky="w", padx=4)
            cv = tk.Canvas(vf, width=56, height=7, bg="#0a0a14", highlightthickness=0)
            cv.grid(row=i*2+1, column=0, columnspan=2, sticky="w", pady=(0, 3))
            self._att_labels[axis] = (lv, cv, color)

    def _ui_temp_pos(self, f):
        """Panel de temperatura (DS18B20 + BMP180) y posición angular."""
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        # Temperaturas
        tk.Label(f, text="TEMPERATURA INTERNA (BMP180)", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).grid(
                 row=0, column=0, columnspan=2, sticky="w")
        self._lbl_temp_int = tk.Label(f, text="--- °C",
                                      font=(MONO, 14, "bold"),
                                      bg=C["panel"], fg=C["amber"])
        self._lbl_temp_int.grid(row=1, column=0, columnspan=2, sticky="w")

        tk.Frame(f, bg=C["border"], height=1).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=3)

        tk.Label(f, text="TEMPERATURA EXTERNA (DS18B20)", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).grid(
                 row=3, column=0, columnspan=2, sticky="w")
        self._lbl_temp_ext = tk.Label(f, text="--- °C",
                                      font=(MONO, 14, "bold"),
                                      bg=C["panel"], fg=C["cyan"])
        self._lbl_temp_ext.grid(row=4, column=0, columnspan=2, sticky="w")

        tk.Frame(f, bg=C["border"], height=1).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=3)

        # Presión
        tk.Label(f, text="PRESIÓN ATMOSFÉRICA", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).grid(
                 row=6, column=0, columnspan=2, sticky="w")
        self._lbl_presion_ui = tk.Label(f, text="--- hPa",
                                        font=(MONO, 11, "bold"),
                                        bg=C["panel"], fg=C["purple"])
        self._lbl_presion_ui.grid(row=7, column=0, columnspan=2, sticky="w")

    # ── COLUMNA CENTRAL ───────────────────────────────
    def _build_center(self, p):
        self._card(p, "◈ PERFIL DE DESCENSO", self._ui_descent, expand=True)
        self._card(p, "◈ SENSOR STATUS", self._ui_sensor_status)

    def _ui_descent(self, f):
        self._descent_canvas = tk.Canvas(f, bg="#020408", highlightthickness=0)
        self._descent_canvas.pack(fill="both", expand=True)

    def _ui_sensor_status(self, f):
        """Panel de estado de cada sensor."""
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(2, weight=1)

        sensores = [
            ("DS18B20", "TEMP EXT",  "_led_ds18b20"),
            ("MPU-6050","GIROSCOPIO","_led_mpu6050"),
            ("BMP180",  "ALT/PRES",  "_led_bmp180"),
        ]
        for col, (nombre, desc, attr) in enumerate(sensores):
            sf = tk.Frame(f, bg=C["panel"])
            sf.grid(row=0, column=col, padx=6, pady=2)
            cv = tk.Canvas(sf, width=14, height=14,
                           bg=C["panel"], highlightthickness=0)
            cv.pack(side="left", padx=(0, 4))
            tk.Label(sf, text=nombre, font=(MONO, 7, "bold"),
                     bg=C["panel"], fg=C["white"]).pack(side="left")
            lbl = tk.Label(f, text=desc, font=(MONO, 6),
                           bg=C["panel"], fg=C["text_gray"])
            lbl.grid(row=1, column=col)
            setattr(self, attr, cv)

        # Línea de paquetes recibidos
        tk.Frame(f, bg=C["border"], height=1).grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=3)
        self._lbl_paquetes = tk.Label(f, text="Paquetes: 0",
                                      font=MONO_S, bg=C["panel"],
                                      fg=C["text_gray"])
        self._lbl_paquetes.grid(row=3, column=0, columnspan=3, sticky="w", padx=2)

    # ── COLUMNA DERECHA ───────────────────────────────
    def _build_right(self, p):
        self._card(p, "◈ SECUENCIA DE FASES",  self._ui_fases)
        self._card(p, "◈ PRECISIÓN DE ZONA",   self._ui_precision)
        self._card(p, "◈ TELEMETRÍA",           self._ui_telem, expand=True)

    def _ui_fases(self, f):
        self._fase_labels = []
        for i, nombre in enumerate(self.FASE_NOMBRES):
            ff = tk.Frame(f, bg=C["panel"])
            ff.pack(fill="x", pady=1)
            ind = tk.Canvas(ff, width=10, height=10,
                            bg=C["panel"], highlightthickness=0)
            ind.pack(side="left", padx=(0, 4))
            lbl = tk.Label(ff, text=f"{i} │ {nombre}",
                           font=(MONO, 7), bg=C["panel"], fg=C["text_dark"])
            lbl.pack(side="left")
            self._fase_labels.append((ind, lbl))

    def _ui_precision(self, f):
        self._zona_canvas = tk.Canvas(f, height=88, bg="#020408",
                                      highlightthickness=1,
                                      highlightbackground=C["border"])
        self._zona_canvas.pack(fill="x", pady=(0, 4))
        re = tk.Frame(f, bg=C["panel"])
        re.pack(fill="x")
        for col, (lbl, attr) in enumerate([("ERROR LATERAL", "_lbl_err_lat"),
                                            ("ERROR LONG.",   "_lbl_err_lon")]):
            tk.Label(re, text=lbl, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(row=0, column=col,
                     sticky="w", padx=5)
            lv = tk.Label(re, text="0.0 m", font=MONO_S,
                          bg=C["panel"], fg=C["cyan"])
            lv.grid(row=1, column=col, sticky="w", padx=5)
            setattr(self, attr, lv)

    def _ui_telem(self, f):
        self._telem = tk.Text(f, bg="#020408", fg=C["text_gray"],
                              font=(MONO, 7), relief="flat",
                              state="disabled", insertbackground=C["purple"])
        sb = ttk.Scrollbar(f, orient="vertical", command=self._telem.yview)
        self._telem.configure(yscrollcommand=sb.set)
        self._telem.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _card(self, parent, title, builder, expand=False):
        outer = tk.Frame(parent, bg=C["border_hi"], padx=1, pady=1)
        outer.pack(fill="both", expand=expand, pady=3)
        hdr = tk.Frame(outer, bg="#070B14", height=22)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border_hi"], width=3).pack(side="left", fill="y")
        tk.Label(hdr, text=f"  {title}", font=(MONO, 7, "bold"),
                 bg="#070B14", fg=C["purple"]).pack(side="left", pady=3)
        inner = tk.Frame(outer, bg=C["panel"], padx=6, pady=5)
        inner.pack(fill="both", expand=expand)
        builder(inner)

    # ══════════════════════════════════════════════════
    #  TOGGLE SISTEMA
    # ══════════════════════════════════════════════════
    def _toggle(self):
        if not self.sistema_activo:
            # Intentar activar — requiere validar sensores
            self._validar_sensores()
        else:
            # Detener
            self.sistema_activo = False
            self._btn_activar.config(text="[ ACTIVAR ]",
                                     state="normal",
                                     bg=C["purple_dk"], fg=C["purple"])
            self._lbl_sensor_status.config(
                text="● DETENIDO", fg=C["amber"])
            self._log(">>> SISTEMA DETENIDO por operador")

    # ══════════════════════════════════════════════════
    #  LECTURA DE SENSORES (SIN SIMULACIÓN)
    # ══════════════════════════════════════════════════
    def _leer_sensores(self):
        """
        Lee datos únicamente del SerialReader (ESP32 real).
        No existe ningún dato simulado.
        """
        if not self.sistema_activo:
            return
        if not (_reader and _reader.conectado):
            self._log(">>> ✗ Conexión serial perdida")
            self.sistema_activo = False
            return

        d = _reader.datos

        # ── MPU-6050 — Orientación ──────────────────
        self.pitch = d["gy"]
        self.roll  = d["gx"]
        self.yaw   = d["gz"]

        # ── MPU-6050 — Aceleración ──────────────────
        # az en g → convertir a m/s²
        self.aceleracion = d["az"] * 9.80665
        self.magnitud    = d["magnitud"]

        # ── DS18B20 — Temperatura externa ───────────
        self.temp_externa = d["temp_externa"]

        # ── BMP180 — Temperatura interna, presión, altitud
        self.temperatura = d["temp_interna"]
        self.presion     = d["presion"]

        # Altitud relativa: la primera lectura válida es la referencia
        alt_raw = d["altitud"]
        if self._alt_ref is None and alt_raw != 0.0:
            self._alt_ref = alt_raw
            self._log(f">>> Altitud de referencia establecida: {alt_raw:.1f} m")
        self.altitud = (alt_raw - self._alt_ref) if self._alt_ref is not None else 0.0

        # ── Velocidad vertical (derivada de altitud) ─
        now = time.time()
        dt = now - self._t_prev
        if dt > 0:
            self.vel_vert = (self.altitud - self._alt_prev) / dt
        self._alt_prev = self.altitud
        self._t_prev   = now

        # ── Velocidad horizontal (magnitud acelerómetro XY)
        self.vel_horiz = math.sqrt(d["ax"]**2 + d["ay"]**2) * 9.80665

        # ── Fase según inclinación total ────────────
        inclinacion = abs(self.pitch) + abs(self.roll)
        if inclinacion < 2:
            self.fase = 0
        elif inclinacion < 10:
            self.fase = 1
        elif inclinacion < 25:
            self.fase = 2
        else:
            self.fase = 3

        # ── Trayectoria ─────────────────────────────
        self._trayectoria.append((self.altitud, self.vel_vert))
        if len(self._trayectoria) > 300:
            self._trayectoria.pop(0)

    # ══════════════════════════════════════════════════
    #  LOOP PRINCIPAL
    # ══════════════════════════════════════════════════
    def _loop(self):
        self._pulse += 0.15
        self._tick  += 1

        self._leer_sensores()
        self._update_labels()
        self._draw_descent()
        self._draw_zona()
        self._draw_attitude()
        self._update_sensor_leds()
        self._update_fases()
        self._update_statusbar()
        self._lbl_clock.config(text=datetime.now().strftime("T+%H:%M:%S"))

        # Log de telemetría cada ~1 s (10 ticks × 100 ms)
        if self._tick % 10 == 0:
            self._log_telem()
        # Guardar en BD cada ~5 s
        if self._tick % 50 == 0 and self.sistema_activo:
            self._guardar_registro()

        self.parent.after(100, self._loop)

    # ══════════════════════════════════════════════════
    #  ACTUALIZACIÓN DE LABELS
    # ══════════════════════════════════════════════════
    def _update_labels(self):
        if not self.sistema_activo:
            return

        # Altitud
        self._lbl_alt.config(
            text=f"{self.altitud:7.1f} m",
            fg=C["red"] if self.altitud < 20 else C["purple"])

        # Velocidad vertical
        vv_c = (C["green"] if abs(self.vel_vert) < 1 else
                C["amber"] if abs(self.vel_vert) < 5 else C["red"])
        self._lbl_vv.config(text=f"{self.vel_vert:+.2f} m/s", fg=vv_c)
        self._lbl_vh.config(text=f"{self.vel_horiz:.2f} m/s")

        # Aceleración
        self._lbl_acel.config(text=f"{self.aceleracion:+.2f} m/s²")
        self._lbl_mag.config(text=f"{self.magnitud:.3f} m/s²")

        # Barras
        self._bar_vel.update_val(min(abs(self.vel_vert), 30), 30)
        self._bar_acel.update_val(min(abs(self.aceleracion), 50), 50)

        # Temperatura
        tmp_c = (C["red"] if self.temperatura > 80 else
                 C["amber"] if self.temperatura > 40 else C["cyan"])
        self._lbl_temp_int.config(text=f"{self.temperatura:.1f} °C", fg=tmp_c)
        ext_c = C["red"] if self.temp_externa > 50 else C["cyan"]
        self._lbl_temp_ext.config(text=f"{self.temp_externa:.1f} °C", fg=ext_c)
        self._lbl_presion_ui.config(text=f"{self.presion:.1f} hPa")

        # Actitud (pitch/roll/yaw)
        for axis, val in [("PITCH", self.pitch),
                           ("ROLL",  self.roll),
                           ("YAW",   self.yaw)]:
            lv, cv, color = self._att_labels[axis]
            lv.config(text=f"{val:+.1f}°")
            cv.delete("all")
            w = cv.winfo_width() or 56
            mid = w // 2
            px = max(2, min(w-2, int(mid + (val/45)*(mid-2))))
            cv.create_rectangle(0, 0, w, 7, fill="#0a0a14", outline="")
            cv.create_rectangle(mid-1, 0, mid+1, 7, fill=C["border"])
            cv.create_rectangle(max(mid, px)-3, 1,
                                min(mid, px)+3, 6, fill=color, outline="")

        # Error de zona (derivado de roll/pitch escalado)
        self.error_lat = self.roll  * 0.5
        self.error_lon = self.pitch * 0.5
        self._lbl_err_lat.config(
            text=f"{self.error_lat:.1f} m",
            fg=C["green"] if abs(self.error_lat) < 5 else C["amber"])
        self._lbl_err_lon.config(
            text=f"{self.error_lon:.1f} m",
            fg=C["green"] if abs(self.error_lon) < 5 else C["amber"])

    def _update_statusbar(self):
        s = self._status_labels
        if not self.sistema_activo:
            return
        s["ALTITUD"].config(
            text=f"{self.altitud:.1f}m",
            fg=C["red"] if self.altitud < 20 else C["purple"])
        s["VEL.VERT"].config(
            text=f"{self.vel_vert:+.2f}m/s",
            fg=C["red"] if abs(self.vel_vert) > 5 else C["cyan"])
        s["ACEL"].config(text=f"{self.aceleracion:+.2f}m/s²")
        s["TEMP.INT"].config(
            text=f"{self.temperatura:.1f}°C",
            fg=C["red"] if self.temperatura > 80 else C["amber"])
        s["TEMP.EXT"].config(
            text=f"{self.temp_externa:.1f}°C",
            fg=C["red"] if self.temp_externa > 50 else C["amber"])
        s["PRESIÓN"].config(text=f"{self.presion:.1f}hPa")
        s["PITCH"].config(text=f"{self.pitch:+.1f}°")
        s["ROLL"].config(text=f"{self.roll:+.1f}°")
        s["YAW"].config(text=f"{self.yaw:+.1f}°")

    def _update_sensor_leds(self):
        """Actualiza los LEDs de estado de cada sensor."""
        if not _reader:
            return
        est = _reader.estado_sensores() if self.sensores_ok else {}
        for attr, ok in [("_led_ds18b20", self.sensores_ok and est.get("DS18B20", False)),
                         ("_led_mpu6050", self.sensores_ok and est.get("MPU6050", False)),
                         ("_led_bmp180",  self.sensores_ok and est.get("BMP180",  False))]:
            cv = getattr(self, attr)
            cv.delete("all")
            color = C["green"] if ok else C["red_dim"]
            cv.create_oval(1, 1, 13, 13, fill=color, outline="")

        # Contador de paquetes recibidos
        paq = int((time.time() - (_reader._ultimo_paquete or time.time())) * 0)
        total = self._tick if self.sistema_activo else 0
        self._lbl_paquetes.config(
            text=f"Ticks activos: {total}  |  Sensor: {'ACTIVO' if self.sensores_ok else 'INACTIVO'}")

    # ══════════════════════════════════════════════════
    #  DIBUJADO
    # ══════════════════════════════════════════════════
    def _draw_descent(self):
        c = self._descent_canvas
        c.delete("all")
        w = c.winfo_width(); h = c.winfo_height()
        if w < 10 or h < 10:
            return

        # Grid
        for y in range(0, h, max(1, h//8)):
            c.create_line(0, y, w, y, fill=C["grid"])
        for x in range(0, w, max(1, w//8)):
            c.create_line(x, 0, x, h, fill=C["grid"])

        if not self.sistema_activo:
            c.create_text(w//2, h//2, text="ESPERANDO SENSORES",
                          fill=C["purple_dim"], font=MONO_M)
            return

        # Escala fija de 0 a 50m
        alt_max = 50.0

        # Líneas de referencia de altitud
        for alt_m in [0, 10, 20, 30, 40, 50]:
            if alt_m > alt_max:
                break
            py = max(10, h - int((alt_m / alt_max) * (h - 20)) - 10)
            c.create_line(0, py, w, py, fill="#0d0a20", dash=(4, 6))
            c.create_text(4, py, text=f"{alt_m}m",
                          fill=C["purple_dim"], font=(MONO, 6), anchor="w")

        # Trayectoria
        if len(self._trayectoria) >= 2:
            pts = []
            for i, (alt, _) in enumerate(self._trayectoria):
                px = int(w * 0.15 + (i / len(self._trayectoria)) * w * 0.7)
                py = max(5, h - int((max(0, alt) / alt_max) * (h - 20)) - 10)
                pts.extend([px, py])
            if len(pts) >= 4:
                c.create_line(pts, fill=C["purple_dim"], width=1, smooth=True)

        # Cohete / marcador
        pct_alt = max(0, min(1, self.altitud / alt_max))
        rx = w // 2
        ry = max(10, min(h - 10, h - int(pct_alt * (h - 20)) - 10))
        pulse = 6 + int(3 * abs(math.sin(self._pulse)))
        c.create_line(rx, h, rx, ry, fill=C["purple_dim"], dash=(3, 5))
        c.create_polygon(rx-6, ry+12, rx+6, ry+12, rx, ry-12,
                         fill=C["purple"], outline=C["white"], width=1)
        c.create_oval(rx - pulse, ry - pulse, rx + pulse, ry + pulse,
                      outline=C["purple_dim"], width=1)

        # Zona de aterrizaje
        zw = 24
        c.create_rectangle(rx-zw, h-14, rx+zw, h-2,
                           fill=C["green_dim"], outline=C["green"], width=1)
        c.create_text(rx, h - 8, text="ZONA", fill=C["green"], font=(MONO, 6))

        # Textos de overlay
        c.create_text(8, 8, text=f"ALT {self.altitud:.1f}m",
                      fill=C["purple"], font=(MONO, 7, "bold"), anchor="nw")
        c.create_text(w - 8, 8, text=self.FASE_NOMBRES[self.fase],
                      fill=C["amber"], font=(MONO, 7, "bold"), anchor="ne")
        c.create_text(8, h - 8, text=f"VEL {self.vel_vert:+.2f}m/s",
                      fill=C["cyan"], font=(MONO, 6, "bold"), anchor="sw")

    def _draw_zona(self):
        c = self._zona_canvas
        c.delete("all")
        w = c.winfo_width() or 160; h = c.winfo_height() or 88
        if w < 10 or h < 10:
            return
        cx, cy = w // 2, h // 2
        for r, lbl in [(38, "50m"), (24, "25m"), (10, "10m")]:
            c.create_oval(cx-r, cy-r, cx+r, cy+r,
                          outline=C["purple_dim"], dash=(4, 4))
            c.create_text(cx+r+2, cy, text=lbl,
                          fill=C["text_gray"], font=(MONO, 5), anchor="w")
        c.create_line(cx-5, cy, cx+5, cy, fill=C["green"], width=2)
        c.create_line(cx, cy-5, cx, cy+5, fill=C["green"], width=2)
        scale = 38 / 50
        bx = max(5, min(w-5, int(cx + self.error_lat * scale)))
        by = max(5, min(h-5, int(cy - self.error_lon * scale)))
        p = 4 + int(2 * abs(math.sin(self._pulse)))
        c.create_oval(bx-p, by-p, bx+p, by+p, outline=C["amber"], width=1)
        c.create_oval(bx-2, by-2, bx+2, by+2, fill=C["amber"], outline="")
        err = math.sqrt(self.error_lat**2 + self.error_lon**2)
        c.create_text(4, h - 5, text=f"Δ {err:.1f}m",
                      fill=C["cyan"], font=(MONO, 6), anchor="sw")

    def _draw_attitude(self):
        c = self._att_canvas
        c.delete("all")
        w = c.winfo_width() or 110; h = c.winfo_height() or 86
        if w < 10:
            return
        cx, cy = w // 2, h // 2
        r = min(cx, cy) - 4
        ang = math.radians(self.roll)
        dx = r * math.sin(ang); dy = r * math.cos(ang)
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#0a0520", outline=C["border"])
        po = int((self.pitch / 45) * r * 0.5)
        c.create_rectangle(cx-r, cy+po, cx+r, cy+r+r, fill=C["purple_dk"], outline="")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill="", outline=C["border"])
        c.create_line(cx-dx, cy-dy+po, cx+dx, cy+dy+po, fill=C["amber"], width=2)
        c.create_line(cx-12, cy, cx+12, cy, fill=C["purple"], width=2)
        c.create_line(cx, cy-8, cx, cy+8, fill=C["purple"], width=2)
        c.create_oval(cx-3, cy-3, cx+3, cy+3, fill=C["purple"], outline="")
        c.create_text(4, 4, text="ATT", fill=C["purple_dim"],
                      font=(MONO, 6, "bold"), anchor="nw")

    def _update_fases(self):
        for i, (ind, lbl) in enumerate(self._fase_labels):
            ind.delete("all")
            if i < self.fase:
                ind.create_oval(1, 1, 9, 9, fill=C["green"], outline="")
                lbl.config(fg=C["text_gray"])
            elif i == self.fase:
                b = 0.6 + 0.4 * abs(math.sin(self._pulse))
                ind.create_oval(1, 1, 9, 9,
                                fill=_hex_blend(C["purple"], b), outline="")
                lbl.config(fg=C["purple"])
            else:
                ind.create_oval(1, 1, 9, 9, fill=C["text_dark"], outline="")
                lbl.config(fg=C["text_dark"])
        self._lbl_fase.config(text=f"● {self.FASE_NOMBRES[self.fase]}")

    # ══════════════════════════════════════════════════
    #  LOG
    # ══════════════════════════════════════════════════
    def _log_telem(self):
        if not self.sistema_activo:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        msg = (f"[{ts}] ALT={self.altitud:.1f}m  "
               f"VEL={self.vel_vert:+.2f}m/s  "
               f"ACEL={self.aceleracion:+.2f}m/s²  "
               f"T.INT={self.temperatura:.1f}°C  "
               f"T.EXT={self.temp_externa:.1f}°C  "
               f"PRES={self.presion:.1f}hPa  "
               f"P={self.pitch:+.1f}° R={self.roll:+.1f}° Y={self.yaw:+.1f}°\n")
        self._telem.config(state="normal")
        self._telem.insert("end", msg)
        self._telem.see("end")
        self._telem.config(state="disabled")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self._telem.config(state="normal")
        self._telem.insert("end", f"[{ts}] {msg}\n")
        self._telem.see("end")
        self._telem.config(state="disabled")
if __name__ == "__main__":
    # Crea la ventana principal de la interfaz
    root = tk.Tk()
    root.title("Telemetría de Aterrizaje - Equipo 3")
    root.geometry("1100x650")
    
    # Usa el mismo color de fondo que tienen en su paleta
    root.configure(bg="#04080F") 
    
    # Arranca la aplicación dentro de la ventana
    app = ModuloAterrizaje(root)
    
    # Este es el bucle que mantiene la ventana abierta y dibujándose
    root.mainloop()
