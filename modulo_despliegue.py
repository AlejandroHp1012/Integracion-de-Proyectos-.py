"""

MÓDULO DESPLIEGUE v3 — Equipo 2                          

"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time, math, json, os, datetime, csv
import threading, socket

# ── BASE DE DATOS (MySQL / XAMPP) 
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    _MYSQL_DISPONIBLE = True
except ImportError:
    _MYSQL_DISPONIBLE = False
    print("[DB] mysql-connector-python no instalado. "
          "Ejecuta: pip install mysql-connector-python")

DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "",           
    "database": "cohete_db",
}

_SQL_CREAR_BD = "CREATE DATABASE IF NOT EXISTS cohete_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

_SQL_TABLAS = [
    """CREATE TABLE IF NOT EXISTS sesiones (
        id             INT AUTO_INCREMENT PRIMARY KEY,
        nombre         VARCHAR(120)  NOT NULL,
        mision         VARCHAR(60)   DEFAULT 'ALPHA-001',
        modulo         VARCHAR(60)   DEFAULT 'DESPLIEGUE-v3',
        notas          TEXT,
        fecha_inicio   DATETIME      NOT NULL,
        fecha_guardado DATETIME      NOT NULL,
        fase_final     VARCHAR(30),
        max_altitud_m  FLOAT,
        min_velocidad  FLOAT,
        total_eventos  INT           DEFAULT 0
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS eventos (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        sesion_id  INT          NOT NULL,
        timestamp  VARCHAR(12)  NOT NULL,
        tag        VARCHAR(10)  NOT NULL,
        mensaje    TEXT,
        FOREIGN KEY (sesion_id) REFERENCES sesiones(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
    """CREATE TABLE IF NOT EXISTS telemetria (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        sesion_id     INT    NOT NULL,
        muestra_idx   INT    NOT NULL,
        altitud_m     FLOAT,
        velocidad_ms  FLOAT,
        FOREIGN KEY (sesion_id) REFERENCES sesiones(id) ON DELETE CASCADE
    ) ENGINE=InnoDB""",
]


class DBManager:
    """Gestiona la conexion y escritura a MySQL (XAMPP).
    
    Uso rapido:
        db = DBManager()
        if db.conectar():
            sid = db.guardar_sesion(datos_dict)
            db.desconectar()
    """

    def __init__(self):
        self._conn   = None
        self._cursor = None
        self.activa  = False

    def conectar(self):
        if not _MYSQL_DISPONIBLE:
            return False
        try:
            cfg_sin_bd = {k: v for k, v in DB_CONFIG.items() if k != "database"}
            tmp = mysql.connector.connect(**cfg_sin_bd)
            cur = tmp.cursor()
            cur.execute(_SQL_CREAR_BD)
            tmp.commit()
            cur.close()
            tmp.close()

            self._conn   = mysql.connector.connect(**DB_CONFIG)
            self._cursor = self._conn.cursor()
            for stmt in _SQL_TABLAS:
                self._cursor.execute(stmt)
            self._conn.commit()
            self.activa = True
            print("[DB] Conectado a MySQL — cohete_db lista.")
            return True
        except Exception as e:
            print(f"[DB] Error de conexion: {e}")
            self.activa = False
            return False

    def desconectar(self):
        try:
            if self._cursor:
                self._cursor.close()
            if self._conn and self._conn.is_connected():
                self._conn.close()
        except Exception:
            pass
        self.activa = False

    def reconectar(self):
        self.desconectar()
        return self.conectar()

    def guardar_sesion(self, sesion):
        if not self.activa:
            return None
        try:
            meta   = sesion.get("meta",   {})
            estado = sesion.get("estado", {})
            hist   = sesion.get("historial", {})
            evs    = sesion.get("eventos", [])

            ahora = datetime.datetime.now()
            ts_inicio = meta.get("timestamp", ahora.isoformat())
            try:
                dt_inicio = datetime.datetime.fromisoformat(ts_inicio)
            except Exception:
                dt_inicio = ahora

            self._cursor.execute(
                """INSERT INTO sesiones
                   (nombre, mision, modulo, notas,
                    fecha_inicio, fecha_guardado,
                    fase_final, max_altitud_m, min_velocidad, total_eventos)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    meta.get("nombre",  "sin_nombre"),
                    meta.get("mision",  "ALPHA-001"),
                    meta.get("modulo",  "DESPLIEGUE-v3"),
                    meta.get("notas",   ""),
                    dt_inicio, ahora,
                    estado.get("fase_actual",   "STANDBY"),
                    estado.get("max_altitud_m", 0.0),
                    estado.get("min_velocidad", 0.0),
                    len(evs),
                )
            )
            sesion_id = self._cursor.lastrowid

            if evs:
                self._cursor.executemany(
                    "INSERT INTO eventos (sesion_id, timestamp, tag, mensaje) VALUES (%s, %s, %s, %s)",
                    [(sesion_id, e.get("ts",""), e.get("tag",""), e.get("msg","")) for e in evs]
                )

            alts = hist.get("altitud",   [])
            vels = hist.get("velocidad", [])
            n    = max(len(alts), len(vels))
            if n:
                self._cursor.executemany(
                    "INSERT INTO telemetria (sesion_id, muestra_idx, altitud_m, velocidad_ms) VALUES (%s, %s, %s, %s)",
                    [(sesion_id, i,
                      float(alts[i]) if i < len(alts) else None,
                      float(vels[i]) if i < len(vels) else None)
                     for i in range(n)]
                )

            self._conn.commit()
            print(f"[DB] Sesion #{sesion_id} guardada ({len(evs)} eventos, {n} muestras).")
            return sesion_id
        except Exception as e:
            print(f"[DB] Error al guardar sesion: {e}")
            try:
                self._conn.rollback()
            except Exception:
                pass
            return None

    def listar_sesiones(self):
        if not self.activa:
            return []
        try:
            self._cursor.execute(
                "SELECT id, nombre, mision, fecha_guardado, fase_final, total_eventos "
                "FROM sesiones ORDER BY id DESC LIMIT 50"
            )
            cols = ["id", "nombre", "mision", "fecha_guardado", "fase_final", "total_eventos"]
            return [dict(zip(cols, row)) for row in self._cursor.fetchall()]
        except Exception as e:
            print(f"[DB] Error al listar sesiones: {e}")
            return []

    def insertar_evento_rt(self, sesion_id, ts, tag, msg):
        if not self.activa or sesion_id is None:
            return
        try:
            self._cursor.execute(
                "INSERT INTO eventos (sesion_id, timestamp, tag, mensaje) VALUES (%s, %s, %s, %s)",
                (sesion_id, ts, tag, msg)
            )
            self._conn.commit()
        except Exception as e:
            print(f"[DB] Error insertar evento: {e}")

    def insertar_telemetria_rt(self, sesion_id, idx, altitud, velocidad):
        if not self.activa or sesion_id is None:
            return
        try:
            self._cursor.execute(
                "INSERT INTO telemetria (sesion_id, muestra_idx, altitud_m, velocidad_ms) VALUES (%s,%s,%s,%s)",
                (sesion_id, idx, altitud, velocidad)
            )
            self._conn.commit()
        except Exception as e:
            print(f"[DB] Error insertar telemetria: {e}")




BG_ROOT    = "#F0F4F8"
BG_PANEL   = "#FFFFFF"
BG_DEEP    = "#E2E8F0"
BG_INPUT   = "#EDF2F7"

NAVY       = "#0A2463"
BLUE       = "#1565C0"
TEAL       = "#00796B"
GREEN_V    = "#2E7D32"
RED_V      = "#C62828"
ORANGE_V   = "#E65100"
AMBER_V    = "#F57F17"
CYAN_V     = "#00838F"
PURPLE_V   = "#6A1B9A"

TXT_HEAD   = "#0A1929"
TXT_MAIN   = "#1A237E"
TXT_SUB    = "#455A64"
TXT_MUTED  = "#90A4AE"

BDR        = "#CFD8DC"
BDR_HOT    = "#1565C0"

MONO       = "Courier New"
SANS       = "Trebuchet MS"

FASES_ORDEN = ["STANDBY","ASCENSO","APOGEO","DESPLIEGUE","DESCENSO","ATERRIZAJE"]
FASES_COLOR = {
    "STANDBY":    TXT_MUTED,
    "ASCENSO":    CYAN_V,
    "APOGEO":     AMBER_V,
    "DESPLIEGUE": ORANGE_V,
    "DESCENSO":   TEAL,
    "ATERRIZAJE": PURPLE_V,
}
FASES_BG = {
    "STANDBY":    "#ECEFF1",
    "ASCENSO":    "#E0F7FA",
    "APOGEO":     "#FFF8E1",
    "DESPLIEGUE": "#FBE9E7",
    "DESCENSO":   "#E8F5E9",
    "ATERRIZAJE": "#F3E5F5",
}


class ModuloDespliegue:
    def __init__(self, parent_frame):
        self.parent = parent_frame

        self.fase_actual     = "STANDBY"
        self.altitud         = 0.0
        self.velocidad       = 0.0
        self.bateria         = 0.0
        self.paracaidas_ok   = False
        self.despliegue_conf = False
        self._alt_hist       = []
        self._vel_hist       = []
        self._eventos        = []
        self._sesion_inicio  = time.strftime("%Y%m%d_%H%M%S")
        self._para_anim      = 0.0
        self._tick           = 0
        self._blink          = True
        self._max_alt        = 0.0
        self._min_vel        = 9999.0

      
        self._umbral_alt_m   = 50.0         
        self._fase_ts        = time.time()   
        self._MAX_EVENTOS    = 500           
        self.on_despliegue_confirmado = None

    
        self._udp_alt_ant     = 0.0
        self._udp_subiendo    = False
        self._udp_apo_det     = False
        self._udp_dep_done    = False
        self._udp_dep_ant     = False
        self._udp_cnt_baj     = 0
        self._udp_cnt_est     = 0
        self._udp_alt_est_ref = 0.0

        # ── BASE DE DATOS (MySQL/XAMPP) — init ANTES de _build_ui ──────────
        self._db           = DBManager()
        self._db_sesion_id = None    # ID de sesión activa en BD
        self._tel_idx      = 0       # Contador de muestras de telemetría RT

        self._build_ui()
        self._loop()

        hilo_udp = threading.Thread(
            target=self._servidor_udp, daemon=True)
        hilo_udp.start()

        hilo_db = threading.Thread(target=self._conectar_db_async, daemon=True)
        hilo_db.start()

   

    def _build_ui(self):
        self.parent.configure(bg=BG_ROOT)

       
        root = self.parent.winfo_toplevel()
        root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._build_topbar()

        body = tk.Frame(self.parent, bg=BG_ROOT)
        body.pack(fill="both", expand=True, padx=10, pady=(4, 8))

        self.col_L = tk.Frame(body, bg=BG_ROOT, width=260)
        self.col_L.pack(side="left", fill="y", padx=(0, 6))
        self.col_L.pack_propagate(False)

        self.col_M = tk.Frame(body, bg=BG_ROOT)
        self.col_M.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.col_R = tk.Frame(body, bg=BG_ROOT, width=240)
        self.col_R.pack(side="right", fill="y")
        self.col_R.pack_propagate(False)

        self._panel_datos_grandes()
        self._panel_condiciones()
        self._panel_fase()
        self._panel_grafica()
        self._panel_log()
        self._panel_paracaidas()
        self._panel_confirmacion()
        self._panel_guardado()

   
    def _build_topbar(self):
        bar = tk.Frame(self.parent, bg=NAVY, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self.top_band = tk.Frame(bar, bg=TXT_MUTED, height=5)
        self.top_band.pack(fill="x")

        inner = tk.Frame(bar, bg=NAVY)
        inner.pack(fill="both", expand=True, padx=14)

        left = tk.Frame(inner, bg=NAVY)
        left.pack(side="left", fill="y")

        tk.Label(left, text="🪂", font=("Segoe UI Emoji", 18),
                 bg=NAVY, fg="white").pack(side="left", padx=(0, 8))

        titl = tk.Frame(left, bg=NAVY)
        titl.pack(side="left")
        tk.Label(titl, text="MÓDULO DE DESPLIEGUE",
                 font=(SANS, 13, "bold"), bg=NAVY, fg="white").pack(anchor="w")
        tk.Label(titl, text="MISIÓN ALPHA-001  ·  SISTEMA DE RECUPERACIÓN",
                 font=(SANS, 8), bg=NAVY, fg="#90CAF9").pack(anchor="w")

        right = tk.Frame(inner, bg=NAVY)
        right.pack(side="right", fill="y")

        for txt, cmd, clr, bg in [
            ("↓ GUARDAR", self._guardar_sesion,    NAVY, "#64B5F6"),
            ("↑ CARGAR",  self._cargar_sesion,     NAVY, "#4DB6AC"),
            ("⟳ RESET",   self._reset_mision,      NAVY, "#EF9A9A"),
            ("📋 LOG",    self._exportar_log,       NAVY, "#CE93D8"),
            ("🗄 BD",     self._mostrar_sesiones_db, NAVY, "#A5D6A7"),
        ]:
            tk.Button(right, text=txt,
                      font=(SANS, 8, "bold"),
                      bg=bg, fg=clr, relief="flat",
                      padx=10, pady=4, cursor="hand2",
                      activebackground="white", activeforeground=NAVY,
                      command=cmd).pack(side="right", padx=3, pady=8)

        clk_box = tk.Frame(right, bg=NAVY)
        clk_box.pack(side="right", padx=16)
        self.lbl_clock = tk.Label(clk_box, text="T+00:00:00",
                                   font=(MONO, 14, "bold"),
                                   bg=NAVY, fg="white")
        self.lbl_clock.pack()
        self.lbl_fase_top = tk.Label(clk_box, text="● STANDBY",
                                      font=(SANS, 8, "bold"),
                                      bg=NAVY, fg=TXT_MUTED)
        self.lbl_fase_top.pack()
        self.lbl_db_st = tk.Label(clk_box, text="DB ○",
                                   font=(SANS, 7), bg=NAVY, fg="#EF5350")
        self.lbl_db_st.pack()



    def _panel_datos_grandes(self):
        self._tarjeta_dato(
            self.col_L, "ALTITUD", "lbl_alt",
            "m", BLUE, "#EBF5FB", accent_left=BLUE)

        self._tarjeta_dato(
            self.col_L, "VELOCIDAD", "lbl_vel",
            "m/s", TEAL, "#E8F8F5", accent_left=TEAL)

        self._tarjeta_dato(
            self.col_L, "BATERÍA", "lbl_batt",
            "%", AMBER_V, "#FFFDE7", accent_left=AMBER_V)

    def _tarjeta_dato(self, parent, titulo, attr, unidad,
                      color, bg_card, accent_left):
        card = tk.Frame(parent, bg=bg_card,
                        highlightbackground=BDR,
                        highlightthickness=1)
        card.pack(fill="x", pady=4)

        tk.Frame(card, bg=accent_left, width=6).pack(side="left", fill="y")

        body = tk.Frame(card, bg=bg_card, padx=10, pady=8)
        body.pack(side="left", fill="both", expand=True)

        tk.Label(body, text=titulo,
                 font=(SANS, 9, "bold"),
                 bg=bg_card, fg=TXT_SUB).pack(anchor="w")

        val_row = tk.Frame(body, bg=bg_card)
        val_row.pack(anchor="w")

        lbl = tk.Label(val_row, text="---",
                       font=(MONO, 32, "bold"),
                       bg=bg_card, fg=color)
        lbl.pack(side="left", anchor="s")

        tk.Label(val_row, text=f" {unidad}",
                 font=(SANS, 12),
                 bg=bg_card, fg=TXT_SUB).pack(side="left", anchor="s",
                                               pady=(0, 5))
        setattr(self, attr, lbl)

    def _panel_condiciones(self):
        card = self._card(self.col_L, "CONDICIONES", BLUE)
        self.cond_items = {}
        for key, texto in [("alt", "Altitud en rango"),
                            ("vel", "Velocidad decreciente"),
                            ("apo", "Apogeo detectado"),
                            ("cmd", "Comando recibido")]:
            row = tk.Frame(card, bg=BG_PANEL)
            row.pack(fill="x", pady=3)

            ind = tk.Label(row, text="●",
                           font=(SANS, 13),
                           bg=BG_PANEL, fg=BDR)
            ind.pack(side="left")

            lbl = tk.Label(row, text=texto,
                           font=(SANS, 10),
                           bg=BG_PANEL, fg=TXT_MUTED)
            lbl.pack(side="left", padx=6)
            self.cond_items[key] = (ind, lbl)

 
        tk.Frame(card, bg=BDR, height=1).pack(fill="x", pady=(6, 4))
        umb_row = tk.Frame(card, bg=BG_PANEL)
        umb_row.pack(fill="x")
        tk.Label(umb_row, text="Umbral alt. (m):",
                 font=(SANS, 8), bg=BG_PANEL, fg=TXT_SUB).pack(side="left")
        self._umbral_var = tk.StringVar(value=str(int(self._umbral_alt_m)))
        umb_entry = tk.Entry(umb_row, textvariable=self._umbral_var,
            width=6, font=(MONO, 9), bg=BG_INPUT, fg=TXT_HEAD,
            relief="flat", highlightbackground=BDR, highlightthickness=1,
            insertbackground=BLUE)
        umb_entry.pack(side="left", padx=4)
        tk.Button(umb_row, text="✓", font=(SANS, 8, "bold"),
                  bg=BLUE, fg="white", relief="flat", padx=4,
                  cursor="hand2",
                  command=self._aplicar_umbral).pack(side="left")

   

    def _panel_fase(self):
        card = self._card(self.col_M, "FASE DE VUELO", BLUE)

        top_row = tk.Frame(card, bg=BG_PANEL)
        top_row.pack(fill="x")

        self.fase_box = tk.Frame(top_row, bg=FASES_BG["STANDBY"],
                                  highlightbackground=TXT_MUTED,
                                  highlightthickness=2)
        self.fase_box.pack(side="left", fill="y", padx=(0, 12), pady=2)

        tk.Label(self.fase_box, text="FASE ACTUAL",
                 font=(SANS, 8, "bold"),
                 bg=FASES_BG["STANDBY"], fg=TXT_SUB).pack(pady=(8,0), padx=16)
        self.lbl_fase_gde = tk.Label(self.fase_box, text="STANDBY",
                                      font=(SANS, 24, "bold"),
                                      bg=FASES_BG["STANDBY"], fg=TXT_MUTED)
        self.lbl_fase_gde.pack(padx=20, pady=(2, 8))

        info_col = tk.Frame(top_row, bg=BG_PANEL)
        info_col.pack(side="left", fill="both", expand=True)

        self.lbl_paso = tk.Label(info_col, text="PASO  1 / 6",
                                  font=(MONO, 11, "bold"),
                                  bg=BG_PANEL, fg=TXT_MUTED)
        self.lbl_paso.pack(anchor="w")

        self.lbl_fase_desc = tk.Label(info_col,
            text="Sistema en espera.\nSin telemetría activa.",
            font=(SANS, 9), bg=BG_PANEL, fg=TXT_SUB,
            justify="left", wraplength=260)
        self.lbl_fase_desc.pack(anchor="w", pady=(4, 0))

        # ── CRONÓMETRO DE FASE ────────────────────────────────
        self.lbl_fase_timer = tk.Label(info_col, text="en fase: 00:00",
            font=(MONO, 8), bg=BG_PANEL, fg=TXT_MUTED)
        self.lbl_fase_timer.pack(anchor="w", pady=(2, 0))

        tk.Frame(card, bg=BDR, height=1).pack(fill="x", pady=(8, 4))

        prog_row = tk.Frame(card, bg=BG_PANEL)
        prog_row.pack(fill="x")
        self.fase_segs = {}
        for i, f in enumerate(FASES_ORDEN):
            col_f = tk.Frame(prog_row, bg=BG_PANEL)
            col_f.pack(side="left", expand=True, fill="x")

            seg = tk.Frame(col_f, bg=BG_DEEP, height=10)
            seg.pack(fill="x", padx=1)
            self.fase_segs[f] = seg

            tk.Label(col_f, text=f[:3],
                     font=(SANS, 7, "bold"),
                     bg=BG_PANEL, fg=TXT_MUTED).pack(pady=(2, 0))

        tk.Frame(card, bg=BDR, height=1).pack(fill="x", pady=(6, 4))
        kv_row = tk.Frame(card, bg=BG_PANEL)
        kv_row.pack(fill="x")

        for attr, lbl_txt, clr, bg_c in [
            ("lbl_c_alt",  "ALT (m)",  BLUE,     "#EBF5FB"),
            ("lbl_c_vel",  "VEL m/s",  TEAL,     "#E8F8F5"),
            ("lbl_c_fase", "FASE",     ORANGE_V,  "#FBE9E7"),
        ]:
            cell = tk.Frame(kv_row, bg=bg_c,
                            highlightbackground=BDR,
                            highlightthickness=1)
            cell.pack(side="left", expand=True, fill="x",
                      padx=3, ipady=6)
            tk.Label(cell, text=lbl_txt,
                     font=(SANS, 8, "bold"),
                     bg=bg_c, fg=TXT_SUB).pack()
            v = tk.Label(cell, text="---",
                         font=(MONO, 16, "bold"),
                         bg=bg_c, fg=clr)
            v.pack()
            setattr(self, attr, v)

    def _panel_grafica(self):
        card = self._card(self.col_M, "PERFIL DE VUELO", BLUE)

        lbl_row = tk.Frame(card, bg=BG_PANEL)
        lbl_row.pack(fill="x", pady=(0, 3))
        tk.Label(lbl_row, text="▲ ALTITUD",
                 font=(SANS, 8, "bold"), bg=BG_PANEL, fg=BLUE).pack(side="left")
        tk.Label(lbl_row, text="● VELOCIDAD",
                 font=(SANS, 8, "bold"), bg=BG_PANEL, fg=ORANGE_V).pack(side="right")

        self.cv_alt = tk.Canvas(card, bg=BG_DEEP, height=80,
                                highlightthickness=0)
        self.cv_alt.pack(fill="x", pady=(0, 3))
        self.cv_vel = tk.Canvas(card, bg=BG_DEEP, height=48,
                                highlightthickness=0)
        self.cv_vel.pack(fill="x")

        st_row = tk.Frame(card, bg=BG_PANEL)
        st_row.pack(fill="x", pady=(6, 0))
        for txt, attr, clr in [
            ("ALT. MÁX",  "lbl_amax", BLUE),
            ("VEL. MÍN",  "lbl_vmin", ORANGE_V),
        ]:
            s = tk.Frame(st_row, bg=BG_DEEP,
                         highlightbackground=BDR, highlightthickness=1)
            s.pack(side="left", expand=True, fill="x", padx=3, ipady=5)
            tk.Label(s, text=txt, font=(SANS, 7, "bold"),
                     bg=BG_DEEP, fg=TXT_SUB).pack()
            lbl = tk.Label(s, text="---",
                           font=(MONO, 13, "bold"), bg=BG_DEEP, fg=clr)
            lbl.pack()
            setattr(self, attr, lbl)

    def _panel_log(self):
        card = self._card(self.col_M, "REGISTRO DE EVENTOS", BLUE)

        note_row = tk.Frame(card, bg=BG_PANEL)
        note_row.pack(fill="x", pady=(0, 4))

        tk.Label(note_row, text="✏",
                 font=("Segoe UI Emoji", 10),
                 bg=BG_PANEL, fg=TXT_SUB).pack(side="left")
        self.nota_var = tk.StringVar()
        nota_entry = tk.Entry(note_row,
            textvariable=self.nota_var,
            font=(SANS, 9), bg=BG_INPUT, fg=TXT_HEAD,
            relief="flat",
            highlightbackground=BDR, highlightthickness=1,
            insertbackground=BLUE)
        nota_entry.pack(side="left", fill="x", expand=True, padx=6)
        nota_entry.insert(0, "Nota del operador...")
        nota_entry.bind("<FocusIn>",  lambda e: nota_entry.delete(0,"end")
                        if nota_entry.get()=="Nota del operador..." else None)
        nota_entry.bind("<FocusOut>", lambda e: nota_entry.insert(0,"Nota del operador...")
                        if not nota_entry.get().strip() else None)
        nota_entry.bind("<Return>", lambda e: self._enviar_nota(nota_entry))

        tk.Button(note_row, text="ENVIAR",
                  font=(SANS, 8, "bold"),
                  bg=BLUE, fg="white", relief="flat",
                  padx=8, pady=3, cursor="hand2",
                  activebackground=NAVY, activeforeground="white",
                  command=lambda: self._enviar_nota(nota_entry)).pack(side="right")

        self.log_text = tk.Text(
            card, bg="#FAFCFF", fg=TXT_HEAD,
            font=(MONO, 9), relief="flat",
            height=7, state="disabled",
            highlightbackground=BDR, highlightthickness=1,
            selectbackground=BLUE, selectforeground="white")
        sb = ttk.Scrollbar(card, orient="vertical",
                           command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.log_text.tag_config("SYS",  foreground=TXT_SUB)
        self.log_text.tag_config("FASE", foreground=BLUE)
        self.log_text.tag_config("CHT",  foreground=GREEN_V)
        self.log_text.tag_config("EMRG", foreground=RED_V)
        self.log_text.tag_config("OP",   foreground=ORANGE_V)
        self.log_text.tag_config("SAVE", foreground=AMBER_V)

        self._log("MÓDULO DESPLIEGUE v3 — INICIADO", "SYS")
        self._log("Aguardando datos de telemetría.", "SYS")


    def _panel_paracaidas(self):
        card = self._card(self.col_R, "PARACAÍDAS", ORANGE_V)

        self.cv_chute = tk.Canvas(card, width=220, height=130,
                                  bg=BG_DEEP, highlightthickness=0)
        self.cv_chute.pack(pady=(0, 6))
        self._draw_chute(False, 0)

        self.estado_box = tk.Frame(card, bg=BG_DEEP,
                                    highlightbackground=BDR,
                                    highlightthickness=2)
        self.estado_box.pack(fill="x", pady=(0, 4))
        self.lbl_chute_st = tk.Label(self.estado_box, text="EN ESPERA",
                                      font=(SANS, 14, "bold"),
                                      bg=BG_DEEP, fg=TXT_MUTED, pady=6)
        self.lbl_chute_st.pack()
        self.lbl_chute_sub = tk.Label(self.estado_box,
            text="Aguardando condiciones.",
            font=(SANS, 8), bg=BG_DEEP, fg=TXT_SUB, pady=(0))
        self.lbl_chute_sub.pack(pady=(0, 6))

    def _panel_confirmacion(self):
        card = self._card(self.col_R, "CONFIRMACIÓN DE DESPLIEGUE", GREEN_V)

        self.auth_frame = tk.Frame(card, bg="#FFEBEE",
                                    highlightbackground=RED_V,
                                    highlightthickness=2)
        self.auth_frame.pack(fill="x", pady=(0, 6))
        self.lbl_auth = tk.Label(self.auth_frame,
            text="✗  ACCESO DENEGADO",
            font=(SANS, 12, "bold"),
            bg="#FFEBEE", fg=RED_V, pady=8)
        self.lbl_auth.pack()

        self.btn_deploy = tk.Button(card,
            text="▶  DESPLEGAR PARACAÍDAS",
            font=(SANS, 11, "bold"),
            bg=BG_DEEP, fg=TXT_MUTED,
            relief="flat", bd=0, pady=14,
            cursor="hand2", state="disabled",
            command=self._confirmar_despliegue)
        self.btn_deploy.pack(fill="x", pady=(0, 4))

        self.btn_manual = tk.Button(card,
            text="⚠  DESPLIEGUE MANUAL",
            font=(SANS, 10, "bold"),
            bg="#FFF8E1", fg=AMBER_V,
            relief="flat", bd=0, pady=8,
            cursor="hand2",
            command=self._despliegue_manual)
        self.btn_manual.pack(fill="x")

        tk.Frame(card, bg=BDR, height=1).pack(fill="x", pady=6)
        tk.Label(card, text="PAYLOAD → RECUPERACIÓN",
                 font=(SANS, 7, "bold"),
                 bg=BG_PANEL, fg=TXT_MUTED).pack(anchor="w")
        self.lbl_payload = tk.Label(card,
            text='{ "status": "waiting" }',
            font=(MONO, 8), bg=BG_INPUT, fg=TXT_SUB,
            justify="left", anchor="w", wraplength=210)
        self.lbl_payload.pack(fill="x", ipady=5, ipadx=8, pady=(2, 0))

    def _panel_guardado(self):
        card = self._card(self.col_R, "GUARDAR / CARGAR SESIÓN", TEAL)

        tk.Label(card, text="NOMBRE DE SESIÓN",
                 font=(SANS, 8, "bold"),
                 bg=BG_PANEL, fg=TXT_SUB).pack(anchor="w")
        self.sesion_name_var = tk.StringVar(
            value=f"SESION_{self._sesion_inicio}")
        tk.Entry(card,
                 textvariable=self.sesion_name_var,
                 font=(SANS, 9), bg=BG_INPUT, fg=TXT_HEAD,
                 relief="flat",
                 highlightbackground=BDR, highlightthickness=1,
                 insertbackground=TEAL).pack(fill="x", pady=(2, 6))

        tk.Label(card, text="NOTAS DE MISIÓN",
                 font=(SANS, 8, "bold"),
                 bg=BG_PANEL, fg=TXT_SUB).pack(anchor="w")
        self.notas_txt = tk.Text(card, bg=BG_INPUT, fg=TXT_HEAD,
            font=(SANS, 8), height=3, relief="flat",
            highlightbackground=BDR, highlightthickness=1,
            insertbackground=TEAL)
        self.notas_txt.pack(fill="x", pady=(2, 6))
        self.notas_txt.insert("1.0", "Condiciones nominales.")

        btn_row = tk.Frame(card, bg=BG_PANEL)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="↓  GUARDAR JSON",
                  font=(SANS, 9, "bold"),
                  bg=TEAL, fg="white",
                  relief="flat", pady=7, cursor="hand2",
                  activebackground=GREEN_V, activeforeground="white",
                  command=self._guardar_sesion).pack(
                      side="left", expand=True, fill="x", padx=(0, 3))
        tk.Button(btn_row, text="↑  CARGAR JSON",
                  font=(SANS, 9, "bold"),
                  bg=BLUE, fg="white",
                  relief="flat", pady=7, cursor="hand2",
                  activebackground=NAVY, activeforeground="white",
                  command=self._cargar_sesion).pack(
                      side="left", expand=True, fill="x", padx=(3, 0))

        tk.Frame(card, bg=BDR, height=1).pack(fill="x", pady=(6, 3))
        self.lbl_save_st = tk.Label(card,
            text="Sin sesión guardada.",
            font=(SANS, 8), bg=BG_PANEL, fg=TXT_MUTED)
        self.lbl_save_st.pack(anchor="w")


    def _card(self, parent, title, accent=BLUE):
        outer = tk.Frame(parent, bg=BG_PANEL,
                         highlightbackground=BDR,
                         highlightthickness=1)
        outer.pack(fill="x", pady=4)

        hdr_bg = self._lighten(accent)
        hdr = tk.Frame(outer, bg=hdr_bg, height=28)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=accent, width=5).pack(side="left", fill="y")
        tk.Label(hdr, text=f"  {title}",
                 font=(SANS, 9, "bold"),
                 bg=hdr_bg, fg=accent, anchor="w").pack(side="left", fill="y")

        inner = tk.Frame(outer, bg=BG_PANEL, padx=10, pady=8)
        inner.pack(fill="both", expand=True)
        return inner

    @staticmethod
    def _lighten(hex_color):
        mix = {
            BLUE:     "#E3F2FD",
            TEAL:     "#E0F2F1",
            GREEN_V:  "#E8F5E9",
            RED_V:    "#FFEBEE",
            ORANGE_V: "#FBE9E7",
            AMBER_V:  "#FFF8E1",
            CYAN_V:   "#E0F7FA",
            PURPLE_V: "#F3E5F5",
            NAVY:     "#E8EAF6",
        }
        return mix.get(hex_color, "#F5F5F5")



    def _draw_chute(self, deployed=False, anim=0.0):
        c = self.cv_chute
        c.delete("all")
        cx, cy = 110, 28
        w, h = 220, 130

        if not deployed:
            c.create_text(cx, 10, text="SISTEMA CERRADO",
                          font=(SANS, 8, "bold"), fill=TXT_MUTED, anchor="n")
            c.create_rectangle(cx-14, 38, cx+14, 72,
                               fill=BG_DEEP, outline=BDR, width=2)
            c.create_polygon(cx-14, 38, cx, 16, cx+14, 38,
                             fill=BLUE, outline=BLUE)
            for y in range(44, 72, 7):
                c.create_line(cx-14, y, cx+14, y, fill=BDR, width=1)
            for lx in [cx-5, cx, cx+5]:
                c.create_line(lx, 72, lx, 100, fill=TXT_MUTED, dash=(3,3))
            c.create_rectangle(cx-10, 100, cx+10, 116,
                               fill=BG_DEEP, outline=TXT_MUTED, width=1)
            c.create_text(cx, 108, text="PKG", font=(MONO, 7), fill=TXT_MUTED)
        else:
            color = GREEN_V if self.despliegue_conf else ORANGE_V
            bg_fill = "#E8F5E9" if self.despliegue_conf else "#FBE9E7"
            swing = math.sin(anim) * 7

            pts = []
            for i in range(15):
                angle = math.radians(180 + i * 12.85)
                r = 46 + 7 * math.sin(anim * 2.2 + i * 0.4)
                px = cx + swing * 0.3 + r * math.cos(angle)
                py = cy + r * math.sin(angle) * 0.52
                pts.append((px, py))

            if pts:
                flat = [v for p in pts for v in p]
                c.create_polygon(flat, fill=bg_fill, outline=color,
                                 width=3, smooth=True)

            for i in [0, 3, 7, 11, 14]:
                if i < len(pts):
                    c.create_line(pts[i][0], pts[i][1],
                                  cx + swing * 0.6, 108,
                                  fill=color, width=1)

            cx2 = int(cx + swing * 0.6)
            c.create_rectangle(cx2-11, 108, cx2+11, 124,
                               fill=bg_fill, outline=color, width=2)

            est = "CONFIRMADO" if self.despliegue_conf else "DESPLEGADO"
            c.create_text(cx, 5, text=f"✓ {est}",
                          font=(SANS, 9, "bold"), fill=color, anchor="n")



    def _update_graficas(self):
        self._draw_curve(self.cv_alt, self._alt_hist,
                         BLUE, "#BBDEFB", zero_line=False)
        self._draw_curve(self.cv_vel, self._vel_hist,
                         ORANGE_V, "#FFCCBC", zero_line=True)

    def _draw_curve(self, canvas, hist, line_color, fill_color,
                    zero_line=False):
        c = canvas
        w = c.winfo_width() or 280
        h = c.winfo_height() or 70
        c.delete("all")

        for gx in range(0, w, 40):
            c.create_line(gx, 0, gx, h, fill=BDR, width=1)
        for gy in range(0, h, 20):
            c.create_line(0, gy, w, gy, fill=BDR, width=1)

        data = hist[-60:] if len(hist) > 60 else hist
        if len(data) < 2:
            c.create_text(w//2, h//2, text="SIN DATOS",
                          fill=TXT_MUTED, font=(SANS, 9))
            return

        mn = min(data); mx = max(data)
        rng = mx - mn or 1

        pts = []
        for i, v in enumerate(data):
            x = int(i / (len(data) - 1) * (w - 6)) + 3
            y = int(h - 5 - ((v - mn) / rng) * (h - 12))
            pts.append((x, y))

        area = [pts[0][0], h] + [v for p in pts for v in p] + [pts[-1][0], h]
        c.create_polygon(area, fill=fill_color, outline="", stipple="gray50")
        c.create_polygon(area, fill=fill_color, outline="")

        flat = [v for p in pts for v in p]
        c.create_line(flat, fill=line_color, width=2, smooth=True)

        lx, ly = pts[-1]
        c.create_oval(lx-5, ly-5, lx+5, ly+5,
                      fill=line_color, outline="white", width=2)

        if zero_line and mn < 0 < mx:
            zy = int(h - 5 - ((0 - mn) / rng) * (h - 12))
            c.create_line(0, zy, w, zy, fill=RED_V, dash=(5,3), width=1)
            c.create_text(w-3, zy-3, text="0",
                          fill=RED_V, font=(SANS, 7), anchor="ne")

        last_val = data[-1]
        txt = f"{last_val:+.1f}" if zero_line else f"{last_val:.0f} m"
        c.create_text(w-4, 4, text=txt,
                      fill=line_color, font=(MONO, 9, "bold"), anchor="ne")


    def _loop(self):
        self._tick += 1
        self.lbl_clock.config(text=time.strftime("T+%H:%M:%S"))

        if self._tick % 6 == 0:
            self._blink = not self._blink

        color = FASES_COLOR[self.fase_actual]
        sym = "●" if self._blink else "○"
        self.lbl_fase_top.config(text=f"{sym} {self.fase_actual}", fg=color)
        self.top_band.config(bg=color)

     
        elapsed = int(time.time() - self._fase_ts)
        mm, ss = divmod(elapsed, 60)
        self.lbl_fase_timer.config(
            text=f"en fase: {mm:02d}:{ss:02d}", fg=color)

        if self.paracaidas_ok:
            self._para_anim += 0.1
            self._draw_chute(True, self._para_anim)

        self._update_graficas()
        self.parent.after(120, self._loop)


    def _actualizar(self, datos: dict):
        self.altitud   = datos.get("altitud_m",    self.altitud)
        self.velocidad = datos.get("velocidad_ms", self.velocidad)
        self.bateria   = datos.get("bateria_pct",  self.bateria)
        nueva_fase     = datos.get("fase", self.fase_actual).upper()

        self._alt_hist.append(self.altitud)
        self._vel_hist.append(self.velocidad)
        self._telem_a_db(self.altitud, self.velocidad)  # MySQL RT
        if len(self._alt_hist) > 200: self._alt_hist = self._alt_hist[-200:]
        if len(self._vel_hist) > 200: self._vel_hist = self._vel_hist[-200:]

        if self.altitud > self._max_alt:
            self._max_alt = self.altitud
            self.lbl_amax.config(text=f"{self._max_alt:.0f} m")
        if self.velocidad < self._min_vel:
            self._min_vel = self.velocidad
            self.lbl_vmin.config(text=f"{self._min_vel:+.1f} m/s")

        self.lbl_alt.config(text=f"{self.altitud:.1f}")
        vel_c = TEAL if self.velocidad <= 0 else CYAN_V
        self.lbl_vel.config(text=f"{self.velocidad:+.1f}", fg=vel_c)
        bat_c = GREEN_V if self.bateria > 50 else AMBER_V if self.bateria > 20 else RED_V
        self.lbl_batt.config(text=f"{self.bateria:.1f}", fg=bat_c)

        self.lbl_c_alt.config(
            text=f"{self.altitud:.0f}",
            fg=BLUE if self.altitud > self._umbral_alt_m else TXT_MUTED)
        self.lbl_c_vel.config(
            text=f"{self.velocidad:+.1f}",
            fg=TEAL if self.velocidad <= 0 else CYAN_V)
        self.lbl_c_fase.config(
            text=nueva_fase[:4],
            fg=FASES_COLOR.get(nueva_fase, TXT_MAIN))

        if nueva_fase != self.fase_actual and nueva_fase in FASES_ORDEN:
            self._cambiar_fase(nueva_fase)

        self._update_condiciones()

    def _cambiar_fase(self, nueva: str):
        prev = self.fase_actual
        self.fase_actual = nueva
        color  = FASES_COLOR[nueva]
        bg_f   = FASES_BG[nueva]
        idx    = FASES_ORDEN.index(nueva)

        DESCS = {
            "STANDBY":    "Sistema en espera.\nSin telemetría activa.",
            "ASCENSO":    "Motor activo.\nCohete en trayectoria ascendente.",
            "APOGEO":     "Punto más alto alcanzado.\nMotor apagado.",
            "DESPLIEGUE": "Activando sistema\nde recuperación.",
            "DESCENSO":   "Descenso controlado.\nParacaídas desplegado.",
            "ATERRIZAJE": "Aproximación final.\nPreparando aterrizaje.",
        }

        self.lbl_fase_gde.config(text=nueva, fg=color, bg=bg_f)
        self.fase_box.config(bg=bg_f, highlightbackground=color)
        for w in self.fase_box.winfo_children():
            w.config(bg=bg_f)
        self.lbl_fase_gde.config(bg=bg_f)
        self.lbl_paso.config(text=f"PASO  {idx+1} / 6", fg=color)
        self.lbl_fase_desc.config(text=DESCS.get(nueva, ""), fg=TXT_SUB)

        for i, f in enumerate(FASES_ORDEN):
            if i < idx:
                self.fase_segs[f].config(bg=TEAL)
            elif i == idx:
                self.fase_segs[f].config(bg=color)
            else:
                self.fase_segs[f].config(bg=BG_DEEP)

        self._log(f"FASE: {prev} → {nueva}", "FASE")
        self._fase_ts = time.time()  
        if nueva == "DESPLIEGUE":
            self._activar_paracaidas()

    def _update_condiciones(self):
        ok_alt = self.altitud > self._umbral_alt_m
        ok_vel = self.velocidad <= 0
        ok_apo = self.fase_actual in ("APOGEO","DESPLIEGUE","DESCENSO","ATERRIZAJE")
        ok_cmd = self.fase_actual in ("DESPLIEGUE","DESCENSO","ATERRIZAJE")

        for key, ok in [("alt",ok_alt),("vel",ok_vel),
                        ("apo",ok_apo),("cmd",ok_cmd)]:
            ind, lbl = self.cond_items[key]
            ind.config(fg=TEAL   if ok else BDR)
            lbl.config(fg=GREEN_V if ok else TXT_MUTED,
                       font=(SANS, 10, "bold") if ok else (SANS, 10))

        if ok_alt and ok_vel and ok_apo and not self.paracaidas_ok:
            self.btn_deploy.config(state="normal",
                                   bg=GREEN_V, fg="white",
                                   activebackground=TEAL,
                                   activeforeground="white")
            self.lbl_auth.config(text="✓  ACCESO AUTORIZADO",
                                  fg=GREEN_V, bg="#E8F5E9")
            self.auth_frame.config(bg="#E8F5E9",
                                    highlightbackground=GREEN_V)

    def _activar_paracaidas(self):
        self.paracaidas_ok = True
        self.lbl_chute_st.config(text="● ACTIVADO", fg=GREEN_V,
                                  bg="#E8F5E9")
        self.estado_box.config(highlightbackground=GREEN_V, bg="#E8F5E9")
        self.lbl_chute_sub.config(text="Descenso controlado activo.",
                                   fg=TEAL, bg="#E8F5E9")
        self._log("PARACAÍDAS ACTIVADO — NOMINAL", "CHT")



    def _confirmar_despliegue(self):
        if self.despliegue_conf:
            return
       
        if not messagebox.askokcancel(
            "Confirmar despliegue",
            f"¿Confirmar DESPLIEGUE DE PARACAÍDAS?\n\n"
            f"  Altitud:   {self.altitud:.1f} m\n"
            f"  Velocidad: {self.velocidad:+.1f} m/s\n"
            f"  Fase:      {self.fase_actual}\n\n"
            "Esta acción no se puede deshacer.",
            icon="warning"
        ):
            return
    
        self.despliegue_conf = True
        self.paracaidas_ok   = True
        self.btn_deploy.config(text="✓  DESPLIEGUE CONFIRMADO",
                               state="disabled",
                               bg="#E8F5E9", fg=GREEN_V)
        self.lbl_chute_st.config(text="✓ CONFIRMADO", fg=GREEN_V)
        self.lbl_auth.config(text="✓  CONFIRMADO POR OPERADOR",
                              fg=GREEN_V, bg="#E8F5E9")
        self.auth_frame.config(bg="#E8F5E9", highlightbackground=GREEN_V)
        self._log("DESPLIEGUE CONFIRMADO POR OPERADOR", "CHT")

        payload = {
            "despliegue":   True,
            "altitud_m":    self.altitud,
            "velocidad_ms": self.velocidad,
            "bateria_pct":  self.bateria,
            "fase":         self.fase_actual,
            "timestamp":    time.strftime("%H:%M:%S"),
        }
        self.lbl_payload.config(
            text=f'{{ "despliegue": true,\n'
                 f'  "alt": {self.altitud:.0f}m,\n'
                 f'  "fase": "{self.fase_actual}" }}',
            fg=GREEN_V)
        if callable(self.on_despliegue_confirmado):
            self.on_despliegue_confirmado(payload)
        
        messagebox.showinfo(
            "Despliegue confirmado",
            f"✓ Paracaídas desplegado correctamente.\n\n"
            f"  Altitud:   {self.altitud:.1f} m\n"
            f"  Timestamp: {time.strftime('%H:%M:%S')}"
        )

    def _despliegue_manual(self):
   
        if not messagebox.askyesno(
            "⚠ DESPLIEGUE MANUAL — OVERRIDE",
            "Está a punto de activar el DESPLIEGUE MANUAL.\n\n"
            "Este modo omite todas las condiciones automáticas.\n"
            "Use solo en caso de emergencia.\n\n"
            "¿Desea continuar?",
            icon="warning"
        ):
            return
       
        self._log("⚠ DESPLIEGUE MANUAL ACTIVADO", "EMRG")
        self._activar_paracaidas()
        self.btn_deploy.config(state="normal",
                               bg=GREEN_V, fg="white")
        self.lbl_auth.config(text="⚠  OVERRIDE MANUAL",
                              fg=AMBER_V, bg="#FFF8E1")
        self.auth_frame.config(bg="#FFF8E1", highlightbackground=AMBER_V)
        # ── CONFIRMACIÓN FINAL
        messagebox.showwarning(
            "Override manual ejecutado",
            f"⚠ Despliegue manual activado.\n\n"
            f"  Altitud:   {self.altitud:.1f} m\n"
            f"  Velocidad: {self.velocidad:+.1f} m/s\n"
            f"  Timestamp: {time.strftime('%H:%M:%S')}"
        )

    def _enviar_nota(self, entry_widget):
        txt = entry_widget.get().strip()
        placeholder = "Nota del operador..."
        if txt and txt != placeholder:
            self._log(f"[OP] {txt}", "OP")
            entry_widget.delete(0, "end")
            entry_widget.insert(0, placeholder)
          
            messagebox.showinfo("Nota registrada",
                                f"Nota añadida al registro:\n\n\"{txt}\"")


    def _guardar_sesion(self):
        nombre = self.sesion_name_var.get().strip() or f"sesion_{self._sesion_inicio}"
        notas  = self.notas_txt.get("1.0", "end-1c")
        sesion = {
            "meta": {
                "nombre":    nombre,
                "notas":     notas,
                "timestamp": datetime.datetime.now().isoformat(),
                "mision":    "ALPHA-001",
                "modulo":    "DESPLIEGUE-v3",
            },
            "estado": {
                "fase_actual":     self.fase_actual,
                "altitud_m":       self.altitud,
                "velocidad_ms":    self.velocidad,
                "bateria_pct":     self.bateria,
                "paracaidas_ok":   self.paracaidas_ok,
                "despliegue_conf": self.despliegue_conf,
                "max_altitud_m":   self._max_alt,
                "min_velocidad":   self._min_vel,
            },
            "historial": {
                "altitud":   self._alt_hist,
                "velocidad": self._vel_hist,
            },
            "eventos": self._eventos,
        }
        ruta = filedialog.asksaveasfilename(
            title="Guardar sesión",
            defaultextension=".json",
            initialfile=f"{nombre}.json",
            filetypes=[("JSON","*.json"),("Todos","*.*")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(sesion, f, indent=2, ensure_ascii=False)
            self.lbl_save_st.config(
                text=f"✓  Guardado: {os.path.basename(ruta)}", fg=GREEN_V)
            self._log(f"SESIÓN GUARDADA → {os.path.basename(ruta)}", "SAVE")
          

            # Respaldo en MySQL / XAMPP 
            db_msg = ""
            if self._db.activa:
                sid = self._db.guardar_sesion(sesion)
                if sid:
                    self._db_sesion_id = sid
                    db_msg = f"\n  MySQL ID: #{sid}"
                    self._log(f"SESIÓN → MySQL #{sid}", "SAVE")
                else:
                    db_msg = "\n  MySQL: error al guardar"
            else:
                db_msg = "\n  MySQL: sin conexión (XAMPP apagado)"

            messagebox.showinfo(
                "Sesión guardada",
                f"✓ Sesión guardada exitosamente.\n\n"
                f"  Archivo: {os.path.basename(ruta)}\n"
                f"  Fase:    {self.fase_actual}\n"
                f"  Eventos: {len(self._eventos)}" + db_msg
            )
        except Exception as ex:
            self.lbl_save_st.config(text=f"✗  Error: {ex}", fg=RED_V)

    def _cargar_sesion(self):
       
        if not messagebox.askokcancel(
            "Cargar sesión",
            "¿Cargar una sesión guardada?\n\n"
            "El estado actual del módulo será reemplazado\n"
            "por los datos del archivo seleccionado.",
            icon="question"
        ):
            return
        ruta = filedialog.askopenfilename(
            title="Cargar sesión",
            filetypes=[("JSON","*.json"),("Todos","*.*")])
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                sesion = json.load(f)

            if not isinstance(sesion, dict):
                raise ValueError("El archivo no contiene un objeto JSON válido.")
            for seccion in ("meta", "estado", "historial"):
                if seccion not in sesion:
                    raise ValueError(f"Falta la sección requerida: '{seccion}'.")
            estado_req = ("fase_actual", "altitud_m", "velocidad_ms", "bateria_pct")
            for campo in estado_req:
                if campo not in sesion["estado"]:
                    raise ValueError(f"Falta el campo de estado: '{campo}'.")
            fase_cargada = sesion["estado"].get("fase_actual", "STANDBY").upper()
            if fase_cargada not in FASES_ORDEN:
                raise ValueError(
                    f"Fase desconocida en el archivo: '{fase_cargada}'.\n"
                    f"Valores válidos: {', '.join(FASES_ORDEN)}")
         

            meta   = sesion.get("meta",   {})
            estado = sesion.get("estado", {})
            hist   = sesion.get("historial", {})
            evs    = sesion.get("eventos", [])

            self.fase_actual     = estado.get("fase_actual",     "STANDBY")
            self.altitud         = float(estado.get("altitud_m",      0))
            self.velocidad       = float(estado.get("velocidad_ms",   0))
            self.bateria         = float(estado.get("bateria_pct",    0))
            self.paracaidas_ok   = bool(estado.get("paracaidas_ok",  False))
            self.despliegue_conf = bool(estado.get("despliegue_conf",False))
            self._max_alt        = float(estado.get("max_altitud_m",  0))
            self._min_vel        = float(estado.get("min_velocidad",  0))
            self._alt_hist = [float(v) for v in hist.get("altitud",   [])]
            self._vel_hist = [float(v) for v in hist.get("velocidad", [])]
            self._eventos  = evs

            self.sesion_name_var.set(meta.get("nombre", ""))
            self.notas_txt.delete("1.0","end")
            self.notas_txt.insert("1.0", meta.get("notas",""))

            self._actualizar({
                "altitud_m":    self.altitud,
                "velocidad_ms": self.velocidad,
                "bateria_pct":  self.bateria,
                "fase":         self.fase_actual,
            })
            self.lbl_amax.config(text=f"{self._max_alt:.0f} m")
            self.lbl_vmin.config(text=f"{self._min_vel:+.1f} m/s")

            fname = os.path.basename(ruta)
            self.lbl_save_st.config(
                text=f"↑  Cargado: {fname}", fg=BLUE)
            self._log(f"SESIÓN CARGADA ← {fname}", "SAVE")
         
            messagebox.showinfo(
                "Sesión cargada",
                f"✓ Sesión cargada exitosamente.\n\n"
                f"  Archivo: {fname}\n"
                f"  Misión:  {meta.get('mision', '—')}\n"
                f"  Fase:    {self.fase_actual}\n"
                f"  Eventos: {len(evs)}"
            )
        except Exception as ex:
            self.lbl_save_st.config(text=f"✗  Error: {ex}", fg=RED_V)
            messagebox.showerror("Error al cargar", str(ex))



    def _log(self, msg, tag="SYS"):
        ts = time.strftime("%H:%M:%S")
        self._eventos.append({"ts": ts, "tag": tag, "msg": msg})
     
        if len(self._eventos) > self._MAX_EVENTOS:
            self._eventos = self._eventos[-self._MAX_EVENTOS:]
        t = self.log_text
        t.config(state="normal")
        t.insert("end", f"[{ts}][{tag}] {msg}\n", tag)
        t.see("end")
        t.config(state="disabled")
        self._log_a_db(ts, tag, msg)  

   

    def _on_closing(self):
        """Confirmación de cierre con oferta de guardar."""
        if self.fase_actual not in ("STANDBY",) or self._eventos:
            resp = messagebox.askyesnocancel(
                "Cerrar módulo",
                f"La misión está en fase: {self.fase_actual}\n"
                f"Hay {len(self._eventos)} evento(s) registrados.\n\n"
                "¿Desea guardar la sesión antes de salir?",
                icon="warning"
            )
            if resp is None:          
                return
            if resp:                 
                self._guardar_sesion()
        self.parent.winfo_toplevel().destroy()

    def _reset_mision(self):
        """Reinicia el módulo a estado STANDBY limpio."""
        if not messagebox.askyesno(
            "⟳ RESET — Nueva misión",
            "¿Iniciar una NUEVA MISIÓN?\n\n"
            "Se borrarán todos los datos actuales:\n"
            "historial de vuelo, eventos y estado.\n\n"
            "Guarde la sesión antes si lo necesita.",
            icon="warning"
        ):
            return

        self.fase_actual     = "STANDBY"
        self.altitud         = 0.0
        self.velocidad       = 0.0
        self.bateria         = 0.0
        self.paracaidas_ok   = False
        self.despliegue_conf = False
        self._alt_hist       = []
        self._vel_hist       = []
        self._eventos        = []
        self._sesion_inicio  = time.strftime("%Y%m%d_%H%M%S")
        self._para_anim      = 0.0
        self._max_alt        = 0.0
        self._min_vel        = 9999.0
        self._fase_ts        = time.time()

        self.lbl_alt.config(text="---")
        self.lbl_vel.config(text="---", fg=TEAL)
        self.lbl_batt.config(text="---", fg=AMBER_V)
        self.lbl_amax.config(text="---")
        self.lbl_vmin.config(text="---")
        self.lbl_c_alt.config(text="---", fg=TXT_MUTED)
        self.lbl_c_vel.config(text="---", fg=TEAL)
        self.lbl_c_fase.config(text="STBY", fg=TXT_MUTED)
        self.lbl_fase_gde.config(text="STANDBY", fg=TXT_MUTED,
                                  bg=FASES_BG["STANDBY"])
        self.fase_box.config(bg=FASES_BG["STANDBY"],
                              highlightbackground=TXT_MUTED)
        for w in self.fase_box.winfo_children():
            w.config(bg=FASES_BG["STANDBY"])
        self.lbl_paso.config(text="PASO  1 / 6", fg=TXT_MUTED)
        self.lbl_fase_desc.config(
            text="Sistema en espera.\nSin telemetría activa.")
        self.lbl_fase_timer.config(text="en fase: 00:00", fg=TXT_MUTED)
        for f in FASES_ORDEN:
            self.fase_segs[f].config(bg=BG_DEEP)

       
        self._draw_chute(False, 0)
        self.lbl_chute_st.config(text="EN ESPERA", fg=TXT_MUTED, bg=BG_DEEP)
        self.lbl_chute_sub.config(
            text="Aguardando condiciones.", fg=TXT_SUB, bg=BG_DEEP)
        self.estado_box.config(highlightbackground=BDR, bg=BG_DEEP)

        
        self.btn_deploy.config(text="▶  DESPLEGAR PARACAÍDAS",
                               state="disabled", bg=BG_DEEP, fg=TXT_MUTED)
        self.lbl_auth.config(text="✗  ACCESO DENEGADO",
                              fg=RED_V, bg="#FFEBEE")
        self.auth_frame.config(bg="#FFEBEE", highlightbackground=RED_V)
        self.lbl_payload.config(text='{ "status": "waiting" }', fg=TXT_SUB)

       
        for key in self.cond_items:
            ind, lbl = self.cond_items[key]
            ind.config(fg=BDR)
            lbl.config(fg=TXT_MUTED, font=(SANS, 10))

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        self.sesion_name_var.set(f"SESION_{self._sesion_inicio}")
        self.lbl_save_st.config(text="Sin sesión guardada.", fg=TXT_MUTED)

        self._log("RESET — NUEVA MISIÓN INICIADA", "SYS")
        self._log("Aguardando datos de telemetría.", "SYS")

        messagebox.showinfo(
            "Reset completado",
            "✓ Módulo reiniciado.\n\n"
            "Sistema en STANDBY.\n"
            "Esperando datos reales del ESP32."
        )

    def _exportar_log(self):
        """Exporta el registro de eventos a TXT o CSV."""
        if not self._eventos:
            messagebox.showinfo("Log vacío",
                                "No hay eventos registrados para exportar.")
            return

        ruta = filedialog.asksaveasfilename(
            title="Exportar registro de eventos",
            defaultextension=".txt",
            initialfile=f"LOG_{self._sesion_inicio}",
            filetypes=[
                ("Texto plano", "*.txt"),
                ("CSV",         "*.csv"),
                ("Todos",       "*.*"),
            ]
        )
        if not ruta:
            return

        try:
            ext = os.path.splitext(ruta)[1].lower()
            if ext == ".csv":
                with open(ruta, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["ts", "tag", "msg"])
                    writer.writeheader()
                    writer.writerows(self._eventos)
            else:
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(f"MÓDULO DESPLIEGUE v3 — REGISTRO DE EVENTOS\n")
                    f.write(f"Sesión: {self._sesion_inicio}\n")
                    f.write(f"Exportado: {datetime.datetime.now().isoformat()}\n")
                    f.write("=" * 52 + "\n\n")
                    for ev in self._eventos:
                        f.write(f"[{ev['ts']}][{ev['tag']:4s}] {ev['msg']}\n")

            self._log(
                f"LOG EXPORTADO → {os.path.basename(ruta)} "
                f"({len(self._eventos)} eventos)", "SAVE")
            messagebox.showinfo(
                "Log exportado",
                f"✓ Registro exportado exitosamente.\n\n"
                f"  Archivo: {os.path.basename(ruta)}\n"
                f"  Eventos: {len(self._eventos)}\n"
                f"  Formato: {ext.upper() or '.TXT'}"
            )
        except Exception as ex:
            messagebox.showerror("Error al exportar", str(ex))

    def _aplicar_umbral(self):
        """Aplica el nuevo umbral de altitud ingresado por el operador."""
        try:
            nuevo = float(self._umbral_var.get().strip())
            if nuevo < 0:
                raise ValueError("El umbral no puede ser negativo.")
            self._umbral_alt_m = nuevo
            self._log(f"UMBRAL ALTITUD → {nuevo:.0f} m", "SYS")
            messagebox.showinfo(
                "Umbral actualizado",
                f"✓ Nuevo umbral de altitud: {nuevo:.0f} m\n\n"
                "Las condiciones de despliegue\nse evaluarán con este valor."
            )
        except ValueError as ex:
            messagebox.showerror("Valor inválido",
                                 f"Ingrese un número válido.\n\n{ex}")
            self._umbral_var.set(str(int(self._umbral_alt_m)))

 

    def recibir_datos(self, datos: dict):
        self._actualizar(datos)


    def _conectar_db_async(self):
        """Intenta conectar a MySQL en background y actualiza el indicador."""
        ok = self._db.conectar()
        def _actualizar_ui():
            if hasattr(self, "lbl_db_st"):
                if ok:
                    self.lbl_db_st.config(text="DB ●", fg="#4CAF50")
                    # Crear sesión RT en la BD para eventos en tiempo real
                    sesion_inicial = {
                        "meta": {
                            "nombre":    self.sesion_name_var.get() if hasattr(self, "sesion_name_var") else "RT",
                            "notas":     "",
                            "timestamp": datetime.datetime.now().isoformat(),
                            "mision":    "ALPHA-001",
                            "modulo":    "DESPLIEGUE-v3",
                        },
                        "estado": {
                            "fase_actual":   self.fase_actual,
                            "altitud_m":     0,
                            "velocidad_ms":  0,
                            "bateria_pct":   0,
                            "paracaidas_ok": False,
                            "despliegue_conf": False,
                            "max_altitud_m": 0,
                            "min_velocidad": 0,
                        },
                        "historial": {"altitud": [], "velocidad": []},
                        "eventos": [],
                    }
                    sid = self._db.guardar_sesion(sesion_inicial)
                    self._db_sesion_id = sid
                    if sid:
                        self._log(f"BD conectada — sesión RT #{sid}", "SYS")
                else:
                    self.lbl_db_st.config(text="DB ✗", fg="#EF5350")
                    self._log("BD MySQL sin conexión. Verifica XAMPP.", "SYS")
        if hasattr(self, "parent"):
            self.parent.after(0, _actualizar_ui)

    def _log_a_db(self, ts, tag, msg):
        """Inserta un evento en MySQL en hilo separado (no bloquea la UI)."""
        if self._db.activa and self._db_sesion_id:
            threading.Thread(
                target=self._db.insertar_evento_rt,
                args=(self._db_sesion_id, ts, tag, msg),
                daemon=True
            ).start()

    def _telem_a_db(self, altitud, velocidad):
        """Guarda muestra de telemetría en MySQL en hilo separado."""
        if self._db.activa and self._db_sesion_id:
            self._tel_idx += 1
            threading.Thread(
                target=self._db.insertar_telemetria_rt,
                args=(self._db_sesion_id, self._tel_idx, altitud, velocidad),
                daemon=True
            ).start()

    def _mostrar_sesiones_db(self):
        """Muestra las últimas sesiones guardadas en MySQL."""
        if not self._db.activa:
            ok = self._db.reconectar()
            if not ok:
                messagebox.showwarning(
                    "Sin conexión a MySQL",
                    "No se pudo conectar a MySQL.\n\n"
                    "Verifica:\n"
                    "  1. XAMPP → MySQL en verde\n"
                    "  2. Puerto 3306 disponible\n"
                    "  3. pip install mysql-connector-python\n\n"
                    "Revisa la consola (PowerShell) para\n"
                    "ver el error exacto de conexión."
                )
                return
            else:
                self.lbl_db_st.config(text="DB ●", fg="#4CAF50")
                self._log("BD reconectada exitosamente", "SYS")
        rows = self._db.listar_sesiones()
        if not rows:
            messagebox.showinfo("BD vacía", "No hay sesiones en la base de datos.")
            return
        win = tk.Toplevel(self.parent)
        win.title("Sesiones en MySQL — cohete_db")
        win.configure(bg=BG_ROOT)
        win.geometry("640x360")
        tk.Label(win, text="SESIONES EN BASE DE DATOS",
                 font=(SANS, 11, "bold"), bg=BG_ROOT, fg=NAVY).pack(pady=(12, 4))
        cols = ("ID", "Nombre", "Misión", "Guardado", "Fase", "Eventos")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (50, 180, 90, 150, 90, 70)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="center")
        for r in rows:
            tree.insert("", "end", values=(
                r["id"], r["nombre"], r["mision"],
                str(r["fecha_guardado"])[:16],
                r["fase_final"], r["total_eventos"]
            ))
        sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(12,0), pady=8)
        sb.pack(side="right", fill="y", padx=(0,12), pady=8)

        self._actualizar(datos)



    def _calcular_fase(self, datos: dict) -> str:
        altitud    = datos.get("altitud",    0.0)
        desplegado = datos.get("desplegado", False)

    
        if desplegado and not self._udp_dep_ant:
            self._udp_dep_ant  = True
            self._udp_dep_done = True
            self._udp_apo_det  = True
            print("[FASE] Despliegue confirmado por ESP32")
            return "DESPLIEGUE"

      
        delta              = altitud - self._udp_alt_ant
        self._udp_alt_ant  = altitud

       
        if delta > 0.03:
            self._udp_subiendo  = True
            self._udp_cnt_baj   = 0
            self._udp_cnt_est   = 0

        if delta < -0.03:
            self._udp_cnt_baj += 1
            self._udp_cnt_est  = 0
        elif abs(delta) <= 0.05:
            self._udp_cnt_est     += 1
            self._udp_alt_est_ref  = altitud
        else:
            self._udp_cnt_est = 0

     
        if self._udp_subiendo and self._udp_cnt_baj >= 3 and not self._udp_apo_det:
            self._udp_apo_det  = True
            self._udp_dep_done = True
            print("[FASE] Apogeo detectado localmente → DESPLIEGUE")
            return "DESPLIEGUE"

       
        if self._udp_dep_done and self._udp_cnt_est >= 10 and abs(self._udp_alt_est_ref) < 2.0:
            return "ATERRIZAJE"

        if self._udp_dep_done:
            return "DESCENSO"

      
        if altitud > 0.1 and self._udp_subiendo:
            return "ASCENSO"

      
        return "STANDBY"

    def _servidor_udp(self):
        """Servidor UDP que recibe datos del ESP32. Corre en hilo daemon."""
        PUERTO_UDP = 8082
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", PUERTO_UDP))
        sock.settimeout(1.0)
        print(f"[UDP] Escuchando en puerto {PUERTO_UDP}...")
        print(f"[UDP] Esperando datos del ESP32...")

        root_ref = self.parent.winfo_toplevel()

        while True:
            try:
                datos_raw, addr = sock.recvfrom(1024)
                mensaje = datos_raw.decode("utf-8").strip()
                datos   = json.loads(mensaje)

             
                if datos.get("type", "") != "despliegue":
                    continue

                fase = self._calcular_fase(datos)

                print(f"[ESP32] Alt: {datos.get('altitud', 0):.2f}m | "
                      f"Desplegado: {datos.get('desplegado', False)} | "
                      f"Fase: {fase} | "
                      f"Desde: {addr[0]}")

                datos_app = {
                    "altitud_m":    datos.get("altitud",   0.0),
                    "velocidad_ms": datos.get("velocidad", 0.0),
                    "bateria_pct":  datos.get("bateria",   100.0),
                    "fase":         fase,
                }

           
                root_ref.after(0, lambda d=datos_app: self.recibir_datos(d))

            except socket.timeout:
                continue
            except json.JSONDecodeError as e:
                print(f"[ERROR JSON] {e}")
            except Exception as e:
                print(f"[ERROR UDP] {e}")



if __name__ == "__main__":
    def sim_rec(payload):
        print("\n[RECUPERACIÓN] Estado final:")
        for k, v in payload.items():
            print(f"  {k}: {v}")

   
    root = tk.Tk()
    root.title("Módulo Despliegue v3 — Sala de Control")
    root.state("zoomed")
    root.configure(bg=BG_ROOT)

    frame = tk.Frame(root, bg=BG_ROOT)
    frame.pack(fill="both", expand=True)

    modulo = ModuloDespliegue(frame)
    modulo.on_despliegue_confirmado = sim_rec

   
    print("[APP] Interfaz gráfica iniciada")
    print("[APP] Esperando datos UDP del ESP32 en puerto 8080...")

    root.mainloop()
