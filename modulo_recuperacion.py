import tkinter as tk
from tkinter import ttk, messagebox
import math
from datetime import datetime
import time
import threading
import json
import os
import socket  # <--- NUEVA LIBRERÍA PARA EL WI-FI

import shared_state as SS   # Bus de datos compartido

# ── Paleta de colores MEJORADA — alto contraste ───────
C = {
    "bg":           "#0D1117",
    "panel":        "#161B22",
    "card":         "#1C2333",
    "input_bg":     "#0D1117",
    "border":       "#2EA043",
    "border_hi":    "#3FB950",
    "border_dim":   "#1A3A20",
    "green":        "#3FB950",
    "green_bright": "#56D364",
    "green_dim":    "#238636",
    "amber":        "#E3B341",
    "amber_dim":    "#B08800",
    "cyan":         "#58A6FF",
    "cyan_bright":  "#79C0FF",
    "red_alert":    "#F85149",
    "red_dim":      "#8B1A1A",
    "white":        "#E6EDF3",
    "gray":         "#8B949E",
    "gray_dim":     "#484F58",
    "radar_bg":     "#020B02",
    "mapa_bg":      "#020A0E",
    "grid":         "#0D2318",
    "scanline":     "#0A1A0A",
}

LED_OFF   = "off"
LED_OK    = "ok"
LED_ERROR = "error"
LED_COLORS = {
    LED_OFF:   {"center": "#484F58", "ring": "#2D333B", "glow": "#161B22"},
    LED_OK:    {"center": "#56D364", "ring": "#3FB950", "glow": "#1A3A20"},
    LED_ERROR: {"center": "#F85149", "ring": "#DA3633", "glow": "#3D0B0B"},
}

FONT_MONO   = ("Courier New", 7,  "bold")
FONT_MONO_S = ("Courier New", 8,  "bold")
FONT_MONO_L = ("Courier New", 9,  "bold")
FONT_MONO_XL= ("Courier New", 10, "bold")
FONT_VALUE  = ("Courier New", 9,  "bold")
FONT_HEADER = ("Courier New", 9,  "bold")


class FocoLED(tk.Canvas):
    SIZE = 16
    def __init__(self, parent, bg_color, **kw):
        super().__init__(parent, width=self.SIZE, height=self.SIZE,
                         bg=bg_color, highlightthickness=0, **kw)
        self._state = LED_OFF
        self._anim_id = None
        self._pulse = 0
        self._draw()

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        if self._anim_id:
            self.after_cancel(self._anim_id)
            self._anim_id = None
        self._pulse = 0
        if state == LED_OK:
            self._animate()
        else:
            self._draw()

    def _draw(self, brightness=1.0):
        self.delete("all")
        c = LED_COLORS[self._state]
        s = self.SIZE
        self.create_oval(0, 0, s, s, fill=c["glow"], outline="")
        p = s * 0.18
        self.create_oval(p, p, s-p, s-p, fill=c["ring"], outline="")
        p2 = s * 0.38
        cc = self._blend(c["center"], brightness)
        self.create_oval(p2, p2, s-p2, s-p2, fill=cc, outline="")
        if self._state != LED_OFF:
            self.create_oval(s*0.22, s*0.18, s*0.52, s*0.46,
                             fill="#ffffff", outline="")

    def _animate(self):
        self._pulse = (self._pulse + 0.18) % (2 * math.pi)
        b = 0.70 + 0.30 * math.sin(self._pulse)
        self._draw(b)
        self._anim_id = self.after(55, self._animate)

    @staticmethod
    def _blend(hx, b):
        hx = hx.lstrip("#")
        r  = int(int(hx[0:2], 16) * b)
        g  = int(int(hx[2:4], 16) * b)
        bl = int(int(hx[4:6], 16) * b)
        return f"#{r:02x}{g:02x}{bl:02x}"


