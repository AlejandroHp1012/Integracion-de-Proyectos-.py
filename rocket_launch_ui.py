"""
ROCKET LAUNCH CONTROL SYSTEM — INTERFAZ DE DESPEGUE v2.0
Ground Control Station

MODULOS:
  1. Indicador de conexion WiFi (barras de señal)
  2. Panel de estado del dispositivo (recuadro central)
  3. Boton conectar al cohete
  4. Verificacion de señal (barra 0-100%)
  5. Confirmacion de enlace (con leyenda de estado)
  6. Boton Activar Despegue
  7. Boton Desactivar / Abort
  8. Contador de velocidad del viento (sensor externo)

[BLOQUE TELEMETRIA] — marcado con comentario especial
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
import math
import time
import threading

# ======================================================
#  PALETA DE COLORES
# ======================================================
BG_ROOT    = "#04080F"
BG_CARD    = "#0C1624"
BG_CARD2   = "#0A1220"
BG_INPUT   = "#060D18"

CYAN       = "#00D4FF"
GREEN      = "#00FF88"
RED        = "#FF2D55"
AMBER      = "#FFB800"
BLUE_LT    = "#1E90FF"

TEXT_WHITE = "#EAF6FF"
TEXT_GRAY  = "#4A6080"
TEXT_DARK  = "#1E2D40"
BORDER     = "#122035"
BORDER_C   = "#0A4060"

MONO = "Courier New"


# ======================================================
#  HELPER: crear cuadro con titulo
# ======================================================
def make_card(parent, title, accent=None, expand=False):
    if accent is None:
        accent = CYAN
    outer = tk.Frame(parent, bg=accent, bd=1)
    outer.pack(fill="x", pady=5)

    hdr = tk.Frame(outer, bg="#061020", height=36)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Frame(hdr, bg=accent, width=5).pack(side="left", fill="y")
    tk.Label(hdr, text=f"  {title}", font=(MONO, 10, "bold"),
             bg="#061020", fg=accent, anchor="w").pack(side="left", fill="y")

    tk.Frame(outer, bg=accent, height=1).pack(fill="x")

    inner = tk.Frame(outer, bg=BG_CARD, padx=16, pady=12)
    inner.pack(fill="both", expand=expand)
    return inner


# ======================================================
#  VENTANA PRINCIPAL
# ======================================================
class RocketLaunchUI(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("CONTROL SYSTEM DESPEGUE  v2.0")
        self.geometry("1200x870")
        self.minsize(1100, 800)
        self.configure(bg=BG_ROOT)

        # Estado del sistema
        self.system_on        = False  # Estado global: sistema encendido o apagado
        self.wifi_strength    = 0
        self.signal_quality   = 0
        self.wind_speed       = 0.0
        self.rocket_connected = False
        self.signal_verified  = False
        self.link_confirmed   = False
        self.launch_armed     = False
        self.launch_active    = False
        self._running         = True

        self.var_wifi  = tk.StringVar(value="0%")
        self.var_sig   = tk.StringVar(value="0%")
        self.var_wind  = tk.StringVar(value="0.0 km/h")
        self.var_state = tk.StringVar(value="SISTEMA EN STANDBY")

        self._build_header()

        main = tk.Frame(self, bg=BG_ROOT)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.left = tk.Frame(main, bg=BG_ROOT)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.right = tk.Frame(main, bg=BG_ROOT, width=375)
        self.right.pack(side="right", fill="both")
        self.right.pack_propagate(False)

        self._p1_wifi()
        self._p2_device()
        self._p3_signal()
        self._p4_link()
        self._p5_launch()
        self._p6_wind()
        self._p7_telemetry()
        self._build_footer()

        self._start_wifi_sim()
        self._start_wind_sim()
        self._tick_clock()

        self._log("CONTROL SYSTEM DESPEGUE v2.0 INICIADO", "SYS", CYAN)
        self._log("Sistema en estado APAGADO.", "SYS", TEXT_GRAY)
        self._log("Presiona ENCENDER SISTEMA para iniciar.", "SYS", TEXT_GRAY)


    # --------------------------------------------------
    #  HEADER
    # --------------------------------------------------
    def _build_header(self):
        h = tk.Frame(self, bg="#020609", height=75)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Frame(h, bg=CYAN, height=3).pack(fill="x")

        row = tk.Frame(h, bg="#020609")
        row.pack(fill="both", expand=True, padx=18)

        # Título principal actualizado
        tk.Label(row, text="CONTROL SYSTEM DESPEGUE",
                 font=(MONO, 16, "bold"), bg="#020609", fg=CYAN).pack(side="left")
        tk.Label(row, text="   //  GROUND CONTROL STATION  //  MISION ALPHA-001",
                 font=(MONO, 8), bg="#020609", fg=TEXT_GRAY).pack(side="left")

        r = tk.Frame(row, bg="#020609")
        r.pack(side="right")

        # ── BOTONES ENCENDER / APAGAR SISTEMA ────────────────────
        # Estos dos botones controlan el estado global del sistema.
        # ENCENDER activa todos los paneles y sensores.
        # APAGAR resetea todo y bloquea los controles.
        btn_frame = tk.Frame(r, bg="#020609")
        btn_frame.pack(anchor="e", pady=(4, 2))

        self.btn_power_on = tk.Button(
            btn_frame,
            text="  ENCENDER SISTEMA  ",
            font=(MONO, 9, "bold"),
            bg="#003300", fg=GREEN,
            activebackground="#004400", activeforeground=GREEN,
            relief="flat", bd=0, padx=12, pady=6,
            cursor="hand2",
            command=self._power_on
        )
        self.btn_power_on.pack(side="left", padx=(0, 6))

        self.btn_power_off = tk.Button(
            btn_frame,
            text="  APAGAR SISTEMA  ",
            font=(MONO, 9, "bold"),
            bg="#1A0000", fg=RED,
            activebackground="#2A0000", activeforeground=RED,
            relief="flat", bd=0, padx=12, pady=6,
            cursor="hand2",
            state="disabled",   # deshabilitado hasta que se encienda
            command=self._power_off
        )
        self.btn_power_off.pack(side="left")

        # Indicador de estado del sistema
        self.lbl_power_ind = tk.Label(
            btn_frame, text="  SISTEMA APAGADO",
            font=(MONO, 9, "bold"), bg="#020609", fg=TEXT_GRAY
        )
        self.lbl_power_ind.pack(side="left", padx=(10, 0))
        # ─────────────────────────────────────────────────────────

        self.lbl_state = tk.Label(r, textvariable=self.var_state,
                                  font=(MONO, 10, "bold"), bg="#020609", fg=RED)
        self.lbl_state.pack(anchor="e")
        self.lbl_clock = tk.Label(r, text="", font=(MONO, 8),
                                  bg="#020609", fg=TEXT_GRAY)
        self.lbl_clock.pack(anchor="e")
        tk.Frame(h, bg=BLUE_LT, height=1).pack(fill="x", side="bottom")

    def _tick_clock(self):
        self.lbl_clock.config(text=time.strftime("T+%H:%M:%S UTC"))
        self.after(1000, self._tick_clock)


    # --------------------------------------------------
    #  PANEL 1: WiFi
    # --------------------------------------------------
    def _p1_wifi(self):
        inner = make_card(self.left, "PANEL 1 — INDICADOR DE CONEXION WiFi", CYAN)

        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")

        # Barras de señal
        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)

        tk.Label(lb, text="INTENSIDAD DE SEÑAL WiFi",
                 font=(MONO, 9), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        self.wifi_cv = tk.Canvas(lb, width=260, height=70,
                                 bg=BG_CARD, highlightthickness=0)
        self.wifi_cv.pack(anchor="w", pady=(4, 2))

        self.lbl_wifi = tk.Label(lb, textvariable=self.var_wifi,
                                 font=(MONO, 20, "bold"), bg=BG_CARD, fg=CYAN)
        self.lbl_wifi.pack(anchor="w")

        self.lbl_wifi_txt = tk.Label(lb, text="SIN SEÑAL",
                                     font=(MONO, 9, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_wifi_txt.pack(anchor="w")

        tk.Frame(row, bg=BORDER, width=2).pack(side="left", fill="y", padx=16)

        # Boton conectar
        rb = tk.Frame(row, bg=BG_CARD)
        rb.pack(side="left", fill="both", expand=True)

        tk.Label(rb, text="CONEXION CON COHETE",
                 font=(MONO, 9), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w", pady=(0, 8))

        self.btn_connect = tk.Button(
            rb, text="CONECTAR AL COHETE",
            font=(MONO, 12, "bold"), bg="#001833", fg=CYAN,
            activebackground="#002244", activeforeground=CYAN,
            relief="flat", bd=0, pady=18, padx=20,
            cursor="hand2", state="disabled", command=self._do_connect)
        self.btn_connect.pack(fill="x")

        self.lbl_conn_st = tk.Label(rb, text="DESCONECTADO",
                                    font=(MONO, 10, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_conn_st.pack(anchor="w", pady=(10, 0))

        self._draw_wifi(0)

    def _draw_wifi(self, pct):
        c = self.wifi_cv
        c.delete("all")
        for i in range(5):
            x1 = i * 38 + 10
            bh = 60 * ((i + 1) / 5)
            y1 = 65 - bh
            x2 = x1 + 26
            thr = (i + 1) * 20
            color = (GREEN if pct >= 70 else AMBER if pct >= 40 else RED) if pct >= thr else TEXT_DARK
            c.create_rectangle(x1, y1, x2, 65, fill=color, outline="")
        ct = GREEN if pct >= 70 else AMBER if pct >= 40 else RED if pct >= 10 else TEXT_GRAY
        c.create_text(225, 33, text=f"{pct}%", font=(MONO, 13, "bold"), fill=ct)


    # --------------------------------------------------
    #  PANEL 2: Estado del dispositivo
    # --------------------------------------------------
    def _p2_device(self):
        inner = make_card(self.left, "PANEL 2 — ESTADO DEL DISPOSITIVO", BLUE_LT)

        # Recuadro central de evento
        box = tk.Frame(inner, bg=BG_INPUT,
                       highlightbackground=BORDER_C, highlightthickness=2)
        box.pack(fill="x", pady=(0, 10))

        hb = tk.Frame(box, bg="#030F20", height=30)
        hb.pack(fill="x")
        hb.pack_propagate(False)
        tk.Label(hb, text="  ESTADO GENERAL DEL SISTEMA",
                 font=(MONO, 8), bg="#030F20", fg=BLUE_LT,
                 anchor="w").pack(fill="both", expand=True, padx=8)

        self.lbl_dev_ev = tk.Label(box, text="EN ESPERA DE CONEXION",
                                   font=(MONO, 15, "bold"), bg=BG_INPUT,
                                   fg=TEXT_GRAY, pady=20)
        self.lbl_dev_ev.pack(fill="x")

        self.lbl_dev_sb = tk.Label(box,
                                   text="Inicia la conexion WiFi para activar los subsistemas",
                                   font=(MONO, 8), bg=BG_INPUT, fg=TEXT_GRAY, pady=6)
        self.lbl_dev_sb.pack(fill="x")

        # Grid de subsistemas
        g = tk.Frame(inner, bg=BG_CARD)
        g.pack(fill="x")
        self.subsys = {}
        items = [("BATERIA","N/A"),("GPS","N/A"),("GIROSCOPIO","N/A"),
                 ("ALTIMETRO","N/A"),("PROPULSION","N/A"),("TELEMETRIA","N/A")]
        for i, (name, val) in enumerate(items):
            col = i % 3
            row = i // 3
            cell = tk.Frame(g, bg=BG_CARD2, highlightbackground=BORDER,
                            highlightthickness=1)
            cell.grid(row=row, column=col, padx=4, pady=4,
                      sticky="ew", ipadx=8, ipady=8)
            g.columnconfigure(col, weight=1)
            tk.Label(cell, text=name, font=(MONO, 7),
                     bg=BG_CARD2, fg=TEXT_GRAY).pack()
            lbl = tk.Label(cell, text=val, font=(MONO, 10, "bold"),
                           bg=BG_CARD2, fg=TEXT_DARK)
            lbl.pack()
            self.subsys[name] = lbl

    def _set_device(self, state):
        cfgs = {
            "standby":    ("EN ESPERA DE CONEXION",
                           "Inicia la conexion WiFi para activar los subsistemas", TEXT_GRAY),
            "connecting": ("ESTABLECIENDO CONEXION...",
                           "Enviando señal de handshake al cohete", AMBER),
            "connected":  ("COHETE CONECTADO EXITOSAMENTE",
                           "Todos los subsistemas en linea", GREEN),
            "armed":      ("SISTEMA ARMADO — LISTO PARA DESPEGUE",
                           "Enlace confirmado — Lanzamiento autorizado", CYAN),
            "launch":     ("SECUENCIA DE LANZAMIENTO ACTIVA",
                           "Cuenta regresiva en curso — NO INTERRUMPIR", RED),
            "abort":      ("SECUENCIA ABORTADA",
                           "Sistema en modo seguro", AMBER),
        }
        t, s, c = cfgs.get(state, cfgs["standby"])
        self.lbl_dev_ev.config(text=t, fg=c)
        self.lbl_dev_sb.config(text=s)
        if state in ("connected", "armed"):
            data = {"BATERIA":("98.4%",GREEN),"GPS":("ACTIVO",GREEN),
                    "GIROSCOPIO":("OK",GREEN),"ALTIMETRO":("0 m",CYAN),
                    "PROPULSION":("STANDBY",AMBER),"TELEMETRIA":("ONLINE",GREEN)}
            for k,(v,col) in data.items():
                if k in self.subsys:
                    self.subsys[k].config(text=v, fg=col)
        elif state in ("standby","abort"):
            for l in self.subsys.values():
                l.config(text="N/A", fg=TEXT_DARK)


    # --------------------------------------------------
    #  PANEL 3: Verificacion de señal
    # --------------------------------------------------
    def _p3_signal(self):
        inner = make_card(self.left, "PANEL 3 — VERIFICACION DE SEÑAL  (0% a 100%)", AMBER)

        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")

        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)

        tk.Label(lb, text="CALIDAD DE SEÑAL RF",
                 font=(MONO, 9), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Sig.Horizontal.TProgressbar",
                     troughcolor="#030A14", background=AMBER,
                     thickness=28, bordercolor=BORDER)

        self.sig_bar = ttk.Progressbar(lb, orient="horizontal",
                                       mode="determinate",
                                       style="Sig.Horizontal.TProgressbar",
                                       maximum=100)
        self.sig_bar.pack(fill="x", pady=(6, 3))

        sc = tk.Frame(lb, bg=BG_CARD)
        sc.pack(fill="x")
        for t in ["0%","25%","50%","75%","100%"]:
            tk.Label(sc, text=t, font=(MONO, 7),
                     bg=BG_CARD, fg=TEXT_GRAY).pack(side="left", expand=True)

        self.lbl_sig_val = tk.Label(lb, textvariable=self.var_sig,
                                    font=(MONO, 22, "bold"), bg=BG_CARD, fg=AMBER)
        self.lbl_sig_val.pack(anchor="w", pady=(6, 0))

        self.lbl_sig_st = tk.Label(lb, text="En espera...",
                                   font=(MONO, 9), bg=BG_CARD, fg=TEXT_GRAY)
        self.lbl_sig_st.pack(anchor="w")

        tk.Frame(row, bg=BORDER, width=2).pack(side="left", fill="y", padx=16)

        self.btn_verify = tk.Button(
            row, text="VERIFICAR\nSEÑAL",
            font=(MONO, 11, "bold"), bg="#1A1000", fg=AMBER,
            activebackground="#2A1800", activeforeground=AMBER,
            relief="flat", bd=0, width=12, pady=20,
            cursor="hand2", state="disabled",
            command=self._do_verify)
        self.btn_verify.pack(side="left")


    # --------------------------------------------------
    #  PANEL 4: Confirmacion de enlace
    # --------------------------------------------------
    def _p4_link(self):
        inner = make_card(self.left, "PANEL 4 — CONFIRMACION DE ENLACE", GREEN)

        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")

        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)

        self.link_box = tk.Frame(lb, bg="#020F08",
                                 highlightbackground=GREEN, highlightthickness=2)
        self.link_box.pack(fill="x", pady=(0, 8))

        tk.Label(self.link_box, text="  ESTADO DEL ENLACE",
                 font=(MONO, 9), bg="#020F08", fg=GREEN,
                 anchor="w", pady=5).pack(fill="x", padx=8)
        tk.Frame(self.link_box, bg=GREEN, height=1).pack(fill="x")

        self.lbl_link_m = tk.Label(self.link_box, text="FALTA CONEXION",
                                   font=(MONO, 16, "bold"), bg="#020F08",
                                   fg=RED, pady=14)
        self.lbl_link_m.pack(fill="x")

        self.lbl_link_d = tk.Label(
            self.link_box,
            text="No se ha establecido conexion con el cohete.\n"
                 "Motivo: Señal no verificada — Presiona CONECTAR primero.",
            font=(MONO, 8), bg="#020F08", fg=TEXT_GRAY,
            justify="left", pady=6)
        self.lbl_link_d.pack(fill="x", padx=10)

        # Checklist
        pf = tk.Frame(lb, bg=BG_CARD)
        pf.pack(fill="x")
        tk.Label(pf, text="CHECKLIST DE ENLACE:",
                 font=(MONO, 8), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

        self.checks = {}
        for key, label in [("WiFi","Conexion WiFi activa"),
                            ("Cohete","Cohete conectado"),
                            ("Señal","Señal verificada (>80%)")]:
            f = tk.Frame(pf, bg=BG_CARD)
            f.pack(fill="x", pady=1)
            d = tk.Label(f, text="X  " + label, font=(MONO, 9),
                         bg=BG_CARD, fg=RED)
            d.pack(side="left")
            self.checks[key] = d

        tk.Frame(row, bg=BORDER, width=2).pack(side="left", fill="y", padx=16)

        self.btn_confirm = tk.Button(
            row, text="CONFIRMAR\nENLACE",
            font=(MONO, 11, "bold"), bg="#001A08", fg=GREEN,
            activebackground="#002A10", activeforeground=GREEN,
            relief="flat", bd=0, width=12, pady=20,
            cursor="hand2", state="disabled",
            command=self._do_confirm)
        self.btn_confirm.pack(side="left")

    def _set_check(self, key, ok):
        lbl = self.checks.get(key)
        if not lbl:
            return
        old = lbl.cget("text")[3:]
        if ok:
            lbl.config(text="OK " + old, fg=GREEN)
        else:
            lbl.config(text="X  " + old, fg=RED)


    # --------------------------------------------------
    #  PANEL 5: Control de lanzamiento
    # --------------------------------------------------
    def _p5_launch(self):
        inner = make_card(self.left, "PANEL 5 — CONTROL DE DESPEGUE  [ ZONA CRITICA ]", RED)

        ar = tk.Frame(inner, bg=BG_CARD)
        ar.pack(fill="x", pady=(0, 10))
        tk.Label(ar, text="AUTORIZACION:", font=(MONO, 10),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="left")
        self.lbl_auth = tk.Label(ar, text="  DENEGADA — ENLACE NO ESTABLECIDO",
                                 font=(MONO, 11, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_auth.pack(side="left")

        self.lbl_cd = tk.Label(inner, text="T — 00:00",
                               font=(MONO, 36, "bold"), bg=BG_CARD, fg=TEXT_DARK)
        self.lbl_cd.pack(pady=(0, 12))

        br = tk.Frame(inner, bg=BG_CARD)
        br.pack(fill="x")
        br.columnconfigure(0, weight=1)
        br.columnconfigure(1, weight=1)

        self.btn_launch = tk.Button(
            br, text="ACTIVAR DESPEGUE",
            font=(MONO, 14, "bold"), bg="#200000", fg=RED,
            activebackground="#380000", activeforeground="#FF6060",
            relief="flat", bd=0, pady=22, cursor="hand2",
            state="disabled", command=self._do_launch)
        self.btn_launch.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.btn_abort = tk.Button(
            br, text="DESACTIVAR / ABORT",
            font=(MONO, 14, "bold"), bg="#1A1000", fg=AMBER,
            activebackground="#2A1800", activeforeground="#FFD000",
            relief="flat", bd=0, pady=22, cursor="hand2",
            state="disabled", command=self._do_abort)
        self.btn_abort.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.lbl_wind_warn = tk.Label(inner, text="",
                                      font=(MONO, 9, "bold"),
                                      bg=BG_CARD, fg=AMBER)
        self.lbl_wind_warn.pack(pady=(10, 0))


    # --------------------------------------------------
    #  PANEL 6: Velocidad del viento (columna derecha)
    # --------------------------------------------------
    def _p6_wind(self):
        """
        PANEL DEL SENSOR DE VIENTO.
        Para conectar sensor real, sustituir _start_wind_sim()
        con lectura de puerto serial o GPIO.
        """
        inner = make_card(self.right, "VELOCIDAD DEL VIENTO (SENSOR)", CYAN)

        self.wind_cv = tk.Canvas(inner, width=330, height=185,
                                 bg=BG_CARD, highlightthickness=0)
        self.wind_cv.pack(pady=(0, 6))
        self._draw_gauge(0)

        self.lbl_wind_big = tk.Label(inner, textvariable=self.var_wind,
                                     font=(MONO, 26, "bold"), bg=BG_CARD, fg=CYAN)
        self.lbl_wind_big.pack()

        self.lbl_wind_cond = tk.Label(inner, text="CALMO",
                                      font=(MONO, 10, "bold"), bg=BG_CARD, fg=GREEN)
        self.lbl_wind_cond.pack(pady=(2, 8))

        st = ttk.Style()
        st.configure("Wind.Horizontal.TProgressbar",
                     troughcolor="#030A14", background=GREEN,
                     thickness=14, bordercolor=BORDER)
        self.wind_bar = ttk.Progressbar(inner, orient="horizontal",
                                        mode="determinate",
                                        style="Wind.Horizontal.TProgressbar",
                                        maximum=150)
        self.wind_bar.pack(fill="x")

        sc = tk.Frame(inner, bg=BG_CARD)
        sc.pack(fill="x")
        tk.Label(sc, text="0 km/h", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="left")
        tk.Label(sc, text="150 km/h", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(side="right")

    def _draw_gauge(self, speed):
        c = self.wind_cv
        c.delete("all")
        cx, cy, r = 165, 170, 135

        for color, s, e in [(GREEN,0,60),(AMBER,60,120),(RED,120,180)]:
            c.create_arc(cx-r, cy-r, cx+r, cy+r,
                         start=s+180, extent=e,
                         style="arc", outline=color, width=16)

        ms = 150
        ang = math.radians(180 - (min(speed, ms) / ms) * 180)
        nx = cx + (r - 22) * math.cos(ang)
        ny = cy - (r - 22) * math.sin(ang)
        c.create_line(cx, cy, nx, ny, fill=TEXT_WHITE, width=4, capstyle="round")
        c.create_oval(cx-8, cy-8, cx+8, cy+8, fill=CYAN, outline="")

        for v in [0, 30, 60, 90, 120, 150]:
            a = math.radians(180 - (v / ms) * 180)
            lx = cx + (r + 18) * math.cos(a)
            ly = cy - (r + 18) * math.sin(a)
            c.create_text(lx, ly, text=str(v), fill=TEXT_GRAY, font=(MONO, 8))

        c.create_text(cx, cy - 35, text="km/h", fill=TEXT_GRAY, font=(MONO, 9))


    # --------------------------------------------------
    #  PANEL 7: Telemetria (columna derecha)
    # --------------------------------------------------
    def _p7_telemetry(self):
        outer = tk.Frame(self.right, bg=BLUE_LT, bd=1)
        outer.pack(fill="both", expand=True, pady=5)

        hdr = tk.Frame(outer, bg="#061020", height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=BLUE_LT, width=5).pack(side="left", fill="y")
        tk.Label(hdr, text="  TELEMETRIA EN TIEMPO REAL",
                 font=(MONO, 10, "bold"), bg="#061020",
                 fg=BLUE_LT, anchor="w").pack(side="left", fill="y")

        tk.Frame(outer, bg=BLUE_LT, height=1).pack(fill="x")

        inner = tk.Frame(outer, bg=BG_CARD, padx=8, pady=8)
        inner.pack(fill="both", expand=True)

        self.telem = tk.Text(inner, bg="#020A14", fg=GREEN,
                             font=(MONO, 8), relief="flat", bd=0,
                             state="disabled", wrap="word",
                             insertbackground=GREEN)
        self.telem.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(inner, bg=BG_CARD, troughcolor=BG_CARD,
                          activebackground=CYAN, relief="flat")
        sb.pack(side="right", fill="y")
        self.telem.config(yscrollcommand=sb.set)
        sb.config(command=self.telem.yview)

        self.telem.tag_configure("cyan",  foreground=CYAN)
        self.telem.tag_configure("green", foreground=GREEN)
        self.telem.tag_configure("red",   foreground=RED)
        self.telem.tag_configure("amber", foreground=AMBER)
        self.telem.tag_configure("gray",  foreground=TEXT_GRAY)
        self.telem.tag_configure("white", foreground=TEXT_WHITE)


    # ==================================================
    #  METODO DE TELEMETRIA
    #
    #  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #  INICIO BLOQUE — ENLACE CON INTERFAZ DE TELEMETRIA
    #
    #  Este metodo centraliza TODOS los eventos del sistema.
    #  Para enviar datos a la interfaz de telemetria externa
    #  agrega tu codigo debajo de este comentario:
    #
    #  OPCION A — Socket TCP:
    #    self.sock.sendall(f"{tag}|{msg}\n".encode())
    #
    #  OPCION B — MQTT:
    #    self.mqtt.publish("rocket/telemetry", json.dumps(payload))
    #
    #  OPCION C — Puerto Serial (microcontrolador):
    #    self.serial.write(f"{tag}|{msg}\n".encode())
    #
    #  OPCION D — Llamada directa a modulo Python:
    #    telemetry_module.receive(tag, msg, payload)
    #
    #  El diccionario 'payload' tiene el estado completo
    #  del sistema listo para serializar en JSON o CSV.
    #
    #  FIN BLOQUE — ENLACE CON INTERFAZ DE TELEMETRIA
    #  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    # ==================================================
    def _log(self, msg, tag="SYS", color=None):
        ts = time.strftime("%H:%M:%S")

        # Payload del estado completo — ENVIAR A TELEMETRIA EXTERNA
        payload = {
            "timestamp":        ts,
            "tag":              tag,
            "message":          msg,
            "wifi_strength":    self.wifi_strength,
            "signal_quality":   self.signal_quality,
            "wind_speed_kmh":   self.wind_speed,
            "rocket_connected": self.rocket_connected,
            "signal_verified":  self.signal_verified,
            "link_confirmed":   self.link_confirmed,
            "launch_armed":     self.launch_armed,
            "launch_active":    self.launch_active,
        }
        # --- AGREGAR AQUI: socket / mqtt / serial / modulo externo ---

        line = f"[{ts}] [{tag:6s}]  {msg}\n"
        tag_map = {
            CYAN: "cyan", GREEN: "green", RED: "red",
            AMBER: "amber", TEXT_GRAY: "gray"
        }
        ttag = tag_map.get(color, "white")

        self.telem.config(state="normal")
        self.telem.insert("end", line, ttag)
        self.telem.config(state="disabled")
        self.telem.see("end")


    # --------------------------------------------------
    #  SIMULACION DE SENSORES
    # --------------------------------------------------
    def _start_wifi_sim(self):
        def run():
            s = 5
            while self._running:
                s = max(70, min(100, s + random.randint(-3, 4))) if self.rocket_connected \
                    else max(0, min(20, s + random.randint(-2, 3)))
                self.wifi_strength = s
                self.after(0, lambda v=s: self._upd_wifi(v))
                time.sleep(1.0)
        threading.Thread(target=run, daemon=True).start()

    def _upd_wifi(self, s):
        self._draw_wifi(s)
        self.var_wifi.set(f"{s}%")
        if s >= 70:
            self.lbl_wifi_txt.config(text="SEÑAL EXCELENTE", fg=GREEN)
        elif s >= 40:
            self.lbl_wifi_txt.config(text="SEÑAL MODERADA",  fg=AMBER)
        elif s >= 15:
            self.lbl_wifi_txt.config(text="SEÑAL DEBIL",     fg=RED)
        else:
            self.lbl_wifi_txt.config(text="SIN SEÑAL",       fg=TEXT_GRAY)
        self._set_check("WiFi", s >= 40)

    def _start_wind_sim(self):
        """
        SENSOR DE VIENTO — SIMULADO.
        Reemplazar con lectura real del anemometro.
        Ej: ser = serial.Serial('COM3', 9600)
            speed = float(ser.readline().decode().strip())
        """
        def run():
            sp = 5.0
            while self._running:
                sp = max(0, min(145, sp + random.gauss(0, 4)))
                self.wind_speed = round(sp, 1)
                self.after(0, lambda v=self.wind_speed: self._upd_wind(v))
                time.sleep(0.9)
        threading.Thread(target=run, daemon=True).start()

    def _upd_wind(self, sp):
        self.var_wind.set(f"{sp:.1f} km/h")
        self.wind_bar["value"] = min(sp, 150)
        self._draw_gauge(sp)

        if sp < 25:
            cond, col, warn = "CALMO — OPTIMO", GREEN, ""
        elif sp < 55:
            cond, col, warn = "BRISA — ACEPTABLE", CYAN, ""
        elif sp < 85:
            cond, col = "VIENTO FUERTE — PRECAUCION", AMBER
            warn = f"VIENTO ELEVADO ({sp:.0f} km/h) — Evaluar lanzamiento"
        else:
            cond, col = "VIENTO CRITICO — RIESGO", RED
            warn = f"VIENTO PELIGROSO ({sp:.0f} km/h) — NO LANZAR"

        self.lbl_wind_cond.config(text=cond, fg=col)
        if hasattr(self, "lbl_wind_warn"):
            self.lbl_wind_warn.config(text=warn)


    # --------------------------------------------------
    #  ACCIONES DE BOTONES
    # --------------------------------------------------
    def _do_connect(self):
        if not self.system_on:
            messagebox.showwarning("Sistema apagado",
                                   "Debes ENCENDER el sistema primero.")
            return
        self.btn_connect.config(state="disabled", text="CONECTANDO...")
        self._set_device("connecting")
        self.var_state.set("CONECTANDO...")
        self.lbl_state.config(fg=AMBER)
        self._log("Iniciando conexion con cohete...", "NET", AMBER)

        steps = [(600,"Buscando dispositivo en red..."),
                 (1400,"Dispositivo encontrado — handshake..."),
                 (2300,"Handshake recibido — autenticando..."),
                 (3200,"Autenticacion OK — canal seguro..."),
                 (4000,"CONEXION EXITOSA")]

        def do(i=0):
            if i < len(steps):
                d, m = steps[i]
                self.after(d, lambda msg=m: self._log(msg, "NET", AMBER))
                self.after(d, lambda: do(i + 1))
            else:
                self.after(4200, self._on_connected)
        do()

    def _on_connected(self):
        self.rocket_connected = True
        self.btn_connect.config(text="CONECTADO", fg=GREEN, bg="#001800")
        self.lbl_conn_st.config(text="CONECTADO CON COHETE", fg=GREEN)
        self.var_state.set("COHETE CONECTADO")
        self.lbl_state.config(fg=GREEN)
        self._set_device("connected")
        self._set_check("Cohete", True)
        self.btn_verify.config(state="normal")
        self.lbl_link_m.config(text="SEÑAL AUN NO VERIFICADA", fg=AMBER)
        self.lbl_link_d.config(
            text="Cohete conectado.\nMotivo pendiente: Verificar calidad de señal RF.")
        self._log("COHETE CONECTADO EXITOSAMENTE", "NET", GREEN)
        self._log("Estado Telemetria: ROCKET_CONNECTED", "TELEM", CYAN)

    def _do_verify(self):
        self.btn_verify.config(state="disabled", text="VERIFICANDO...")
        self._log("Verificando señal RF...", "RF", AMBER)
        self.lbl_sig_st.config(text="Midiendo calidad de señal...", fg=AMBER)

        def anim(v=0):
            if v <= 94:
                self.sig_bar["value"] = v
                self.var_sig.set(f"{v}%")
                c = GREEN if v > 70 else AMBER if v > 40 else RED
                self.lbl_sig_val.config(fg=c)
                self.after(28, lambda: anim(v + 2))
            else:
                self._on_verified()
        anim()

    def _on_verified(self):
        self.signal_verified = True
        self.signal_quality = 94
        self.sig_bar["value"] = 94
        self.var_sig.set("94%")
        self.lbl_sig_val.config(fg=GREEN)
        self.lbl_sig_st.config(text="SEÑAL EXCELENTE — SNR: 42 dB", fg=GREEN)
        self.btn_verify.config(text="VERIFICADO", fg=GREEN, bg="#001800")
        self._set_check("Señal", True)
        self.btn_confirm.config(state="normal")
        self.lbl_link_m.config(text="LISTO PARA CONFIRMAR ENLACE", fg=CYAN)
        self.lbl_link_d.config(
            text="Señal RF verificada (94%).\nPresiona CONFIRMAR ENLACE para autorizar.")
        self._log("Señal verificada — 94% — SNR 42 dB", "RF", GREEN)
        self._log("Estado Telemetria: SIGNAL_VERIFIED", "TELEM", CYAN)

    def _do_confirm(self):
        self.link_confirmed = self.launch_armed = True
        self.lbl_link_m.config(text="CONEXION EXITOSA — ENLACE CONFIRMADO", fg=GREEN)
        self.lbl_link_d.config(
            text="Todos los subsistemas en linea.\nLanzamiento AUTORIZADO.", fg=GREEN)
        self.link_box.config(highlightbackground=GREEN, bg="#010F06")
        self.lbl_link_m.config(bg="#010F06")
        self.lbl_link_d.config(bg="#010F06")
        self.btn_confirm.config(state="disabled", text="CONFIRMADO",
                                fg=GREEN, bg="#001800")
        self.btn_launch.config(state="normal")
        self.btn_abort.config(state="normal")
        self.lbl_cd.config(fg=CYAN)
        self.lbl_auth.config(text="  AUTORIZADA — ENLACE CONFIRMADO", fg=GREEN)
        self._set_device("armed")
        self.var_state.set("SISTEMA ARMADO — LISTO")
        self.lbl_state.config(fg=GREEN)
        self._log("ENLACE CONFIRMADO — LANZAMIENTO AUTORIZADO", "LAUNCH", GREEN)
        self._log("Estado Telemetria: LAUNCH_AUTHORIZED", "TELEM", CYAN)
        messagebox.showinfo("Enlace Confirmado",
                            "Conexion exitosa.\n\nTodos los subsistemas confirmados.\n"
                            "Lanzamiento AUTORIZADO.\n\nProcede con precaucion.")

    def _do_launch(self):
        ok = messagebox.askyesno(
            "CONFIRMACION DE LANZAMIENTO",
            "Confirmas ACTIVAR el despegue?\n\nOPERACION CRITICA E IRREVERSIBLE",
            icon="warning")
        if not ok:
            return
        self.launch_active = True
        self.btn_launch.config(state="disabled")
        self.lbl_auth.config(text="  SECUENCIA ACTIVA — CUENTA REGRESIVA", fg=RED)
        self._set_device("launch")
        self.var_state.set("LANZAMIENTO ACTIVO")
        self.lbl_state.config(fg=RED)
        self._log("SECUENCIA DE LANZAMIENTO INICIADA", "LAUNCH", RED)
        self._log("Estado Telemetria: LAUNCH_SEQUENCE_ACTIVE", "TELEM", RED)
        self._cdown(10)

    def _cdown(self, n):
        if n >= 0:
            c = RED if n <= 3 else AMBER if n <= 6 else CYAN
            self.lbl_cd.config(text=f"T — 00:{n:02d}", fg=c)
            if n > 0:
                self._log(f"Cuenta regresiva: T-{n:02d}", "LAUNCH", c)
            self.after(1000, lambda: self._cdown(n - 1))
        else:
            self.lbl_cd.config(text="LIFTOFF!", fg=GREEN)
            self._log("LIFTOFF — DESPEGUE EXITOSO", "LAUNCH", GREEN)
            self._log("Estado Telemetria: LIFTOFF_CONFIRMED", "TELEM", GREEN)

    def _do_abort(self):
        ok = messagebox.askyesno("ABORT", "Confirmas DESACTIVAR el despegue?",
                                 icon="question")
        if not ok:
            return
        self.launch_active = self.launch_armed = False
        self.btn_launch.config(state="disabled")
        self.btn_abort.config(state="disabled")
        self.lbl_cd.config(text="T — 00:00", fg=TEXT_DARK)
        self.lbl_auth.config(text="  SECUENCIA ABORTADA", fg=AMBER)
        self._set_device("abort")
        self.var_state.set("SECUENCIA ABORTADA")
        self.lbl_state.config(fg=AMBER)
        self._log("ABORT — SECUENCIA DESACTIVADA", "LAUNCH", AMBER)
        self._log("Sistema en modo SEGURO.", "SYS", AMBER)
        self._log("Estado Telemetria: ABORT_CONFIRMED", "TELEM", CYAN)


    # --------------------------------------------------
    #  ENCENDER / APAGAR SISTEMA
    # --------------------------------------------------
    def _power_on(self):
        """
        Enciende el sistema completo.
        Habilita todos los controles, activa sensores
        y registra el evento en telemetria.
        """
        if self.system_on:
            return

        self.system_on = True

        # Actualizar botones de poder
        self.btn_power_on.config(state="disabled", bg="#001A00")
        self.btn_power_off.config(state="normal", bg="#2A0000")
        self.lbl_power_ind.config(text="  SISTEMA ENCENDIDO", fg=GREEN)

        # Actualizar estado general
        self.var_state.set("SISTEMA ACTIVO")
        self.lbl_state.config(fg=GREEN)

        # Habilitar botón de conexión
        self.btn_connect.config(state="normal")

        # Resetear checklist al encender
        for key in self.checks:
            self._set_check(key, False)

        # Log en telemetría
        self._log("=" * 38, "SYS", CYAN)
        self._log("SISTEMA ENCENDIDO POR OPERADOR", "SYS", GREEN)
        self._log("Todos los modulos activos.", "SYS", GREEN)
        self._log("Estado Telemetria: SYSTEM_ON", "TELEM", CYAN)
        self._log("=" * 38, "SYS", CYAN)

    def _power_off(self):
        """
        Apaga el sistema completo.
        Resetea todos los estados, deshabilita controles
        y registra el apagado en telemetria.
        """
        if not self.system_on:
            return

        ok = messagebox.askyesno(
            "APAGAR SISTEMA",
            "Confirmas APAGAR el sistema completo?\n\n"
            "Se desactivaran todos los modulos y\n"
            "se perdera la conexion con el cohete.",
            icon="warning"
        )
        if not ok:
            return

        self.system_on        = False
        self.rocket_connected = False
        self.signal_verified  = False
        self.link_confirmed   = False
        self.launch_armed     = False
        self.launch_active    = False
        self.wifi_strength    = 0
        self.signal_quality   = 0

        # Actualizar botones de poder
        self.btn_power_on.config(state="normal", bg="#003300")
        self.btn_power_off.config(state="disabled", bg="#1A0000")
        self.lbl_power_ind.config(text="  SISTEMA APAGADO", fg=TEXT_GRAY)

        # Resetear estado general
        self.var_state.set("SISTEMA APAGADO")
        self.lbl_state.config(fg=TEXT_GRAY)

        # Resetear panel WiFi
        self.btn_connect.config(state="disabled", text="CONECTAR AL COHETE",
                                fg=CYAN, bg="#001833")
        self.lbl_conn_st.config(text="DESCONECTADO", fg=RED)
        self.var_wifi.set("0%")
        self.lbl_wifi_txt.config(text="SIN SEÑAL", fg=TEXT_GRAY)
        self._draw_wifi(0)

        # Resetear verificacion de señal
        self.btn_verify.config(state="disabled", text="VERIFICAR\nSEÑAL",
                               fg=AMBER, bg="#1A1000")
        self.sig_bar["value"] = 0
        self.var_sig.set("0%")
        self.lbl_sig_val.config(fg=AMBER)
        self.lbl_sig_st.config(text="En espera...", fg=TEXT_GRAY)

        # Resetear panel de enlace
        self.btn_confirm.config(state="disabled", text="CONFIRMAR\nENLACE",
                                fg=GREEN, bg="#001A08")
        self.lbl_link_m.config(text="SISTEMA APAGADO", fg=TEXT_GRAY,
                               bg="#020F08")
        self.lbl_link_d.config(
            text="El sistema fue apagado por el operador.\n"
                 "Presiona ENCENDER SISTEMA para reiniciar.",
            fg=TEXT_GRAY, bg="#020F08")
        self.link_box.config(highlightbackground=GREEN, bg="#020F08")

        # Resetear checklist
        for key in self.checks:
            self._set_check(key, False)

        # Resetear panel de lanzamiento
        self.btn_launch.config(state="disabled")
        self.btn_abort.config(state="disabled")
        self.lbl_cd.config(text="T — 00:00", fg=TEXT_DARK)
        self.lbl_auth.config(text="  DENEGADA — SISTEMA APAGADO", fg=TEXT_GRAY)
        self.lbl_wind_warn.config(text="")

        # Resetear subsistemas
        self._set_device("standby")

        # Log final en telemetría
        self._log("=" * 38, "SYS", AMBER)
        self._log("SISTEMA APAGADO POR OPERADOR", "SYS", AMBER)
        self._log("Todos los modulos desactivados.", "SYS", AMBER)
        self._log("Estado Telemetria: SYSTEM_OFF", "TELEM", CYAN)
        self._log("=" * 38, "SYS", AMBER)

    # --------------------------------------------------
    #  FOOTER
    # --------------------------------------------------
    def _build_footer(self):
        f = tk.Frame(self, bg="#020609", height=26)
        f.pack(fill="x", side="bottom")
        f.pack_propagate(False)
        tk.Frame(f, bg=BLUE_LT, height=1).pack(fill="x", side="top")
        tk.Label(f,
                 text="SISTEMA CRITICO — USO EXCLUSIVO OPERADORES AUTORIZADOS"
                      "  |  MISION: ALPHA-001  |  GROUND CONTROL v2.0",
                 font=(MONO, 7), bg="#020609", fg=TEXT_GRAY).pack(side="left", padx=14)
        self.dot = tk.Label(f, text="*", font=(MONO, 12, "bold"),
                            bg="#020609", fg=TEXT_DARK)
        self.dot.pack(side="right", padx=14)
        self._blink()

    def _blink(self):
        c = self.dot.cget("fg")
        self.dot.config(fg=CYAN if c == TEXT_DARK else TEXT_DARK)
        self.after(700, self._blink)

    def on_close(self):
        self._running = False
        self.destroy()


# ======================================================
#  PUNTO DE ENTRADA
# ======================================================
if __name__ == "__main__":
    app = RocketLaunchUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
