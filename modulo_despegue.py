"""
╔══════════════════════════════════════════════════════╗
║  MÓDULO DESPEGUE — Equipo 1                         ║
║  Clase: ModuloDespegue                              ║
║  Recibe un tk.Frame como contenedor                 ║
╚══════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
import threading

# ── Colores ──────────────────────────────────────────
BG_ROOT  = "#04080F"
BG_CARD  = "#0C1624"
BG_CARD2 = "#0A1220"
BG_INPUT = "#060D18"
CYAN     = "#00D4FF"
GREEN    = "#00FF88"
RED      = "#FF2D55"
AMBER    = "#FFB800"
BLUE_LT  = "#1E90FF"
TEXT_GRAY = "#4A6080"
TEXT_DARK = "#1E2D40"
BORDER   = "#122035"
BORDER_C = "#0A4060"
MONO     = "Courier New"


def make_card(parent, title, accent=None, expand=False):
    if accent is None:
        accent = CYAN
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
    """
    Módulo de control de Despegue.
    Recibe un tk.Frame como parent_frame — NO crea su propia ventana.
    """
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

        self.var_wifi  = tk.StringVar(value="0%")
        self.var_sig   = tk.StringVar(value="0%")
        self.var_wind  = tk.StringVar(value="0.0 km/h")
        self.var_state = tk.StringVar(value="STANDBY")

        self._build_header()

        main = tk.Frame(self.parent, bg=BG_ROOT)
        main.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self.left = tk.Frame(main, bg=BG_ROOT)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.right = tk.Frame(main, bg=BG_ROOT, width=200)
        self.right.pack(side="right", fill="both")
        self.right.pack_propagate(False)

        self._p1_wifi()
        self._p2_device()
        self._p3_signal()
        self._p4_link()
        self._p5_launch()
        self._p6_wind()
        self._p7_telemetry()

        self._start_wifi_sim()
        self._start_wind_sim()
        self._tick_clock()
        self._log("CONTROL SYSTEM DESPEGUE v2.0 INICIADO", "SYS", CYAN)
        self._log("Presiona ENCENDER SISTEMA para iniciar.", "SYS", TEXT_GRAY)

    def _build_header(self):
        h = tk.Frame(self.parent, bg="#020609", height=50)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Frame(h, bg=CYAN, height=2).pack(fill="x")

        row = tk.Frame(h, bg="#020609")
        row.pack(fill="both", expand=True, padx=10)

        tk.Label(row, text="🚀 DESPEGUE",
                 font=(MONO, 11, "bold"), bg="#020609", fg=CYAN).pack(side="left")
        tk.Label(row, text="  MISION ALPHA-001",
                 font=(MONO, 7), bg="#020609", fg=TEXT_GRAY).pack(side="left")

        r = tk.Frame(row, bg="#020609")
        r.pack(side="right")

        btn_frame = tk.Frame(r, bg="#020609")
        btn_frame.pack(anchor="e")

        self.btn_power_on = tk.Button(
            btn_frame, text="ENCENDER",
            font=(MONO, 7, "bold"), bg="#003300", fg=GREEN,
            relief="flat", bd=0, padx=6, pady=3, cursor="hand2",
            command=self._power_on)
        self.btn_power_on.pack(side="left", padx=(0, 3))

        self.btn_power_off = tk.Button(
            btn_frame, text="APAGAR",
            font=(MONO, 7, "bold"), bg="#1A0000", fg=RED,
            relief="flat", bd=0, padx=6, pady=3, cursor="hand2",
            state="disabled", command=self._power_off)
        self.btn_power_off.pack(side="left")

        self.lbl_state = tk.Label(r, textvariable=self.var_state,
                                  font=(MONO, 7, "bold"), bg="#020609", fg=RED)
        self.lbl_state.pack(anchor="e")
        self.lbl_clock = tk.Label(r, text="", font=(MONO, 7),
                                  bg="#020609", fg=TEXT_GRAY)
        self.lbl_clock.pack(anchor="e")
        tk.Frame(h, bg=BLUE_LT, height=1).pack(fill="x", side="bottom")

    def _tick_clock(self):
        self.lbl_clock.config(text=time.strftime("T+%H:%M:%S"))
        self.parent.after(1000, self._tick_clock)

    def _p1_wifi(self):
        inner = make_card(self.left, "CONEXION WiFi", CYAN)
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")

        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)

        tk.Label(lb, text="INTENSIDAD DE SEÑAL", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
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
            bh = 44 * ((i + 1) / 5)
            y1 = 48 - bh
            x2 = x1 + 18
            thr = (i + 1) * 20
            color = (GREEN if pct >= 70 else AMBER if pct >= 40 else RED) if pct >= thr else TEXT_DARK
            c.create_rectangle(x1, y1, x2, 48, fill=color, outline="")
        ct = GREEN if pct >= 70 else AMBER if pct >= 40 else RED if pct >= 10 else TEXT_GRAY
        c.create_text(148, 25, text=f"{pct}%", font=(MONO, 9, "bold"), fill=ct)

    def _p2_device(self):
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
        items = [("BATERIA","N/A"),("GPS","N/A"),("GIROSCOPIO","N/A"),
                 ("ALTIMETRO","N/A"),("PROPULSION","N/A"),("TELEMETRIA","N/A")]
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

    def _set_device(self, state):
        cfgs = {
            "standby":    ("EN ESPERA DE CONEXION", "Inicia conexion WiFi", TEXT_GRAY),
            "connecting": ("ESTABLECIENDO CONEXION...", "Handshake al cohete", AMBER),
            "connected":  ("COHETE CONECTADO", "Subsistemas en linea", GREEN),
            "armed":      ("ARMADO — LISTO", "Lanzamiento autorizado", CYAN),
            "launch":     ("SECUENCIA ACTIVA", "NO INTERRUMPIR", RED),
            "abort":      ("SECUENCIA ABORTADA", "Modo seguro", AMBER),
        }
        t, s, c = cfgs.get(state, cfgs["standby"])
        self.lbl_dev_ev.config(text=t, fg=c)
        self.lbl_dev_sb.config(text=s)
        if state in ("connected", "armed"):
            data = {"BATERIA":("98%",GREEN),"GPS":("OK",GREEN),
                    "GIROSCOPIO":("OK",GREEN),"ALTIMETRO":("0 m",CYAN),
                    "PROPULSION":("EN ESPERA",AMBER),"TELEMETRIA":("ACTIVA",GREEN)}
            for k,(v,col) in data.items():
                if k in self.subsys:
                    self.subsys[k].config(text=v, fg=col)
        elif state in ("standby","abort"):
            for l in self.subsys.values():
                l.config(text="N/A", fg=TEXT_DARK)

    def _p3_signal(self):
        inner = make_card(self.left, "VERIFICACION DE SEÑAL", AMBER)
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")
        lb = tk.Frame(row, bg=BG_CARD)
        lb.pack(side="left", fill="x", expand=True)
        tk.Label(lb, text="CALIDAD DE SEÑAL RADIOFRECUENCIA", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")

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
        self.lbl_sig_st = tk.Label(lb, text="En espera...",
                                   font=(MONO, 7), bg=BG_CARD, fg=TEXT_GRAY)
        self.lbl_sig_st.pack(anchor="w")

        tk.Frame(row, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
        self.btn_verify = tk.Button(
            row, text="VERIFICAR\nSEÑAL",
            font=(MONO, 8, "bold"), bg="#1A1000", fg=AMBER,
            relief="flat", bd=0, width=8, pady=12,
            cursor="hand2", state="disabled",
            command=self._do_verify)
        self.btn_verify.pack(side="left")

    def _p4_link(self):
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
        for key, label in [("WiFi","WiFi activa"),
                            ("Cohete","Cohete conectado"),
                            ("Señal","Señal >80%")]:
            f = tk.Frame(lb, bg=BG_CARD)
            f.pack(fill="x", pady=1)
            d = tk.Label(f, text="✗  " + label, font=(MONO, 7),
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
        if key in self.checks:
            self.checks[key].config(
                text=("✓  " if ok else "✗  ") + self.checks[key].cget("text")[3:],
                fg=GREEN if ok else RED)

    def _p5_launch(self):
        inner = make_card(self.right, "LANZAMIENTO", RED)
        self.lbl_auth = tk.Label(inner, text="  DENEGADA",
                                 font=(MONO, 7, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_auth.pack(anchor="w", pady=(0, 4))
        self.lbl_cd = tk.Label(inner, text="T — 00:00",
                               font=(MONO, 16, "bold"), bg=BG_CARD, fg=TEXT_DARK)
        self.lbl_cd.pack(pady=4)
        self.btn_launch = tk.Button(
            inner, text="▶ ACTIVAR DESPEGUE",
            font=(MONO, 8, "bold"), bg="#1A0000", fg=RED,
            relief="flat", bd=0, pady=8,
            cursor="hand2", state="disabled",
            command=self._do_launch)
        self.btn_launch.pack(fill="x", pady=(4, 2))
        self.btn_abort = tk.Button(
            inner, text="■ ABORTAR SECUENCIA",
            font=(MONO, 8, "bold"), bg="#0A0600", fg=AMBER,
            relief="flat", bd=0, pady=8,
            cursor="hand2", state="disabled",
            command=self._do_abort)
        self.btn_abort.pack(fill="x")

    def _p6_wind(self):
        inner = make_card(self.right, "VIENTO", CYAN)
        tk.Label(inner, text="VELOCIDAD VIENTO", font=(MONO, 7),
                 bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        self.lbl_wind_val = tk.Label(inner, textvariable=self.var_wind,
                                     font=(MONO, 13, "bold"), bg=BG_CARD, fg=CYAN)
        self.lbl_wind_val.pack(anchor="w")
        self.lbl_wind_warn = tk.Label(inner, text="",
                                      font=(MONO, 7, "bold"), bg=BG_CARD, fg=AMBER)
        self.lbl_wind_warn.pack(anchor="w")

    def _p7_telemetry(self):
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

    def _start_wifi_sim(self):
        def _sim():
            while self._running:
                if self.system_on and self.rocket_connected:
                    self.wifi_strength = min(100, self.wifi_strength + random.randint(-3, 5))
                elif self.system_on:
                    self.wifi_strength = random.randint(20, 60)
                else:
                    self.wifi_strength = 0
                self.wifi_strength = max(0, min(100, self.wifi_strength))
                pct = self.wifi_strength
                self.var_wifi.set(f"{pct}%")
                self._draw_wifi(pct)
                color = GREEN if pct >= 70 else AMBER if pct >= 40 else RED
                txt = "EXCELENTE" if pct >= 70 else "MODERADA" if pct >= 40 else "DEBIL"
                self.lbl_wifi_txt.config(text=txt, fg=color)
                self._set_check("WiFi", pct >= 40)
                time.sleep(1)
        threading.Thread(target=_sim, daemon=True).start()

    def _start_wind_sim(self):
        def _sim():
            while self._running:
                if self.system_on:
                    self.wind_speed = random.uniform(0, 45)
                    self.var_wind.set(f"{self.wind_speed:.1f} km/h")
                    if self.wind_speed > 35:
                        self.lbl_wind_warn.config(text="⚠ VIENTO CRITICO", fg=RED)
                    elif self.wind_speed > 20:
                        self.lbl_wind_warn.config(text="VIENTO MODERADO", fg=AMBER)
                    else:
                        self.lbl_wind_warn.config(text="CONDICIONES OK", fg=GREEN)
                time.sleep(2)
        threading.Thread(target=_sim, daemon=True).start()

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
        self._log("SISTEMA ENCENDIDO", "SYS", GREEN)

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
        self.lbl_cd.config(text="T — 00:00", fg=TEXT_DARK)
        self.lbl_auth.config(text="  DENEGADA", fg=TEXT_GRAY)
        self._set_device("standby")
        self._log("SISTEMA APAGADO", "SYS", AMBER)

    def _do_connect(self):
        if not self.system_on:
            return
        self.btn_connect.config(state="disabled", text="CONECTANDO...", fg=AMBER)
        self.lbl_conn_st.config(text="CONECTANDO...", fg=AMBER)
        self._set_device("connecting")
        self._log("Iniciando conexion con cohete...", "CONN", AMBER)
        self.parent.after(2000, self._connect_done)

    def _connect_done(self):
        self.rocket_connected = True
        self.btn_connect.config(text="✓ CONECTADO", fg=GREEN, bg="#001A08")
        self.lbl_conn_st.config(text="CONECTADO", fg=GREEN)
        self._set_device("connected")
        self._set_check("Cohete", True)
        self.btn_verify.config(state="normal")
        self._log("COHETE CONECTADO EXITOSAMENTE", "CONN", GREEN)

    def _do_verify(self):
        self.btn_verify.config(state="disabled", text="VERIFICANDO...", fg=AMBER)
        self._log("Verificando señal RF...", "SIG", AMBER)
        self.parent.after(3000, self._verify_done)

    def _verify_done(self):
        q = random.randint(70, 99)
        self.signal_quality = q
        self.sig_bar["value"] = q
        self.var_sig.set(f"{q}%")
        ok = q >= 80
        self.signal_verified = ok
        color = GREEN if ok else RED
        self.lbl_sig_val.config(fg=color)
        self.lbl_sig_st.config(text="SEÑAL OK" if ok else "SEÑAL INSUFICIENTE", fg=color)
        self._set_check("Señal", ok)
        self.btn_verify.config(text="VERIFICAR\nSEÑAL", fg=AMBER)
        if ok:
            self.btn_confirm.config(state="normal")
        self._log(f"Señal verificada: {q}%", "SIG", color)

    def _do_confirm(self):
        self.link_confirmed = True
        self.lbl_link_m.config(text="ENLACE CONFIRMADO", fg=GREEN)
        self.lbl_link_d.config(text="Todos los subsistemas confirmados.")
        self.btn_confirm.config(state="disabled", fg=GREEN, bg="#001800")
        self.btn_launch.config(state="normal")
        self.btn_abort.config(state="normal")
        self.lbl_cd.config(fg=CYAN)
        self.lbl_auth.config(text="  AUTORIZADA", fg=GREEN)
        self._set_device("armed")
        self.var_state.set("ARMADO")
        self.lbl_state.config(fg=GREEN)
        self._log("ENLACE CONFIRMADO — LANZAMIENTO AUTORIZADO", "LAUNCH", GREEN)

    def _do_launch(self):
        ok = messagebox.askyesno("CONFIRMAR LANZAMIENTO",
                                 "¿Activar despegue? OPERACION CRITICA",
                                 icon="warning")
        if not ok:
            return
        self.launch_active = True
        self.btn_launch.config(state="disabled")
        self.lbl_auth.config(text="  CUENTA REGRESIVA", fg=RED)
        self._set_device("launch")
        self.var_state.set("LANZAMIENTO")
        self.lbl_state.config(fg=RED)
        self._log("SECUENCIA DE LANZAMIENTO INICIADA", "LAUNCH", RED)
        self._cdown(10)

    def _cdown(self, n):
        if n >= 0:
            c = RED if n <= 3 else AMBER if n <= 6 else CYAN
            self.lbl_cd.config(text=f"T — 00:{n:02d}", fg=c)
            if n > 0:
                self._log(f"T-{n:02d}", "LAUNCH", c)
            self.parent.after(1000, lambda: self._cdown(n - 1))
        else:
            self.lbl_cd.config(text="LIFTOFF!", fg=GREEN)
            self._log("LIFTOFF — DESPEGUE EXITOSO", "LAUNCH", GREEN)

    def _do_abort(self):
        ok = messagebox.askyesno("ABORT", "¿Confirmas ABORTAR?", icon="question")
        if not ok:
            return
        self.launch_active = self.launch_armed = False
        self.btn_launch.config(state="disabled")
        self.btn_abort.config(state="disabled")
        self.lbl_cd.config(text="T — 00:00", fg=TEXT_DARK)
        self.lbl_auth.config(text="  ABORTADA", fg=AMBER)
        self._set_device("abort")
        self.var_state.set("ABORTADO")
        self.lbl_state.config(fg=AMBER)
        self._log("ABORT — SECUENCIA DESACTIVADA", "LAUNCH", AMBER)