class ModuloRecuperacion:
    def __init__(self, parent_frame):
        self.root = parent_frame

        self.sistema_activo = False
        self._modo_espejo   = False
        self.escuchando_wifi = False
        self.latitud   = 22.16100
        self.longitud  = -102.26877
        self.altitud   = 2500.0
        self.velocidad = 0.0
        self.distancia = 1500.0
        self.angulo_radar    = 0
        self.hora_gps       = "--:--:--"
        self.wifi_strength  = 0
        self.signal_quality = 0
        self._launch_state  = "STANDBY"
        self.trayectoria = []
        self._tick = 0
        self._leds: dict = {}
        self._json_buffer: list = []
        self._json_last_flush: float = 0.0
        self._json_last_save: float  = 0.0
        self._json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "telemetria_log.json")

        self._construir_ui()
        self._loop()

        self._log(f"Sistema iniciado — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log("Aguardando activación del subsistema de recuperación...")
        self._log(f"Pos base: {self.latitud:.4f}°N, {self.longitud:.4f}°W  Alt: {self.altitud:.0f}m")

    def _construir_ui(self):
        hdr = tk.Frame(self.root, bg=C["panel"], height=38)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border_hi"], height=2).pack(fill=tk.X)

        inner_hdr = tk.Frame(hdr, bg=C["panel"])
        inner_hdr.pack(fill=tk.BOTH, expand=True, padx=10)

        logo_f = tk.Frame(inner_hdr, bg=C["panel"])
        logo_f.pack(side=tk.LEFT)
        tk.Label(logo_f, text="🪂  RECUPERACIÓN",
                 font=("Courier New", 9, "bold"),
                 bg=C["panel"], fg=C["green_bright"]).pack(side=tk.LEFT)
        tk.Label(logo_f, text="   Misión Alpha-001",
                 font=("Courier New", 7), bg=C["panel"],
                 fg=C["gray"]).pack(side=tk.LEFT)

        right_hdr = tk.Frame(inner_hdr, bg=C["panel"])
        right_hdr.pack(side=tk.RIGHT)

        btn_row = tk.Frame(right_hdr, bg=C["panel"])
        btn_row.pack(anchor="e")

        self._btn = tk.Button(
            btn_row, text="⏻  ACTIVAR",
            font=("Courier New", 8, "bold"),
            bg="#1A3A20", fg=C["green_bright"],
            activebackground="#2A5A30", activeforeground=C["green_bright"],
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
            command=self._toggle)
        self._btn.pack(side=tk.LEFT, padx=(0, 6))

        self._sys_lbl = tk.Label(
            btn_row, text="● INACTIVO",
            font=("Courier New", 7, "bold"),
            bg=C["panel"], fg=C["red_alert"])
        self._sys_lbl.pack(side=tk.LEFT, padx=(0, 8))

        tk.Frame(hdr, bg=C["border_dim"], height=1).pack(fill=tk.X, side=tk.BOTTOM)

        status_bar = tk.Frame(self.root, bg=C["card"], height=18)
        status_bar.pack(fill=tk.X, padx=4)
        status_bar.pack_propagate(False)

        self._status_items = []
        for key, val in [("SISTEMA","NOMINAL"),("COMUNICACION","SIN ENLACE"),
                          ("GPS","EN ESPERA"),("DISTANCIA","1500m"),("ALTITUD","2500m")]:
            f = tk.Frame(status_bar, bg=C["card"])
            f.pack(side=tk.LEFT, padx=8)
            tk.Label(f, text=key+":", font=FONT_MONO_S,
                     bg=C["card"], fg=C["amber_dim"]).pack(side=tk.LEFT)
            lbl = tk.Label(f, text=val, font=FONT_MONO_S,
                           bg=C["card"], fg=C["green"])
            lbl.pack(side=tk.LEFT, padx=(2, 0))
            self._status_items.append((key, lbl))

        tk.Frame(status_bar, bg=C["border_dim"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=3, padx=6)
        self._modo_lbl = tk.Label(
            status_bar, text="◉ MODO: TIEMPO REAL",
            font=FONT_MONO_S, bg=C["card"], fg=C["amber"])
        self._modo_lbl.pack(side=tk.LEFT, padx=8)

        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        body.columnconfigure(0, weight=10)
        body.columnconfigure(1, weight=10)
        body.columnconfigure(2, weight=12)
        body.rowconfigure(0, weight=1)

        col_left = tk.Frame(body, bg=C["bg"])
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self._build_radar(col_left)

        col_center = tk.Frame(body, bg=C["bg"])
        col_center.grid(row=0, column=1, sticky="nsew", padx=2)
        self._build_mapa(col_center)

        col_right = tk.Frame(body, bg=C["bg"])
        col_right.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
        self._build_telemetria(col_right)

        self._build_console()

    def _build_radar(self, parent):
        frame = tk.Frame(parent, bg=C["panel"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 3))
        self._panel_header(frame, "RADAR // SEGUIMIENTO DE BLANCO")
        self.canvas_radar = tk.Canvas(frame, bg=C["radar_bg"], highlightthickness=0)
        self.canvas_radar.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

    def _build_mapa(self, parent):
        frame = tk.Frame(parent, bg=C["panel"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 3))
        self._panel_header(frame, "MAPA // REPRESENTACIÓN TÁCTICA")
        self.canvas_mapa = tk.Canvas(frame, bg=C["mapa_bg"], highlightthickness=0)
        self.canvas_mapa.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

    def _build_telemetria(self, parent):
        frame = tk.Frame(parent, bg=C["panel"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True)
        self._panel_header(frame, "TELEMETRÍA // DATOS EN VIVO")

        inner = tk.Frame(frame, bg=C["panel"])
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=3)

        ley = tk.Frame(inner, bg=C["card"],
                       highlightbackground=C["border_dim"], highlightthickness=1)
        ley.pack(fill=tk.X, pady=(0, 3))
        tk.Label(ley, text=" SEÑAL:", font=FONT_MONO_S,
                 bg=C["card"], fg=C["amber_dim"]).pack(side=tk.LEFT, padx=4)
        for state, txt, col in [(LED_OK,   "ACTIVO",   C["green_bright"]),
                                 (LED_ERROR,"ERROR",    C["red_alert"])]:
            led = FocoLED(ley, bg_color=C["card"])
            led.set_state(state)
            led.pack(side=tk.LEFT, padx=(6, 1), pady=3)
            tk.Label(ley, text=txt, font=FONT_MONO_S,
                     bg=C["card"], fg=col).pack(side=tk.LEFT, padx=(0, 4))

        for lbl, var, key in [
            ("LATITUD",  "latitud_valor",  "latitud"),
            ("LONGITUD", "longitud_valor", "longitud"),
            ("ALTITUD",  "altitud_valor",  "altitud"),
            ("HORA GPS", "hora_gps_valor", "hora_gps"),
            ("VELOCIDAD","velocidad_valor","velocidad"),
            ("DISTANCIA","distancia_valor","distancia"),
        ]:
            self._campo_telem(inner, lbl, var, key)

        tk.Frame(inner, bg=C["border_dim"], height=1).pack(fill=tk.X, pady=3)

        hf = tk.Frame(inner, bg=C["card"],
                      highlightbackground=C["border"], highlightthickness=1)
        hf.pack(fill=tk.X, pady=(0, 3))
        tk.Label(hf, text="T // HORA SISTEMA", font=FONT_MONO_S,
                 bg=C["card"], fg=C["amber_dim"]).pack(pady=(2, 0))
        self.hora_valor = tk.Label(
            hf, text="--:--:--",
            font=("Courier New", 12, "bold"),
            bg=C["card"], fg=C["amber"])
        self.hora_valor.pack(pady=(0, 2))

        tk.Frame(inner, bg=C["border_dim"], height=1).pack(fill=tk.X, pady=(0, 3))

        tk.Frame(inner, bg=C["border_dim"], height=1).pack(fill=tk.X, pady=2)

        self.conexion_label = tk.Label(
            inner, text="◌ ENLACE: DESCONECTADO",
            font=FONT_MONO_S, bg=C["panel"], fg=C["red_alert"])
        self.conexion_label.pack(pady=(0, 2))

        tk.Frame(inner, bg=C["border_dim"], height=1).pack(fill=tk.X, pady=2)

        # ── Indicador de señal WiFi ─────────────────────────────
        sf = tk.Frame(inner, bg=C["card"],
                      highlightbackground=C["border_dim"], highlightthickness=1)
        sf.pack(fill=tk.X, pady=(0, 3))
        tk.Label(sf, text="SEÑAL WiFi // UDP",
                 font=FONT_MONO_S, bg=C["card"], fg=C["amber_dim"]).pack(pady=(2, 0))
        self.canvas_wifi = tk.Canvas(sf, bg=C["card"], highlightthickness=0, height=52)
        self.canvas_wifi.pack(fill=tk.X, padx=8, pady=(2, 6))
        self._lbl_wifi_pct = tk.Label(sf, text="-- %  SIN SEÑAL",
                                      font=FONT_MONO_S, bg=C["card"], fg=C["gray"])
        self._lbl_wifi_pct.pack(pady=(0, 4))

        tk.Frame(inner, bg=C["border_dim"], height=1).pack(fill=tk.X, pady=2)

    def _build_console(self):
        frame = tk.Frame(self.root, bg=C["panel"],
                         highlightbackground=C["border"],
                         highlightthickness=1, height=110)
        frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        frame.pack_propagate(False)
        self._panel_header(frame, "CONSOLA // REGISTRO DE EVENTOS")
        self._console = tk.Text(
            frame, bg=C["radar_bg"], fg=C["green"],
            font=("Courier New", 6), relief=tk.FLAT,
            state=tk.DISABLED, wrap=tk.WORD, height=6,
            insertbackground=C["green_bright"], highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self._console.yview)
        self._console.configure(yscrollcommand=sb.set)
        self._console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 4))

    def _panel_header(self, parent, titulo):
        h = tk.Frame(parent, bg=C["card"], height=18)
        h.pack(fill=tk.X)
        h.pack_propagate(False)
        tk.Frame(h, bg=C["border_hi"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(h, text=f"  {titulo}", font=FONT_HEADER,
                 bg=C["card"], fg=C["amber"], anchor="w").pack(
                 side=tk.LEFT, fill=tk.Y)
        return h

    def _campo_telem(self, parent, label, var_name, campo_key):
        row = tk.Frame(parent, bg=C["bg"],
                       highlightbackground=C["border_dim"], highlightthickness=1)
        row.pack(fill=tk.X, pady=1)

        tk.Label(row, text=f" {label}", font=FONT_MONO_S,
                 bg=C["card"], fg=C["amber_dim"], width=9,
                 anchor="w").pack(side=tk.LEFT, fill=tk.Y, ipady=2)
        tk.Frame(row, bg=C["border_dim"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        valor = tk.Label(row, text="───────",
                         font=("Courier New", 8, "bold"),
                         bg=C["bg"], fg=C["green_bright"],
                         anchor="e", padx=4, pady=2)
        valor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        setattr(self, var_name, valor)

        tk.Frame(row, bg=C["border_dim"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        led = FocoLED(row, bg_color=C["bg"])
        led.pack(side=tk.LEFT, padx=4)
        self._leds[campo_key] = led

        etxt = tk.Label(row, text="INACTIVO",
                        font=("Courier New", 6, "bold"),
                        bg=C["bg"], fg=C["gray"], width=7)
        etxt.pack(side=tk.LEFT, padx=(0, 4))
        setattr(self, f"_etxt_{campo_key}", etxt)

    def _log(self, msg):
        t = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._console.config(state=tk.NORMAL)
        self._console.insert(tk.END, f"[{t}] {msg}\n")
        self._console.see(tk.END)
        self._console.config(state=tk.DISABLED)

    def _set_led(self, key, state):
        if key not in self._leds:
            return
        self._leds[key].set_state(state)
        w = getattr(self, f"_etxt_{key}", None)
        if w:
            cfg = {
                LED_OK:    ("ACTIVO",   C["green_bright"]),
                LED_ERROR: ("ERROR",    C["red_alert"]),
                LED_OFF:   ("INACTIVO", C["gray"]),
            }[state]
            w.config(text=cfg[0], fg=cfg[1])

    def _actualizar_leds(self):
        state = LED_OK if self.sistema_activo else LED_OFF
        for campo in ["latitud", "longitud", "altitud", "hora_gps",
                      "velocidad", "distancia"]:
            self._set_led(campo, state)

    def _dibujar_wifi(self):
        c = self.canvas_wifi
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return

        # Leer señal del shared_state (0-100)
        try:
            ss = SS.snapshot()
            pct = ss.get("wifi_strength", 0) if self.sistema_activo else 0
        except Exception:
            pct = 0

        # 5 barras tipo celular
        n_barras = 5
        bar_w = 14
        gap   = 8
        total = n_barras * bar_w + (n_barras - 1) * gap
        x0    = (w - total) / 2
        umbral = pct / 100 * n_barras  # cuántas barras encender

        for i in range(n_barras):
            bx    = x0 + i * (bar_w + gap)
            bh    = int((h - 10) * (i + 1) / n_barras)
            by    = h - bh - 2
            activa = (i + 1) <= umbral

            if activa:
                if pct >= 70:   col = C["green_bright"]
                elif pct >= 40: col = C["amber"]
                else:           col = C["red_alert"]
            else:
                col = C["gray_dim"]

            c.create_rectangle(bx, by, bx + bar_w, h - 2,
                               fill=col, outline="", width=0)

        # Etiqueta de porcentaje y estado
        if pct >= 70:
            txt, fg = f"{pct}%  FUERTE",   C["green_bright"]
        elif pct >= 40:
            txt, fg = f"{pct}%  DÉBIL",    C["amber"]
        elif pct > 0:
            txt, fg = f"{pct}%  MUY DÉBIL", C["red_alert"]
        else:
            txt, fg = "-- %  SIN SEÑAL",   C["gray"]

        self._lbl_wifi_pct.config(text=txt, fg=fg)

    def _dibujar_radar(self):
        c = self.canvas_radar
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 - 20

        for y in range(0, h, 4):
            c.create_line(0, y, w, y,
                          fill=C["scanline"] if y % 8 == 0 else C["radar_bg"])

        for i in range(1, 5):
            r = R * i / 4
            col = ["#1A3A1A", "#143214", "#0F280F", "#0A1E0A"][i-1]
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=1)
            dist_km = (self.distancia / 1000) * i / 4
            c.create_text(cx + r - 6, cy - 10, text=f"{dist_km:.1f}",
                          fill=C["green_dim"], font=("Courier New", 7), anchor="e")

        c.create_line(cx, cy-R, cx, cy+R, fill=C["green_dim"], dash=(2, 6))
        c.create_line(cx-R, cy, cx+R, cy, fill=C["green_dim"], dash=(2, 6))
        c.create_oval(cx-5, cy-5, cx+5, cy+5,
                      fill=C["green_bright"], outline=C["green"])

        if self.sistema_activo:
            # Barrido giratorio
            ar_sweep = math.radians(self.angulo_radar)
            for i in range(8):
                a_trail = math.radians(self.angulo_radar - i * 4)
                fade_g = max(0, int(180 * (1 - i / 8)))
                fade = f"#00{fade_g:02x}00"
                ex = cx + R * math.cos(a_trail)
                ey = cy - R * math.sin(a_trail)
                c.create_line(cx, cy, ex, ey,
                              fill=C["border_hi"] if i == 0 else fade,
                              width=2 if i == 0 else 1)

            # Calcular rumbo real del cohete respecto a la base
            if self.distancia > 0:
                dlat = self.latitud  - 22.16100
                dlon = self.longitud - (-102.26877)
                bearing_rad = math.atan2(dlon, dlat)  # Norte = arriba

                # Escalar distancia al radio del radar
                max_dist = max(self.distancia * 1.5, 100)
                dr = min(self.distancia / max_dist, 1.0) * 0.85

                bx = cx + R * dr * math.sin(bearing_rad)
                by = cy - R * dr * math.cos(bearing_rad)

                ps = 10 + 5 * abs(math.sin(self._tick * 0.15))
                c.create_oval(bx-ps, by-ps, bx+ps, by+ps,
                              outline=C["amber"], width=1)
                c.create_oval(bx-5, by-5, bx+5, by+5,
                              fill=C["amber"], outline="")
                c.create_text(bx+14, by-12,
                              text=f"▲ {self.distancia:.0f}m",
                              fill=C["amber"], font=FONT_MONO_S)

        estado = "ACTIVO ◉" if self.sistema_activo else "EN ESPERA ○"
        c.create_text(8, 8, text=f"RADAR // {estado}",
                      fill=C["green_bright"], font=FONT_MONO_S, anchor="nw")
        c.create_text(w-8, 8, text=f"AZ {self.angulo_radar:03d}°",
                      fill=C["amber"], font=FONT_MONO_S, anchor="ne")
        c.create_text(8, h-8, text=f"R {self.distancia:.0f}m",
                      fill=C["cyan"], font=("Courier New", 7), anchor="sw")

    def _dibujar_mapa_sim(self):
        c = self.canvas_mapa
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return

        gs = 50
        for x in range(0, w, gs):
            c.create_line(x, 0, x, h, fill=C["grid"])
        for y in range(0, h, gs):
            c.create_line(0, y, w, y, fill=C["grid"])
        for xi, x in enumerate(range(0, w, gs)):
            for yi, y in enumerate(range(0, h, gs)):
                if xi % 2 == 0 and yi % 2 == 0:
                    c.create_text(x+2, y+2, text=f"{xi},{yi}",
                                  fill=C["green_dim"],
                                  font=("Courier New", 6), anchor="nw")

        bx, by = w//2, h//2
        c.create_rectangle(bx-8, by-8, bx+8, by+8,
                            fill="#0D2318", outline=C["green"], width=2)
        c.create_text(bx, by, text="✦", fill=C["green_bright"],
                      font=("Courier New", 10))
        c.create_text(bx, by-16, text="◈ BASE",
                      fill=C["green_bright"], font=FONT_MONO_S)

        if self.sistema_activo:
            px = w/2 + (self.longitud - (-102.26877)) * 200000
            py = h/2 - (self.latitud - 22.16100) * 200000
            px = max(20, min(w-20, px))
            py = max(20, min(h-20, py))

            c.create_line(bx, by, px, py,
                          fill=C["cyan"], width=1, dash=(8, 4))
            mx, my = (bx+int(px))//2, (by+int(py))//2
            c.create_text(mx+2, my-8, text=f"{self.distancia:.0f}m",
                          fill=C["cyan_bright"], font=("Courier New", 7))

            ps = 14 + 3*abs(math.sin(self._tick*0.15))
            c.create_oval(px-ps, py-ps, px+ps, py+ps,
                          outline=C["amber"], width=1, dash=(4, 3))
            c.create_polygon(px, py-12, px-8, py+8, px+8, py+8,
                             fill=C["amber"], outline=C["white"], width=1)
            c.create_text(px, py+22, text=f"▲ {self.altitud:.0f}m",
                          fill=C["amber"], font=FONT_MONO_S)

        for x, y, ay in [(0,0,"nw"),(w,0,"ne"),(0,h,"sw"),(w,h,"se")]:
            c.create_text(x, y, text="◈", fill=C["border"],
                          font=("Courier New", 10), anchor=ay)
        c.create_text(8, h-8, text=f"LAT {self.latitud:.4f}°",
                      fill=C["amber_dim"], font=("Courier New", 7), anchor="sw")
        c.create_text(w-8, h-8, text=f"LON {self.longitud:.4f}°",
                      fill=C["amber_dim"], font=("Courier New", 7), anchor="se")

    def _loop(self):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.hora_valor.config(text=now_str)
        self._tick += 1

        if self.sistema_activo:
            # ── Leer datos desde el bus compartido (Despegue → Recuperación) ──
            ss = SS.snapshot()

            # Leer datos desde el bus compartido (ESP32 → shared_state)
            self.wifi_strength  = ss.get("wifi_strength",  self.wifi_strength)
            self.signal_quality = ss.get("signal_quality", self.signal_quality)
            self.altitud        = ss.get("altitud",        self.altitud)
            self.velocidad      = ss.get("velocidad",      self.velocidad)
            self.latitud        = ss.get("latitud",        self.latitud)
            self.longitud       = ss.get("longitud",       self.longitud)
            self.distancia      = ss.get("distancia",      self.distancia)
            self.hora_gps       = ss.get("hora_gps",       now_str)
            self._launch_state  = ss.get("launch_state",   "STANDBY")

            # Rotar radar
            self.angulo_radar = (self.angulo_radar + 5) % 360

            self.latitud_valor.config( text=f"{self.latitud:.6f}°")
            self.longitud_valor.config(text=f"{self.longitud:.6f}°")
            self.altitud_valor.config( text=f"{self.altitud:.1f} m")
            self.hora_gps_valor.config(text=self.hora_gps)
            self.velocidad_valor.config(text=f"{self.velocidad:.2f} m/s")
            self.distancia_valor.config(text=f"{self.distancia:.0f} m")

            # Actualizar barra de estado
            for key, lbl in self._status_items:
                if key == "DISTANCIA":
                    lbl.config(text=f"{self.distancia:.0f}m")
                elif key == "ALTITUD":
                    lbl.config(text=f"{self.altitud:.0f}m")

            if self._tick % 30 == 0:
                src = "WiFi"
                self._log(
                    f"[{src}] POS {self.latitud:.5f}° {self.longitud:.5f}°  "
                    f"ALT {self.altitud:.1f}m  DST {self.distancia:.0f}m")

            ahora = time.time()
            if ahora - self._json_last_save >= 15.0:
                self._json_last_save = ahora
                self._guardar_json()

        self._actualizar_leds()
        self._dibujar_radar()
        self._dibujar_mapa_sim()
        self._dibujar_wifi()
        self.root.after(100, self._loop)

    def _guardar_json(self):
        muestra = {
            "timestamp":    datetime.now().isoformat(timespec="seconds"),
            "latitud":      round(self.latitud,    6),
            "longitud":     round(self.longitud,   6),
            "altitud_m":    round(self.altitud,    2),
            "distancia_m":  round(self.distancia,  1),
            "velocidad_ms": round(self.velocidad,  2),
            "angulo_radar": self.angulo_radar,
            "hora_gps":     self.hora_gps,
        }
        try:
            if os.path.exists(self._json_path):
                with open(self._json_path, "r", encoding="utf-8") as f:
                    datos = json.load(f)
            else:
                datos = []
            datos.append(muestra)
            with open(self._json_path, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            self._log(f">>> JSON guardado — {len(datos)} registros")
        except Exception as e:
            self._log(f">>> ERROR al guardar JSON: {e}")

    def _toggle(self):
        if self.sistema_activo:
            # Pedir confirmación para DESACTIVAR
            resultado = messagebox.askyesno(
                "DESACTIVAR SISTEMA",
                "¿Estás seguro de que deseas DESACTIVAR el sistema?",
                icon=messagebox.WARNING
            )
            if not resultado:
                return
        else:
            # Pedir confirmación para ACTIVAR
            resultado = messagebox.askyesno(
                "ACTIVAR SISTEMA",
                "¿Estás seguro de que deseas ACTIVAR el sistema?",
                icon=messagebox.QUESTION
            )
            if not resultado:
                return
        
        self.sistema_activo = not self.sistema_activo
        if self.sistema_activo:
            self._session_start = datetime.now().isoformat(timespec="milliseconds")
            self._json_buffer = []
            self._json_last_flush = time.time()
            self._btn.config(text="⏹  DESACTIVAR",
                             bg="#3D0B0B", fg=C["red_alert"])
            self._sys_lbl.config(text="◉ ACTIVO", fg=C["green_bright"])
            self.conexion_label.config(text="◉ ENLACE: ESTABLE", fg=C["green_bright"])
            self._log(">>> ✓ SISTEMA ACTIVADO — Inicio de seguimiento")
            for key, lbl in self._status_items:
                if key == "SISTEMA":        lbl.config(text="ACTIVO",    fg=C["green_bright"])
                elif key == "COMUNICACION": lbl.config(text="ENLACE",    fg=C["cyan"])
                elif key == "GPS":          lbl.config(text="BLOQUEADO", fg=C["green_bright"])
            # Iniciar escucha WiFi
            self.iniciar_conexion_wifi()
        else:
            self._btn.config(text="⏻  ACTIVAR",
                             bg="#1A3A20", fg=C["green_bright"])
            self._sys_lbl.config(text="● INACTIVO", fg=C["red_alert"])
            self.conexion_label.config(text="◌ ENLACE: DESCONECTADO", fg=C["red_alert"])
            self._log(">>> ✓ SISTEMA DESACTIVADO")
            for key, lbl in self._status_items:
                if key in ("SISTEMA", "COMUNICACION", "GPS"):
                    lbl.config(
                        text={"SISTEMA":"NOMINAL","COMUNICACION":"SIN ENLACE","GPS":"EN ESPERA"}[key],
                        fg=C["amber_dim"])
            # Detener escucha WiFi
            self.detener_conexion_wifi()
    # ════════════════════════════════════════════════════════════════
    # ── NUEVO SISTEMA DE ENLACE WI-FI (UDP) ──
    # ════════════════════════════════════════════════════════════════

    def iniciar_conexion_wifi(self):
        if getattr(self, 'escuchando_wifi', False):
            self._log(">>> El puerto ya está abierto, esperando datos...")
            return

        # Verificar si el puerto 8081 ya está ocupado (otro proceso lo tiene)
        import socket as _sock
        test = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        try:
            test.bind(("", 8081))
            test.close()
            puerto_libre = True
        except OSError:
            test.close()
            puerto_libre = False

        if not puerto_libre:
            # El main.py ya tiene el puerto — solo leer shared_state
            self._log(">>> Puerto 8081 ocupado — leyendo desde shared_state (modo espejo)")
            self.escuchando_wifi = True
            self._modo_espejo = True
            return

        self._modo_espejo = False
        self.escuchando_wifi = True
        hilo_wifi = threading.Thread(target=self._escuchar_udp, daemon=True)
        hilo_wifi.start()
        self._log(">>> Escuchando telemetría vía Wi-Fi (UDP) en puerto 8081...")
        
        # Cambiamos la etiqueta para mostrar que estamos en Wi-Fi
        try:
            self.conexion_label.config(text="● ENLACE: CONECTADO (WIFI)", fg=C["green_bright"])
        except:
            pass

    def detener_conexion_wifi(self):
        """Llama a esta función para apagar la escucha"""
        self.escuchando_wifi = False
        self._log(">>> Enlace Wi-Fi terminado.")

    def _escuchar_udp(self):
        """Hilo en segundo plano que atrapa los paquetes de la ESP32"""
        UDP_IP = "0.0.0.0"
        UDP_PORT = 8081
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((UDP_IP, UDP_PORT))
            sock.settimeout(2.0) 
        except Exception as e:
            self._log(f">>> ERROR al abrir puerto UDP: {e}")
            return

        while self.escuchando_wifi:
            try:
                data, addr = sock.recvfrom(1024) 
                linea = data.decode('utf-8').strip()
                datos_gps = json.loads(linea)
                
                if datos_gps.get("type") == "telemetria":
                    lat_actual = float(datos_gps["latitud"])
                    lon_actual = float(datos_gps["longitud"])
                    
                    # --- ¡AQUÍ ESTÁ LA CLAVE PARA SINCRONIZAR MAPA Y RADAR! ---
                    # Revisa que estos sean los mismos números que le pusiste a tu mapa
                    BASE_LAT = 22.16100
                    BASE_LON = -102.26877 # <--- CAMBIA ESTO POR TU LONGITUD
                    # ----------------------------------------------------------
                    
                    # Calculamos la Distancia real en metros (Haversine)
                    R = 6371000 
                    phi1 = math.radians(BASE_LAT)
                    phi2 = math.radians(lat_actual)
                    delta_phi = math.radians(lat_actual - BASE_LAT)
                    delta_lambda = math.radians(lon_actual - BASE_LON)
                    
                    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    distancia_calculada = R * c
                    
                    # Filtro Antirruido (Si se mueve menos de 2.5 metros, lo deja en el centro)
                    if distancia_calculada < 2.5:
                        distancia_calculada = 0
                    
                    # Calculamos el Ángulo (Brújula real)
                    y = math.sin(delta_lambda) * math.cos(phi2)
                    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
                    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360

                    # Corrección de Ángulo para que coincida con la pantalla
                    angulo_pantalla = (90 - bearing) % 360

                    # Inyectamos TODO al panel
                    updates = {
                        "latitud": lat_actual,
                        "longitud": lon_actual,
                        "altitud": float(datos_gps["altitud"]),
                        "velocidad": float(datos_gps.get("velocidad", 0.0)),
                        "hora_gps": datos_gps.get("hora_gps", "--:--:--"),
                        "distancia": distancia_calculada,
                        "angulo_radar": angulo_pantalla,
                        "wifi_strength": int(datos_gps.get("rssi", 0)),
                    }
                    
                    try:
                        import shared_state as SS
                        SS.update(updates) 
                    except:
                        pass
                    
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                pass 
            except Exception as e:
                pass 
                
        sock.close()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Módulo de Recuperación - Equipo 4")
    root.geometry("1000x600")
    root.configure(bg="#0D1117")
    app = ModuloRecuperacion(root)
    root.mainloop()
