
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import threading
import socket
import json
import sqlite3
import csv
import os

import shared_state

# Puerto UDP donde el simulador manda telemetria al modulo de despegue
ESP32_HOST        = "127.0.0.1"
ESP32_CMD_PORT    = 9090          # uplink: despegue -> ESP32 (comandos)
DESPEGUE_UDP_PORT = 9091          # downlink: ESP32 -> despegue (telemetria)

DB_PATH          = "despegue_sesiones.db"
JSON_PATH        = "ultimo_estado.json"

# Umbral mínimo de calidad de señal RF para considerar el enlace usable (%)
SIGNAL_MIN_PCT   = 40

BG_ROOT   = "#04080F"
BG_CARD   = "#0C1624"
BG_CARD2  = "#0A1220"
BG_INPUT  = "#060D18"
CYAN      = "#00D4FF"
GREEN     = "#00FF88"
RED       = "#FF2D55"
AMBER     = "#FFB800"
BLUE_LT   = "#1E90FF"
TEXT_GRAY = "#4A6080"
TEXT_DARK = "#1E2D40"
BORDER    = "#122035"
BORDER_C  = "#0A4060"
MONO      = "Courier New"


def make_card(parent, title, accent=CYAN, expand=False):
    outer = tk.Frame(parent, bg=accent, bd=1)
    outer.pack(fill="x", pady=3)
    hdr = tk.Frame(outer, bg="#061020", height=30)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Frame(hdr, bg=accent, width=4).pack(side="left", fill="y")
    tk.Label(hdr, text=f"  {title}", font=(MONO, 8, "bold"),
             bg="#061020", fg=accent, anchor="w").pack(side="left", fill="y")
    tk.Frame(outer, bg=accent, height=1).pack(fill="x")
    inner = tk.Frame(outer, bg=BG_CARD, padx=10, pady=8)
    inner.pack(fill="both", expand=expand)
    return inner


class ModuloDespegue:

    def __init__(self, parent_frame):
        self.parent = parent_frame
        self._running = True

        self.system_on        = False
        self.wifi_strength    = 0
        self.signal_quality   = 0
        self.wind_speed       = 0.0
        self.rocket_connected = False
        self.signal_verified  = False
        self.link_confirmed   = False
        self.launch_armed     = False
        self.launch_active    = False

        # Cola thread-safe para pasar datos del listener UDP al hilo de Tkinter
        self._udp_queue = []
        self._udp_lock  = threading.Lock()
        self._udp_err_count = 0   # contador de errores UDP visible en UI

        self.var_wifi  = tk.StringVar(value="0%")
        self.var_sig   = tk.StringVar(value="0%")
        self.var_wind  = tk.StringVar(value="0.0 km/h")
        self.var_state = tk.StringVar(value="STANDBY")

        self._db_init()
        self._build_header()

        main = tk.Frame(self.parent, bg=BG_ROOT)
        main.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self.left = tk.Frame(main, bg=BG_ROOT)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.right = tk.Frame(main, bg=BG_ROOT, width=200)
        self.right.pack(side="right", fill="both")
        self.right.pack_propagate(False)

        self._build_wifi_panel()
        self._build_device_panel()
        self._build_signal_panel()
        self._build_link_panel()
        self._build_launch_panel()
        self._build_wind_panel()
        self._build_telemetry_panel()

        # Arrancar listener UDP en hilo separado
        self._start_udp_listener()

        self._poll_shared_state()
        self._process_udp_queue()
        self._tick_clock()
        self._log("Modulo Despegue listo. Presiona ENCENDER para iniciar.", "SYS", CYAN)
        self._log(f"Escuchando telemetria UDP en puerto {DESPEGUE_UDP_PORT}...", "UDP", TEXT_GRAY)

    # ── UDP LISTENER REAL ─────────────────────────────────────────

    def _start_udp_listener(self):
        """Abre un socket UDP real y recibe paquetes del simulador ESP32."""
        def _listen():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", DESPEGUE_UDP_PORT))
                sock.settimeout(1.0)
                while self._running:
                    try:
                        data, addr = sock.recvfrom(4096)
                        try:
                            pkt = json.loads(data.decode("utf-8"))
                            with self._udp_lock:
                                self._udp_queue.append(pkt)
                        except json.JSONDecodeError:
                            pass
                    except socket.timeout:
                        continue
                sock.close()
            except OSError as e:
                with self._udp_lock:
                    self._udp_queue.append({"_error": str(e)})

        t = threading.Thread(target=_listen, daemon=True)
        t.start()

    def _process_udp_queue(self):
        """Procesa paquetes UDP recibidos en el hilo principal de Tkinter."""
        with self._udp_lock:
            packets = list(self._udp_queue)
            self._udp_queue.clear()

        for pkt in packets:
            if "_error" in pkt:
                self._udp_err_count += 1
                self._log(f"UDP listener error: {pkt['_error']}", "UDP", RED)
                if hasattr(self, "lbl_udp_err"):
                    self.lbl_udp_err.config(
                        text=f"ERR UDP: {self._udp_err_count}",
                        fg=RED)
                continue
            self._ingest_packet(pkt)

        self.parent.after(200, self._process_udp_queue)

    def _ingest_packet(self, pkt):
        """
        Parsea el paquete del simulador y actualiza shared_state con datos reales.
        El simulador envia: altitud, velocidad, bateria, rssi, latitud, longitud,
        fase, temp_int, temp_ext, presion, ax/ay/az, gx/gy/gz, hora_gps, distancia.
        """
        # RSSI -> wifi_strength y signal_quality (dato real del simulador)
        rssi = pkt.get("rssi", None)
        if rssi is not None:
            shared_state.set("wifi_strength", int(rssi))
            shared_state.set("signal_quality", int(rssi))

        altitud   = pkt.get("altitud",   None)
        velocidad = pkt.get("velocidad", None)
        bateria   = pkt.get("bateria",   None)
        latitud   = pkt.get("latitud",   None)
        longitud  = pkt.get("longitud",  None)
        hora_gps  = pkt.get("hora_gps",  None)
        distancia = pkt.get("distancia", None)
        fase      = pkt.get("fase",      None)

        if altitud   is not None: shared_state.set("altitud",   float(altitud))
        if velocidad is not None: shared_state.set("velocidad", float(velocidad))
        if latitud   is not None: shared_state.set("latitud",   float(latitud))
        if longitud  is not None: shared_state.set("longitud",  float(longitud))
        if hora_gps  is not None: shared_state.set("hora_gps",  hora_gps)
        if distancia is not None: shared_state.set("distancia", float(distancia))

        # Bateria como porcentaje formateado
        if bateria is not None:
            shared_state.set("bateria",         float(bateria))
            shared_state.set("bateria_cohete",  f"{bateria:.1f}%")

        # GPS: OK si tenemos coordenadas validas
        if latitud is not None and longitud is not None:
            shared_state.set("gps_estado", "OK")

        # Giroscopio: OK si llegaron datos IMU
        if pkt.get("gx") is not None:
            shared_state.set("giroscopio", "OK")

        # Altimetro: muestra la altitud actual
        if altitud is not None:
            shared_state.set("altimetro", f"{altitud:.1f} m")

        # Propulsion y telemetria segun la fase de vuelo
        if fase is not None:
            if fase == "STANDBY":
                shared_state.set("propulsion", "EN ESPERA")
                shared_state.set("telemetria", "ACTIVA")
            elif fase in ("ASCENSO", "APOGEO"):
                shared_state.set("propulsion", "OK")
                shared_state.set("telemetria", "ACTIVA")
            else:
                shared_state.set("propulsion", fase)
                shared_state.set("telemetria", "ACTIVA")

        # Viento estimado desde velocidad horizontal (no viene directo del simulador)
        vel = pkt.get("vel_vert", None)
        if vel is not None:
            viento_est = max(0.0, abs(float(vel)) * 0.3)
            shared_state.set("wind_speed", round(viento_est, 1))

    # ── BASE DE DATOS ─────────────────────────────────────────────

    def _db_init(self):
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS sesiones (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT,
                evento      TEXT,
                detalle     TEXT,
                wifi_pct    INTEGER,
                signal_pct  INTEGER,
                viento      REAL,
                estado      TEXT
            )
        """)
        self.db.commit()

    def _db_insert(self, evento, detalle=""):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.db.execute(
            "INSERT INTO sesiones "
            "(timestamp, evento, detalle, wifi_pct, signal_pct, viento, estado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, evento, detalle,
             self.wifi_strength, self.signal_quality,
             self.wind_speed, self.var_state.get())
        )
        self.db.commit()

    def _db_query_all(self):
        cur = self.db.execute(
            "SELECT timestamp, evento, detalle, wifi_pct, signal_pct, viento, estado "
            "FROM sesiones ORDER BY id DESC LIMIT 200"
        )
        return cur.fetchall()

    # ── JSON SAVE / LOAD ──────────────────────────────────────────

    def _save_json(self):
        data = {
            "version":        "1.0",
            "guardado":       time.strftime("%Y-%m-%d %H:%M:%S"),
            "estado":         self.var_state.get(),
            "wifi_strength":  self.wifi_strength,
            "signal_quality": self.signal_quality,
            "wind_speed":     self.wind_speed,
            "rocket_connected": self.rocket_connected,
            "signal_verified":  self.signal_verified,
            "link_confirmed":   self.link_confirmed,
            "launch_active":    self.launch_active,
            "shared_snapshot":  shared_state.snapshot(),
            # Subsistemas leídos desde shared_state (fuente de verdad), no desde los labels de UI
            "subsistemas": {
                "BATERIA":     shared_state.get("bateria_cohete", "N/A"),
                "GPS":         shared_state.get("gps_estado",    "N/A"),
                "GIROSCOPIO":  shared_state.get("giroscopio",    "N/A"),
                "ALTIMETRO":   shared_state.get("altimetro",     "N/A"),
                "PROPULSION":  shared_state.get("propulsion",    "N/A"),
                "TELEMETRIA":  shared_state.get("telemetria",    "N/A"),
            }
        }
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=JSON_PATH,
            title="Guardar estado de sesion"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._log(f"Estado guardado: {os.path.basename(path)}", "JSON", GREEN)
        self._db_insert("JSON_SAVE", path)

    def _load_json(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")],
            title="Cargar estado de sesion"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            messagebox.showerror("Error JSON", f"No se pudo leer el archivo:\n{e}")
            return

        self.var_state.set(data.get("estado", "STANDBY"))
        self.wifi_strength  = data.get("wifi_strength", 0)
        self.signal_quality = data.get("signal_quality", 0)
        self.wind_speed     = data.get("wind_speed", 0.0)

        # Restaurar shared_state desde el snapshot guardado
        snap = data.get("shared_snapshot", {})
        if snap:
            shared_state.update(snap)

        for k, txt in data.get("subsistemas", {}).items():
            if k in self.subsys:
                col = GREEN if ("OK" in txt or "%" in txt) else TEXT_DARK
                self.subsys[k].config(text=txt, fg=col)

        self.var_wifi.set(f"{self.wifi_strength}%")
        self.var_sig.set(f"{self.signal_quality}%")
        self._draw_wifi(self.wifi_strength)
        self._log(
            f"Estado cargado: {os.path.basename(path)} "
            f"(guardado {data.get('guardado', '-')})",
            "JSON", CYAN
        )
        self._db_insert("JSON_LOAD", path)

    # ── EXPORTAR CSV / TXT ────────────────────────────────────────

    def _export_csv(self):
        rows = self._db_query_all()
        if not rows:
            messagebox.showinfo("Sin datos", "No hay eventos registrados en esta sesion.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="despegue_log.csv",
            title="Exportar log CSV"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "evento", "detalle", "wifi%", "signal%", "viento_kmh", "estado"])
            w.writerows(rows)
        self._log(f"CSV exportado: {os.path.basename(path)} ({len(rows)} filas)", "RPT", GREEN)

    def _export_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="despegue_log.txt",
            title="Exportar log TXT"
        )
        if not path:
            return
        t = self.telem_text
        t.config(state="normal")
        contenido = t.get("1.0", "end")
        t.config(state="disabled")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Log de Despegue -- Mision Alpha-001\n")
            f.write(f"Exportado: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 50 + "\n")
            f.write(contenido)
        self._log(f"TXT exportado: {os.path.basename(path)}", "RPT", GREEN)

    # ── INTERFAZ ──────────────────────────────────────────────────

    def _build_header(self):
        h = tk.Frame(self.parent, bg="#020609", height=50)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Frame(h, bg=CYAN, height=2).pack(fill="x")

        row = tk.Frame(h, bg="#020609")
        row.pack(fill="both", expand=True, padx=10)

        tk.Label(row, text="DESPEGUE",
                 font=(MONO, 11, "bold"), bg="#020609", fg=CYAN).pack(side="left")
        tk.Label(row, text="  MISION ALPHA-001  //  UDP:" + str(DESPEGUE_UDP_PORT),
                 font=(MONO, 7), bg="#020609", fg=TEXT_GRAY).pack(side="left")

        r = tk.Frame(row, bg="#020609")
        r.pack(side="right")

        btns = tk.Frame(r, bg="#020609")
        btns.pack(anchor="e")

        self.btn_power_on = tk.Button(
            btns, text="ENCENDER",
            font=(MONO, 7, "bold"), bg="#003300", fg=GREEN,
            relief="flat", bd=0, padx=6, pady=3, cursor="hand2",
            command=self._power_on)
        self.btn_power_on.pack(side="left", padx=(0, 3))

        self.btn_power_off = tk.Button(
            btns, text="APAGAR",
            font=(MONO, 7, "bold"), bg="#1A0000", fg=RED,
            relief="flat", bd=0, padx=6, pady=3, cursor="hand2",
            state="disabled", command=self._power_off)
        self.btn_power_off.pack(side="left", padx=(0, 6))

        tk.Button(btns, text="JSON↓", font=(MONO, 6), bg="#0A0A20", fg=CYAN,
                  relief="flat", bd=0, padx=4, pady=3, cursor="hand2",
                  command=self._save_json).pack(side="left", padx=(0, 2))

        tk.Button(btns, text="JSON↑", font=(MONO, 6), bg="#0A0A20", fg=CYAN,
                  relief="flat", bd=0, padx=4, pady=3, cursor="hand2",
                  command=self._load_json).pack(side="left", padx=(0, 2))

        tk.Button(btns, text="CSV", font=(MONO, 6), bg="#0A0A20", fg=AMBER,
                  relief="flat", bd=0, padx=4, pady=3, cursor="hand2",
                  command=self._export_csv).pack(side="left", padx=(0, 2))

        tk.Button(btns, text="TXT", font=(MONO, 6), bg="#0A0A20", fg=AMBER,
                  relief="flat", bd=0, padx=4, pady=3, cursor="hand2",
                  command=self._export_txt).pack(side="left")

        self.lbl_state = tk.Label(r, textvariable=self.var_state,
                                  font=(MONO, 7, "bold"), bg="#020609", fg=RED)
        self.lbl_state.pack(anchor="e")
        self.lbl_udp_err = tk.Label(r, text="ERR UDP: 0",
                                    font=(MONO, 6), bg="#020609", fg=TEXT_GRAY)
        self.lbl_udp_err.pack(anchor="e")
        self.lbl_clock = tk.Label(r, text="", font=(MONO, 7),
                                  bg="#020609", fg=TEXT_GRAY)
        self.lbl_clock.pack(anchor="e")
        tk.Frame(h, bg=BLUE_LT, height=1).pack(fill="x", side="bottom")

    def _tick_clock(self):
        self.lbl_clock.config(text=time.strftime("T+%H:%M:%S"))
        self.parent.after(1000, self._tick_clock)

    def _build_wifi_panel(self):
        inner = make_card(self.left, "CONEXION WiFi / RSSI", CYAN)
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")

        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)
        tk.Label(lb, text="INTENSIDAD DE SEÑAL (desde ESP32)",
                 font=(MONO, 7), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        self.wifi_cv = tk.Canvas(lb, width=160, height=50,
                                 bg=BG_CARD, highlightthickness=0)
        self.wifi_cv.pack(anchor="w", pady=(2, 1))
        self.lbl_wifi = tk.Label(lb, textvariable=self.var_wifi,
                                 font=(MONO, 13, "bold"), bg=BG_CARD, fg=CYAN)
        self.lbl_wifi.pack(anchor="w")
        self.lbl_wifi_txt = tk.Label(lb, text="SIN SEÑAL",
                                     font=(MONO, 7, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_wifi_txt.pack(anchor="w")

        tk.Frame(row, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)

        rb = tk.Frame(row, bg=BG_CARD)
        rb.pack(side="left", fill="both", expand=True)
        tk.Label(rb, text="CONEXION COHETE", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w", pady=(0, 4))
        self.btn_connect = tk.Button(
            rb, text="CONECTAR", font=(MONO, 9, "bold"),
            bg="#001833", fg=CYAN, relief="flat", bd=0, pady=10,
            cursor="hand2", state="disabled", command=self._do_connect)
        self.btn_connect.pack(fill="x")
        self.lbl_conn_st = tk.Label(rb, text="DESCONECTADO",
                                    font=(MONO, 8, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_conn_st.pack(anchor="w", pady=(6, 0))
        self._draw_wifi(0)

    def _draw_wifi(self, pct):
        c = self.wifi_cv
        c.delete("all")
        for i in range(5):
            x1 = i * 24 + 6
            bar_h = 44 * ((i + 1) / 5)
            y1 = 48 - bar_h
            x2 = x1 + 18
            threshold = (i + 1) * 20
            if pct >= threshold:
                bar_color = GREEN if pct >= 70 else AMBER if pct >= 40 else RED
            else:
                bar_color = TEXT_DARK
            c.create_rectangle(x1, y1, x2, 48, fill=bar_color, outline="")
        txt_color = GREEN if pct >= 70 else AMBER if pct >= 40 else RED if pct >= 10 else TEXT_GRAY
        c.create_text(148, 25, text=f"{pct}%", font=(MONO, 9, "bold"), fill=txt_color)

    def _build_device_panel(self):
        inner = make_card(self.left, "ESTADO DEL SISTEMA", BLUE_LT)
        box = tk.Frame(inner, bg=BG_INPUT,
                       highlightbackground=BORDER_C, highlightthickness=1)
        box.pack(fill="x", pady=(0, 6))

        self.lbl_dev_ev = tk.Label(box, text="EN ESPERA DE CONEXION",
                                   font=(MONO, 9, "bold"), bg=BG_INPUT,
                                   fg=TEXT_GRAY, pady=8)
        self.lbl_dev_ev.pack(fill="x")
        self.lbl_dev_sb = tk.Label(box,
                                   text="Inicia la conexion WiFi para activar",
                                   font=(MONO, 7), bg=BG_INPUT, fg=TEXT_GRAY, pady=3)
        self.lbl_dev_sb.pack(fill="x")

        g = tk.Frame(inner, bg=BG_CARD)
        g.pack(fill="x")
        self.subsys = {}
        items = [("BATERIA", "N/A"), ("GPS", "N/A"), ("GIROSCOPIO", "N/A"),
                 ("ALTIMETRO", "N/A"), ("PROPULSION", "N/A"), ("TELEMETRIA", "N/A")]
        for i, (name, val) in enumerate(items):
            col = i % 3
            row_n = i // 3
            cell = tk.Frame(g, bg=BG_CARD2, highlightbackground=BORDER,
                            highlightthickness=1)
            cell.grid(row=row_n, column=col, padx=2, pady=2,
                      sticky="ew", ipadx=4, ipady=4)
            g.columnconfigure(col, weight=1)
            tk.Label(cell, text=name, font=(MONO, 6),
                     bg=BG_CARD2, fg=TEXT_GRAY).pack()
            lbl = tk.Label(cell, text=val, font=(MONO, 8, "bold"),
                           bg=BG_CARD2, fg=TEXT_DARK)
            lbl.pack()
            self.subsys[name] = lbl

    def _update_subsystems_from_state(self):
        """
        Actualiza cada subsistema individualmente desde shared_state.
        Los valores vienen del listener UDP real — no se asume nada.
        """
        bateria = shared_state.get("bateria_cohete", None)
        gps     = shared_state.get("gps_estado",    None)
        giro    = shared_state.get("giroscopio",     None)
        alti    = shared_state.get("altimetro",      None)
        prop    = shared_state.get("propulsion",     None)
        telem   = shared_state.get("telemetria",     None)

        if bateria and bateria != "N/A":
            self.subsys["BATERIA"].config(text=str(bateria), fg=GREEN)
        else:
            self.subsys["BATERIA"].config(text="N/A", fg=TEXT_DARK)

        if gps == "OK":
            self.subsys["GPS"].config(text="OK", fg=GREEN)
        elif gps:
            self.subsys["GPS"].config(text=str(gps), fg=RED)
        else:
            self.subsys["GPS"].config(text="N/A", fg=TEXT_DARK)

        if giro == "OK":
            self.subsys["GIROSCOPIO"].config(text="OK", fg=GREEN)
        elif giro:
            self.subsys["GIROSCOPIO"].config(text=str(giro), fg=RED)
        else:
            self.subsys["GIROSCOPIO"].config(text="N/A", fg=TEXT_DARK)

        if alti and alti != "N/A":
            self.subsys["ALTIMETRO"].config(text=str(alti), fg=CYAN)
        else:
            self.subsys["ALTIMETRO"].config(text="N/A", fg=TEXT_DARK)

        if prop == "EN ESPERA":
            self.subsys["PROPULSION"].config(text="EN ESPERA", fg=AMBER)
        elif prop == "OK":
            self.subsys["PROPULSION"].config(text="OK", fg=GREEN)
        elif prop:
            self.subsys["PROPULSION"].config(text=str(prop), fg=AMBER)
        else:
            self.subsys["PROPULSION"].config(text="N/A", fg=TEXT_DARK)

        if telem == "ACTIVA":
            self.subsys["TELEMETRIA"].config(text="ACTIVA", fg=GREEN)
        elif telem:
            self.subsys["TELEMETRIA"].config(text=str(telem), fg=TEXT_GRAY)
        else:
            self.subsys["TELEMETRIA"].config(text="N/A", fg=TEXT_DARK)

    def _set_device(self, state):
        cfgs = {
            "standby":    ("EN ESPERA DE CONEXION",   "Inicia conexion WiFi",      TEXT_GRAY),
            "connecting": ("ESTABLECIENDO CONEXION...", "Handshake al cohete",      AMBER),
            "connected":  ("COHETE CONECTADO",          "Subsistemas en linea",     GREEN),
            "armed":      ("ARMADO -- LISTO",           "Lanzamiento autorizado",   CYAN),
            "launch":     ("SECUENCIA ACTIVA",          "NO INTERRUMPIR",           RED),
            "abort":      ("SECUENCIA ABORTADA",        "Modo seguro",              AMBER),
        }
        t, s, c = cfgs.get(state, cfgs["standby"])
        self.lbl_dev_ev.config(text=t, fg=c)
        self.lbl_dev_sb.config(text=s)
        if state in ("connected", "armed", "launch"):
            self._update_subsystems_from_state()
        elif state in ("standby", "abort"):
            for lbl in self.subsys.values():
                lbl.config(text="N/A", fg=TEXT_DARK)

    def _build_signal_panel(self):
        inner = make_card(self.left, "VERIFICACION DE SEÑAL RF", AMBER)
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")
        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)
        tk.Label(lb, text="CALIDAD DE SEÑAL (RSSI desde ESP32)",
                 font=(MONO, 7), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Sig2.Horizontal.TProgressbar",
                     troughcolor="#030A14", background=AMBER,
                     thickness=18, bordercolor=BORDER)
        self.sig_bar = ttk.Progressbar(lb, orient="horizontal",
                                       mode="determinate",
                                       style="Sig2.Horizontal.TProgressbar",
                                       maximum=100)
        self.sig_bar.pack(fill="x", pady=(4, 2))
        self.lbl_sig_val = tk.Label(lb, textvariable=self.var_sig,
                                    font=(MONO, 14, "bold"), bg=BG_CARD, fg=AMBER)
        self.lbl_sig_val.pack(anchor="w", pady=(3, 0))
        self.lbl_sig_st = tk.Label(lb, text="En espera de datos UDP...",
                                   font=(MONO, 7), bg=BG_CARD, fg=TEXT_GRAY)
        self.lbl_sig_st.pack(anchor="w")

        tk.Frame(row, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
        self.btn_verify = tk.Button(
            row, text="VERIFICAR\nSENAL",
            font=(MONO, 8, "bold"), bg="#1A1000", fg=AMBER,
            relief="flat", bd=0, width=8, pady=12,
            cursor="hand2", state="disabled",
            command=self._do_verify)
        self.btn_verify.pack(side="left")

    def _build_link_panel(self):
        inner = make_card(self.left, "CONFIRMACION DE ENLACE", GREEN)
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")
        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)

        self.link_box = tk.Frame(lb, bg="#020F08",
                                 highlightbackground=GREEN, highlightthickness=1)
        self.link_box.pack(fill="x", pady=(0, 4))
        self.lbl_link_m = tk.Label(self.link_box, text="FALTA CONEXION",
                                   font=(MONO, 10, "bold"), bg="#020F08",
                                   fg=RED, pady=8)
        self.lbl_link_m.pack(fill="x")
        self.lbl_link_d = tk.Label(
            self.link_box,
            text="No se ha establecido conexion con el cohete.",
            font=(MONO, 7), bg="#020F08", fg=TEXT_GRAY,
            justify="left", pady=3)
        self.lbl_link_d.pack(fill="x", padx=8)

        self.checks = {}
        for key, label in [("WiFi", "WiFi / RSSI activa"),
                            ("Cohete", "Cohete conectado"),
                            ("Señal", f"Senal RF >= {SIGNAL_MIN_PCT}%")]:
            f = tk.Frame(lb, bg=BG_CARD)
            f.pack(fill="x", pady=1)
            d = tk.Label(f, text="x  " + label, font=(MONO, 7),
                         bg=BG_CARD, fg=RED)
            d.pack(side="left")
            self.checks[key] = d

        tk.Frame(row, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
        self.btn_confirm = tk.Button(
            row, text="CONFIRMAR\nENLACE",
            font=(MONO, 8, "bold"), bg="#001A08", fg=GREEN,
            relief="flat", bd=0, width=8, pady=12,
            cursor="hand2", state="disabled",
            command=self._do_confirm)
        self.btn_confirm.pack(side="left")

    def _set_check(self, key, ok):
        if key not in self.checks:
            return
        label_text = self.checks[key].cget("text")[3:]
        prefix = "OK " if ok else "x  "
        self.checks[key].config(text=prefix + label_text,
                                fg=GREEN if ok else RED)

    def _build_launch_panel(self):
        inner = make_card(self.right, "LANZAMIENTO", RED)
        self.lbl_auth = tk.Label(inner, text="  DENEGADA",
                                 font=(MONO, 7, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_auth.pack(anchor="w", pady=(0, 4))
        self.lbl_cd = tk.Label(inner, text="T -- 00:00",
                               font=(MONO, 16, "bold"), bg=BG_CARD, fg=TEXT_DARK)
        self.lbl_cd.pack(pady=4)
        self.btn_launch = tk.Button(
            inner, text="ACTIVAR DESPEGUE",
            font=(MONO, 8, "bold"), bg="#1A0000", fg=RED,
            relief="flat", bd=0, pady=8,
            cursor="hand2", state="disabled",
            command=self._do_launch)
        self.btn_launch.pack(fill="x", pady=(4, 2))
        self.btn_abort = tk.Button(
            inner, text="ABORTAR SECUENCIA",
            font=(MONO, 8, "bold"), bg="#0A0600", fg=AMBER,
            relief="flat", bd=0, pady=8,
            cursor="hand2", state="disabled",
            command=self._do_abort)
        self.btn_abort.pack(fill="x")

    def _build_wind_panel(self):
        inner = make_card(self.right, "VIENTO", CYAN)
        tk.Label(inner, text="VELOCIDAD VIENTO (estimada)", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        self.lbl_wind_val = tk.Label(inner, textvariable=self.var_wind,
                                     font=(MONO, 13, "bold"), bg=BG_CARD, fg=CYAN)
        self.lbl_wind_val.pack(anchor="w")
        self.lbl_wind_warn = tk.Label(inner, text="",
                                      font=(MONO, 7, "bold"), bg=BG_CARD, fg=AMBER)
        self.lbl_wind_warn.pack(anchor="w")

    def _build_telemetry_panel(self):
        inner = make_card(self.right, "TELEMETRIA", BLUE_LT, expand=True)
        self.telem_text = tk.Text(inner, bg="#020A14", fg=TEXT_GRAY,
                                  font=(MONO, 7), relief="flat",
                                  height=8, state="disabled",
                                  insertbackground=CYAN)
        sb = ttk.Scrollbar(inner, orient="vertical",
                           command=self.telem_text.yview)
        self.telem_text.configure(yscrollcommand=sb.set)
        self.telem_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _log(self, msg, tag="SYS", color=None):
        color = color or TEXT_GRAY
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}][{tag}] {msg}\n"
        t = self.telem_text
        t.config(state="normal")
        t.insert("end", line)
        t.see("end")
        t.config(state="disabled")

    # ── POLLING de shared_state ───────────────────────────────────

    def _poll_shared_state(self):
        if not self.system_on:
            self.parent.after(1000, self._poll_shared_state)
            return

        # Leer RSSI real desde shared_state (escrito por _ingest_packet)
        pct = max(0, min(100, int(shared_state.get("wifi_strength", 0))))
        self.wifi_strength = pct
        self.var_wifi.set(f"{pct}%")
        self._draw_wifi(pct)
        if pct >= 70:
            wifi_txt, wifi_col = "EXCELENTE", GREEN
        elif pct >= 40:
            wifi_txt, wifi_col = "MODERADA", AMBER
        elif pct > 0:
            wifi_txt, wifi_col = "DEBIL", RED
        else:
            wifi_txt, wifi_col = "SIN SEÑAL", RED
        self.lbl_wifi_txt.config(text=wifi_txt, fg=wifi_col)
        self._set_check("WiFi", pct >= SIGNAL_MIN_PCT)

        # Leer viento estimado desde shared_state
        viento = float(shared_state.get("wind_speed", 0.0))
        self.wind_speed = viento
        self.var_wind.set(f"{viento:.1f} km/h")
        if viento > 35:
            self.lbl_wind_warn.config(text="VIENTO CRITICO", fg=RED)
        elif viento > 20:
            self.lbl_wind_warn.config(text="VIENTO MODERADO", fg=AMBER)
        else:
            self.lbl_wind_warn.config(text="CONDICIONES OK", fg=GREEN)

        if self.rocket_connected:
            self._update_subsystems_from_state()

        self.parent.after(1000, self._poll_shared_state)

    # ── TRANSPORTE UDP (uplink: despegue -> ESP32) ────────────────

    def _send_udp(self, payload: dict):
        """Envia un comando JSON al ESP32/simulador por UDP."""
        def _tx():
            try:
                data = json.dumps(payload).encode("utf-8")
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(2.0)
                    s.sendto(data, (ESP32_HOST, ESP32_CMD_PORT))
                self._log(f"UDP -> {ESP32_HOST}:{ESP32_CMD_PORT}  {payload}", "UDP", CYAN)
            except OSError as e:
                self._log(f"ERROR UDP: {e}", "UDP", RED)
        threading.Thread(target=_tx, daemon=True).start()

    # ── FLUJO DE OPERACION ────────────────────────────────────────

    def _power_on(self):
        if self.system_on:
            return
        self.system_on = True
        self.btn_power_on.config(state="disabled", bg="#001A00")
        self.btn_power_off.config(state="normal", bg="#2A0000")
        self.var_state.set("ACTIVO")
        self.lbl_state.config(fg=GREEN)
        self.btn_connect.config(state="normal")
        for key in self.checks:
            self._set_check(key, False)
        shared_state.set("system_on", True)
        shared_state.set("launch_state", "ACTIVO")
        self._db_insert("POWER_ON")
        self._log("SISTEMA ENCENDIDO — esperando telemetria UDP...", "SYS", GREEN)
        self._log(f"Listener activo en 0.0.0.0:{DESPEGUE_UDP_PORT}", "UDP", CYAN)

    def _power_off(self):
        if not self.system_on:
            return
        ok = messagebox.askyesno("APAGAR", "Confirmas apagar el sistema?", icon="warning")
        if not ok:
            return
        self.system_on = self.rocket_connected = self.signal_verified = False
        self.link_confirmed = self.launch_armed = self.launch_active = False
        self.btn_power_on.config(state="normal", bg="#003300")
        self.btn_power_off.config(state="disabled", bg="#1A0000")
        self.var_state.set("APAGADO")
        self.lbl_state.config(fg=TEXT_GRAY)
        self.btn_connect.config(state="disabled", text="CONECTAR", fg=CYAN)
        self.lbl_conn_st.config(text="DESCONECTADO", fg=RED)
        self._draw_wifi(0)
        self.btn_verify.config(state="disabled")
        self.btn_confirm.config(state="disabled")
        self.btn_launch.config(state="disabled")
        self.btn_abort.config(state="disabled")
        self.lbl_cd.config(text="T -- 00:00", fg=TEXT_DARK)
        self.lbl_auth.config(text="  DENEGADA", fg=TEXT_GRAY)
        self._set_device("standby")
        shared_state.set("system_on", False)
        shared_state.set("launch_state", "STANDBY")
        self._db_insert("POWER_OFF")
        self._log("SISTEMA APAGADO", "SYS", AMBER)

    def _do_connect(self):
        if not self.system_on:
            return
        self.btn_connect.config(state="disabled", text="CONECTANDO...", fg=AMBER)
        self.lbl_conn_st.config(text="CONECTANDO...", fg=AMBER)
        self._set_device("connecting")
        self._log("Enviando ping al ESP32...", "CONN", AMBER)
        # Enviar ping real por UDP al simulador
        self._send_udp({"cmd": "ping"})
        self.parent.after(2000, self._connect_done)

    def _connect_done(self):
        self.rocket_connected = True
        self.btn_connect.config(text="CONECTADO", fg=GREEN, bg="#001A08")
        self.lbl_conn_st.config(text="CONECTADO", fg=GREEN)
        self._set_device("connected")
        self._set_check("Cohete", True)
        self.btn_verify.config(state="normal")
        shared_state.set("rocket_connected", True)
        self._db_insert("COHETE_CONECTADO")
        self._log("COHETE CONECTADO via UDP", "CONN", GREEN)

    def _do_verify(self):
        self.btn_verify.config(state="disabled", text="VERIFICANDO...", fg=AMBER)
        self._log("Consultando señal RF al ESP32...", "SIG", AMBER)
        # Pedir status al simulador para obtener respuesta con RSSI real
        self._send_udp({"cmd": "status"})
        self.parent.after(3000, self._verify_done)

    def _verify_done(self):
        # Leer RSSI real que llego por UDP y fue escrito en shared_state
        q = int(shared_state.get("signal_quality", 0))
        q = max(0, min(100, q))
        self.signal_quality = q
        self.sig_bar["value"] = q
        self.var_sig.set(f"{q}%")
        ok = q >= SIGNAL_MIN_PCT   # umbral: señal RF util (ver constante SIGNAL_MIN_PCT)
        self.signal_verified = ok
        color = GREEN if ok else RED
        self.lbl_sig_val.config(fg=color)
        self.lbl_sig_st.config(text="SEÑAL OK" if ok else "SEÑAL INSUFICIENTE", fg=color)
        self._set_check("Señal", ok)
        self.btn_verify.config(text="VERIFICAR\nSENAL", fg=AMBER)
        if ok:
            self.btn_confirm.config(state="normal")
            self._log(f"Señal RF verificada: {q}% — ENLACE DISPONIBLE", "SIG", GREEN)
        else:
            self._log(f"Señal RF insuficiente: {q}% — verifica simulador", "SIG", RED)
        self._db_insert("VERIFICACION_SEÑAL", f"calidad={q}% ok={ok}")

    def _do_confirm(self):
        self.link_confirmed = True
        self.lbl_link_m.config(text="ENLACE CONFIRMADO", fg=GREEN)
        self.lbl_link_d.config(text="Subsistemas verificados individualmente.")
        self.btn_confirm.config(state="disabled", fg=GREEN, bg="#001800")
        self.btn_launch.config(state="normal")
        self.btn_abort.config(state="normal")
        self.lbl_cd.config(fg=CYAN)
        self.lbl_auth.config(text="  AUTORIZADA", fg=GREEN)
        self._set_device("armed")
        self.var_state.set("ARMADO")
        self.lbl_state.config(fg=GREEN)
        shared_state.set("launch_state", "ARMADO")
        self._db_insert("ENLACE_CONFIRMADO")
        self._log("ENLACE CONFIRMADO — LANZAMIENTO AUTORIZADO", "LAUNCH", GREEN)

    def _do_launch(self):
        ok = messagebox.askyesno("CONFIRMAR LANZAMIENTO",
                                 "Activar despegue? OPERACION CRITICA",
                                 icon="warning")
        if not ok:
            return
        self.launch_active = True
        self.btn_launch.config(state="disabled")
        self.lbl_auth.config(text="  CUENTA REGRESIVA", fg=RED)
        self._set_device("launch")
        self.var_state.set("LANZAMIENTO")
        self.lbl_state.config(fg=RED)
        shared_state.set("launch_state", "LANZAMIENTO")
        shared_state.set("launch_active", True)
        # Enviar comando real de lanzamiento al ESP32 por UDP
        self._send_udp({"cmd": "launch"})
        self._db_insert("LAUNCH_INICIADO")
        self._log("COMANDO 'launch' enviado al ESP32 por UDP", "LAUNCH", RED)
        self._cdown(10)

    def _cdown(self, n):
        if n > 0:
            c = RED if n <= 3 else AMBER if n <= 6 else CYAN
            self.lbl_cd.config(text=f"T -- 00:{n:02d}", fg=c)
            self._log(f"T-{n:02d}", "LAUNCH", c)
            self.parent.after(1000, lambda: self._cdown(n - 1))
        else:
            self.lbl_cd.config(text="LIFTOFF!", fg=GREEN)
            shared_state.set("launch_state", "LANZAMIENTO")
            shared_state.set("launch_active", True)
            self._db_insert("LIFTOFF")
            self._log("LIFTOFF — DESPEGUE EXITOSO", "LAUNCH", GREEN)

    def _do_abort(self):
        ok = messagebox.askyesno("ABORT", "Confirmas ABORTAR?", icon="question")
        if not ok:
            return
        self.launch_active = self.launch_armed = False
        self.btn_launch.config(state="disabled")
        self.btn_abort.config(state="disabled")
        self.lbl_cd.config(text="T -- 00:00", fg=TEXT_DARK)
        self.lbl_auth.config(text="  ABORTADA", fg=AMBER)
        self._set_device("abort")
        self.var_state.set("ABORTADO")
        self.lbl_state.config(fg=AMBER)
        shared_state.set("launch_state", "ABORTADO")
        shared_state.set("launch_active", False)
        # Enviar comando abort al ESP32 por UDP
        self._send_udp({"cmd": "abort"})
        self._db_insert("ABORT")
        self._log("ABORT — comando enviado al ESP32", "LAUNCH", AMBER)
