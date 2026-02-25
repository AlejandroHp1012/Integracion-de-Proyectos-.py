"""
╔══════════════════════════════════════════════════════╗
║  MÓDULO RECUPERACIÓN — Equipo 4                     ║
║  Clase: ModuloRecuperacion                          ║
║  Recibe un tk.Frame como contenedor                 ║
╚══════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk
import math
import random
from datetime import datetime
import time
import json
import os

# ── Paleta de colores ─────────────────────────────────
C = {
    "bg":           "#080c08",
    "panel":        "#0a0f0a",
    "border":       "#1a4a1a",
    "border_hi":    "#2aff2a",
    "amber":        "#ffb000",
    "amber_dim":    "#7a5500",
    "green":        "#00ff41",
    "green_dim":    "#004d14",
    "red_alert":    "#ff2200",
    "cyan":         "#00e5ff",
    "white":        "#e8ffe8",
    "grid":         "#0d1f0d",
    "scanline":     "#050a05",
}

LED_OFF   = "off"
LED_OK    = "ok"
LED_ERROR = "error"
LED_COLORS = {
    LED_OFF:   {"center": "#2a2a1a", "ring": "#1a1a0a", "glow": "#0a0a05"},
    LED_OK:    {"center": "#aaff44", "ring": "#66cc00", "glow": "#1a3300"},
    LED_ERROR: {"center": "#ff4400", "ring": "#cc2200", "glow": "#330800"},
}

FONT_MONO   = ("Courier", 8, "bold")
FONT_MONO_S = ("Courier", 7, "bold")
FONT_MONO_L = ("Courier", 11, "bold")
FONT_MONO_XL= ("Courier", 14, "bold")


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
        r = int(int(hx[0:2], 16) * b)
        g = int(int(hx[2:4], 16) * b)
        bl= int(int(hx[4:6], 16) * b)
        return f"#{r:02x}{g:02x}{bl:02x}"


class ModuloRecuperacion:
    """
    Módulo de control de Recuperación.
    Recibe un tk.Frame como parent_frame — NO crea su propia ventana.
    """
    def __init__(self, parent_frame):
        self.root = parent_frame

        self.sistema_activo = False
        self.latitud   = 22.1475
        self.longitud  = -102.2783
        self.altitud   = 2500.0
        self.velocidad = 0.0
        self.distancia = 1500.0
        self.angulo_radar = 0
        self.bateria   = 85
        self.hora_gps  = "--:--:--"
        self.trayectoria = []
        self.marker_cohete = None
        self.path_trayectoria = None
        self._tick = 0
        self._leds: dict = {}
        self._json_buffer: list = []
        self._json_last_flush: float = 0.0
        self._json_last_save: float  = 0.0          # control del guardado cada 15s
        self._json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "telemetria_log.json")

        self._construir_ui()
        self._loop()

    def _construir_ui(self):
        hdr = tk.Frame(self.root, bg=C["bg"], height=58)
        hdr.pack(fill=tk.X, padx=6, pady=(6, 0))
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border_hi"], height=1).pack(fill=tk.X)

        inner_hdr = tk.Frame(hdr, bg=C["bg"])
        inner_hdr.pack(fill=tk.BOTH, expand=True)

        logo_f = tk.Frame(inner_hdr, bg=C["bg"])
        logo_f.pack(side=tk.LEFT, padx=12)
        tk.Label(logo_f, text="◈ MCC-REC",
                 font=("Courier", 9, "bold"), bg=C["bg"],
                 fg=C["amber"]).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(logo_f, text="🪂 MISIÓN CONTROL // SUBSISTEMA DE RECUPERACIÓN",
                 font=("Courier", 11, "bold"), bg=C["bg"],
                 fg=C["green"]).pack(side=tk.LEFT)

        right_hdr = tk.Frame(inner_hdr, bg=C["bg"])
        right_hdr.pack(side=tk.RIGHT, padx=12)

        self._clock_lbl = tk.Label(right_hdr, text="00:00:00",
                                   font=("Courier", 16, "bold"),
                                   bg=C["bg"], fg=C["amber"])
        self._clock_lbl.pack(side=tk.RIGHT, padx=(12, 0))
        tk.Label(right_hdr, text="T+", font=FONT_MONO_S,
                 bg=C["bg"], fg=C["amber_dim"]).pack(side=tk.RIGHT)

        self._btn_f = tk.Frame(right_hdr, bg=C["green"], padx=1, pady=1)
        self._btn_f.pack(side=tk.RIGHT, padx=16)
        self._btn = tk.Button(self._btn_f, text="[ ACTIVAR SISTEMA ]",
                              font=FONT_MONO, bg="#001a00", fg=C["green"],
                              activebackground="#002a00", activeforeground=C["green"],
                              bd=0, padx=10, pady=6, cursor="hand2",
                              command=self._toggle)
        self._btn.pack()

        tk.Frame(hdr, bg=C["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)

        status_bar = tk.Frame(self.root, bg=C["panel"], height=26)
        status_bar.pack(fill=tk.X, padx=6)
        status_bar.pack_propagate(False)

        self._status_items = []
        for key, val in [("SISTEMA","NOMINAL"),("COMUNICACION","SIN ENLACE"),
                         ("GPS","EN ESPERA"),("DISTANCIA","1500m"),("ALTITUD","2500m")]:
            f = tk.Frame(status_bar, bg=C["panel"])
            f.pack(side=tk.LEFT, padx=8)
            tk.Label(f, text=key+":", font=FONT_MONO_S,
                     bg=C["panel"], fg=C["amber_dim"]).pack(side=tk.LEFT)
            lbl = tk.Label(f, text=val, font=FONT_MONO_S,
                           bg=C["panel"], fg=C["green"])
            lbl.pack(side=tk.LEFT, padx=(2, 0))
            self._status_items.append((key, lbl))

        tk.Frame(status_bar, bg=C["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=4, padx=6)
        self._modo_lbl = tk.Label(status_bar, text="◉ MODO: SIMULACIÓN",
                                  font=FONT_MONO_S, bg=C["panel"], fg=C["amber"])
        self._modo_lbl.pack(side=tk.LEFT, padx=8)
        self._sys_lbl = tk.Label(status_bar, text="● SISTEMA: INACTIVO",
                                 font=FONT_MONO_S, bg=C["panel"], fg=C["red_alert"])
        self._sys_lbl.pack(side=tk.RIGHT, padx=12)

        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        col_left = tk.Frame(body, bg=C["bg"])
        col_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        self._build_radar(col_left)

        col_center = tk.Frame(body, bg=C["bg"])
        col_center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self._build_mapa(col_center)

        col_right = tk.Frame(body, bg=C["bg"], width=260)
        col_right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(4, 0))
        col_right.pack_propagate(False)
        self._build_telemetria(col_right)

        self._build_console()

    def _build_radar(self, parent):
        frame = tk.Frame(parent, bg=C["bg"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self._panel_header(frame, "RADAR // SEGUIMIENTO DE BLANCO")
        self.canvas_radar = tk.Canvas(frame, bg="#020802", highlightthickness=0)
        self.canvas_radar.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

    def _build_mapa(self, parent):
        frame = tk.Frame(parent, bg=C["bg"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self._panel_header(frame, "MAPA // REPRESENTACIÓN TÁCTICA")
        self.canvas_mapa = tk.Canvas(frame, bg="#020c02", highlightthickness=0)
        self.canvas_mapa.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))

    def _build_telemetria(self, parent):
        frame = tk.Frame(parent, bg=C["bg"],
                         highlightbackground=C["border"], highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True)
        self._panel_header(frame, "TELEMETRÍA // DATOS EN VIVO")

        inner = tk.Frame(frame, bg=C["bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        ley = tk.Frame(inner, bg=C["panel"],
                       highlightbackground=C["border"], highlightthickness=1)
        ley.pack(fill=tk.X, pady=(0, 8))
        tk.Label(ley, text=" SEÑAL:", font=FONT_MONO_S,
                 bg=C["panel"], fg=C["amber_dim"]).pack(side=tk.LEFT, padx=4)
        for state, txt, col in [(LED_OK,"ACTIVO",C["green"]),
                                 (LED_ERROR,"ERROR",C["red_alert"]),
                                 (LED_OFF,"INACTIVO",C["amber_dim"])]:
            led = FocoLED(ley, bg_color=C["panel"])
            led.set_state(state)
            led.pack(side=tk.LEFT, padx=(6, 1), pady=3)
            tk.Label(ley, text=txt, font=FONT_MONO_S,
                     bg=C["panel"], fg=col).pack(side=tk.LEFT, padx=(0, 4))

        for lbl, var, key in [("LATITUD","latitud_valor","latitud"),
                               ("LONGITUD","longitud_valor","longitud"),
                               ("ALTITUD","altitud_valor","altitud"),
                               ("HORA GPS","hora_gps_valor","hora_gps")]:
            self._campo_telem(inner, lbl, var, key)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X, pady=8)

        hf = tk.Frame(inner, bg=C["panel"],
                      highlightbackground=C["border_hi"], highlightthickness=1)
        hf.pack(fill=tk.X, pady=(0, 8))
        tk.Label(hf, text="T // HORA SISTEMA", font=FONT_MONO_S,
                 bg=C["panel"], fg=C["amber_dim"]).pack(pady=(6, 0))
        self.hora_valor = tk.Label(hf, text="--:--:--",
                                   font=("Courier", 18, "bold"),
                                   bg=C["panel"], fg=C["amber"])
        self.hora_valor.pack(pady=(0, 6))

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X, pady=(0, 8))

        bf = tk.Frame(inner, bg=C["bg"])
        bf.pack(fill=tk.X, pady=(0, 6))
        tk.Label(bf, text="ENERGÍA:", font=FONT_MONO_S,
                 bg=C["bg"], fg=C["amber_dim"]).pack(side=tk.LEFT)
        self._bat_canvas = tk.Canvas(bf, bg=C["bg"], height=16, highlightthickness=0)
        self._bat_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X, pady=6)

        pf = tk.Frame(inner, bg=C["bg"])
        pf.pack(fill=tk.X)
        tk.Label(pf, text="PUERTO:", font=FONT_MONO_S,
                 bg=C["bg"], fg=C["amber_dim"]).pack(side=tk.LEFT)
        self.puerto_entry = tk.Entry(pf, width=8, font=FONT_MONO_S,
                                     bg="#0a0a0a", fg=C["green"],
                                     insertbackground=C["green"],
                                     relief=tk.FLAT,
                                     highlightbackground=C["border"],
                                     highlightthickness=1)
        self.puerto_entry.insert(0, "COM3")
        self.puerto_entry.pack(side=tk.LEFT, padx=4)
        tk.Button(pf, text="CONECTAR", font=FONT_MONO_S,
                  bg="#0a1a0a", fg=C["green"], activebackground="#0f2a0f",
                  bd=0, padx=6, pady=2, cursor="hand2",
                  command=self._conectar_serial).pack(side=tk.LEFT)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill=tk.X, pady=6)

        for txt, cmd, col, fc in [
            ("[ REINICIAR ]",   self._reiniciar,  "#1a0800", C["amber"]),
            ("[ CALIBRAR ]",    self._calibrar,   "#001020", C["cyan"]),
            ("[ BORRAR RUTA ]", self._borrar_ruta,"#0a0a0a", C["amber_dim"]),
        ]:
            tk.Button(inner, text=txt, font=FONT_MONO_S,
                      bg=col, fg=fc, bd=0, pady=5,
                      activebackground=col, cursor="hand2",
                      command=cmd).pack(fill=tk.X, pady=2)

        self.conexion_label = tk.Label(inner, text="◌ ENLACE: DESCONECTADO",
                                       font=FONT_MONO_S, bg=C["bg"],
                                       fg=C["red_alert"])
        self.conexion_label.pack(pady=(8, 0))

    def _build_console(self):
        frame = tk.Frame(self.root, bg=C["bg"],
                         highlightbackground=C["border"],
                         highlightthickness=1, height=90)
        frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        frame.pack_propagate(False)
        self._panel_header(frame, "CONSOLA // REGISTRO DE EVENTOS")
        self._console = tk.Text(frame, bg="#02050a", fg=C["green"],
                                font=("Courier", 7), relief=tk.FLAT,
                                state=tk.DISABLED, wrap=tk.WORD, height=4,
                                insertbackground=C["green"], highlightthickness=0)
        self._console.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._log(f"Sistema iniciado — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log("Aguardando activación del subsistema de recuperación...")
        self._log(f"Posición base: {self.latitud:.4f}° N, {self.longitud:.4f}° W  |  Alt: {self.altitud:.0f} m")

    def _panel_header(self, parent, titulo):
        h = tk.Frame(parent, bg=C["panel"], height=22)
        h.pack(fill=tk.X)
        h.pack_propagate(False)
        tk.Frame(h, bg=C["border_hi"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(h, text=f"  {titulo}", font=FONT_MONO_S,
                 bg=C["panel"], fg=C["amber"], anchor="w").pack(side=tk.LEFT, fill=tk.Y)
        return h

    def _campo_telem(self, parent, label, var_name, campo_key):
        row = tk.Frame(parent, bg=C["bg"],
                       highlightbackground=C["border"], highlightthickness=1)
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text=f" {label}", font=FONT_MONO_S,
                 bg=C["panel"], fg=C["amber_dim"], width=9,
                 anchor="w").pack(side=tk.LEFT, fill=tk.Y, ipady=4)
        tk.Frame(row, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        valor = tk.Label(row, text="───────", font=("Courier", 10, "bold"),
                         bg=C["bg"], fg=C["green"], anchor="e", padx=6, pady=4)
        valor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        setattr(self, var_name, valor)
        tk.Frame(row, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        led = FocoLED(row, bg_color=C["bg"])
        led.pack(side=tk.LEFT, padx=4)
        self._leds[campo_key] = led
        etxt = tk.Label(row, text="INACTIVO", font=("Courier", 6, "bold"),
                        bg=C["bg"], fg=C["amber_dim"], width=7)
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
            cfg = {LED_OK:("ACTIVO",C["green"]),
                   LED_ERROR:("ERROR",C["red_alert"]),
                   LED_OFF:("INACTIVO",C["amber_dim"])}[state]
            w.config(text=cfg[0], fg=cfg[1])

    def _actualizar_leds(self):
        state = LED_OK if self.sistema_activo else LED_OFF
        for campo in ["latitud", "longitud", "altitud", "hora_gps"]:
            self._set_led(campo, state)

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
            shade = C["scanline"] if y % 8 == 0 else "#030b03"
            c.create_line(0, y, w, y, fill=shade)

        for i in range(1, 5):
            r = R * i / 4
            alpha_col = ["#0d1f0d","#102010","#143014","#1a4a1a"][i-1]
            c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=alpha_col, width=1)
            dist_km = (self.distancia / 1000) * i / 4
            c.create_text(cx + r - 6, cy - 10, text=f"{dist_km:.1f}",
                          fill=C["green_dim"], font=("Courier", 7), anchor="e")

        c.create_line(cx, cy-R, cx, cy+R, fill=C["green_dim"], dash=(2, 6))
        c.create_line(cx-R, cy, cx+R, cy, fill=C["green_dim"], dash=(2, 6))
        c.create_oval(cx-4, cy-4, cx+4, cy+4, fill=C["green"], outline=C["green"])

        if self.sistema_activo:
            ar = math.radians(self.angulo_radar)
            for i in range(8):
                a_trail = math.radians(self.angulo_radar - i * 4)
                alpha = int(180 * (1 - i / 8))
                fade = f"#{0:02x}{max(0,alpha-60):02x}{0:02x}"
                ex = cx + R * math.cos(a_trail)
                ey = cy - R * math.sin(a_trail)
                c.create_line(cx, cy, ex, ey,
                              fill=C["border_hi"] if i == 0 else fade,
                              width=2 if i == 0 else 1)
            if self.distancia > 0:
                dr = min(self.distancia / (self.distancia * 1.5 + 1), 1) * 0.7
                bx = cx + R * dr * math.cos(ar)
                by = cy - R * dr * math.sin(ar)
                ps = 10 + 5 * abs(math.sin(self._tick * 0.15))
                c.create_oval(bx-ps, by-ps, bx+ps, by+ps, outline=C["amber"], width=1)
                c.create_oval(bx-5, by-5, bx+5, by+5, fill=C["amber"], outline="")
                c.create_text(bx+14, by-12, text=f"▲ {self.distancia:.0f}m",
                              fill=C["amber"], font=FONT_MONO_S)

        estado = "ACTIVO ◉" if self.sistema_activo else "EN ESPERA ○"
        c.create_text(8, 8, text=f"RADAR // {estado}",
                      fill=C["green"], font=FONT_MONO_S, anchor="nw")
        c.create_text(w-8, 8, text=f"AZ {self.angulo_radar:03d}°",
                      fill=C["amber"], font=FONT_MONO_S, anchor="ne")
        c.create_text(8, h-8, text=f"R {self.distancia:.0f}m",
                      fill=C["amber_dim"], font=("Courier", 7), anchor="sw")

    def _dibujar_mapa_sim(self):
        c = self.canvas_mapa
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2 or h < 2:
            return

        for y in range(0, h, 4):
            c.create_line(0, y, w, y,
                          fill="#020c02" if y % 8 == 0 else "#030d03")
        gs = 50
        for x in range(0, w, gs):
            c.create_line(x, 0, x, h, fill=C["grid"])
        for y in range(0, h, gs):
            c.create_line(0, y, w, y, fill=C["grid"])
        for xi, x in enumerate(range(0, w, gs)):
            for yi, y in enumerate(range(0, h, gs)):
                if xi % 2 == 0 and yi % 2 == 0:
                    c.create_text(x+2, y+2, text=f"{xi},{yi}",
                                  fill=C["green_dim"], font=("Courier", 6), anchor="nw")

        bx, by = w//2, h//2
        c.create_rectangle(bx-8, by-8, bx+8, by+8,
                           fill=C["green_dim"], outline=C["green"], width=1)
        c.create_text(bx, by-16, text="◈ BASE", fill=C["green"], font=FONT_MONO_S)

        if self.sistema_activo:
            px = w/2 + (self.longitud - (-102.2783)) * 1200
            py = h/2 - (self.latitud - 22.1475) * 1200
            px = max(20, min(w-20, px))
            py = max(20, min(h-20, py))
            c.create_line(bx, by, px, py, fill=C["cyan"], width=1, dash=(8, 4))
            mx, my = (bx+int(px))//2, (by+int(py))//2
            c.create_text(mx+2, my-8, text=f"{self.distancia:.0f}m",
                          fill=C["cyan"], font=("Courier", 7))
            ps = 14 + 3*abs(math.sin(self._tick*0.15))
            c.create_oval(px-ps, py-ps, px+ps, py+ps,
                         outline=C["amber"], width=1, dash=(4, 3))
            c.create_polygon(px, py-12, px-8, py+8, px+8, py+8,
                            fill=C["amber"], outline=C["white"], width=1)
            c.create_text(px, py+20, text=f"▲ {self.altitud:.0f}m",
                         fill=C["amber"], font=FONT_MONO_S)

        for x, y, ay in [(0,0,"nw"),(w,0,"ne"),(0,h,"sw"),(w,h,"se")]:
            c.create_text(x, y, text="◈", fill=C["border"],
                         font=("Courier", 10), anchor=ay)
        c.create_text(8, h-8, text=f"LAT {self.latitud:.4f}°",
                     fill=C["amber_dim"], font=("Courier", 7), anchor="sw")
        c.create_text(w-8, h-8, text=f"LON {self.longitud:.4f}°",
                     fill=C["amber_dim"], font=("Courier", 7), anchor="se")

    def _dibujar_bateria(self):
        c = self._bat_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 4:
            return
        pct = max(0, min(100, self.bateria)) / 100
        c.create_rectangle(0, 2, w-6, 13, fill="#0a0a0a", outline=C["border"])
        col = C["green"] if pct > 0.4 else C["amber"] if pct > 0.2 else C["red_alert"]
        bar_w = int((w-8) * pct)
        if bar_w > 0:
            c.create_rectangle(1, 3, bar_w, 12, fill=col, outline="")
        c.create_rectangle(w-5, 5, w-1, 10, fill=C["border"], outline="")
        c.create_text(w//2, 7, text=f"{self.bateria:.0f}%",
                     fill=C["white"], font=("Courier", 7))

    def _loop(self):
        now_str = datetime.now().strftime("%H:%M:%S")
        self._clock_lbl.config(text=now_str)
        self.hora_valor.config(text=now_str)
        self._tick += 1

        if self.sistema_activo:
            self.angulo_radar = (self.angulo_radar + 5) % 360
            self.distancia = max(50, self.distancia + random.uniform(-20, -5))
            self.altitud   = max(0,  self.altitud   + random.uniform(-10, 5))
            self.velocidad = random.uniform(0, 15)
            self.latitud  += random.uniform(-0.0001, 0.0001)
            self.longitud += random.uniform(-0.0001, 0.0001)
            self.bateria   = max(0, self.bateria - 0.01)
            self.hora_gps  = now_str

            self.latitud_valor.config( text=f"{self.latitud:.6f}°")
            self.longitud_valor.config(text=f"{self.longitud:.6f}°")
            self.altitud_valor.config( text=f"{self.altitud:.1f} m")
            self.hora_gps_valor.config(text=self.hora_gps)

            for key, lbl in self._status_items:
                if key == "DISTANCIA":
                    lbl.config(text=f"{self.distancia:.0f}m")
                elif key == "ALTITUD":
                    lbl.config(text=f"{self.altitud:.0f}m")

            if self._tick % 30 == 0:
                self._log(f"POS {self.latitud:.5f}° {self.longitud:.5f}°  "
                          f"ALT {self.altitud:.1f}m  DST {self.distancia:.0f}m  "
                          f"BAT {self.bateria:.1f}%")

            # ── Guardado JSON cada 15 segundos ───────────────────
            ahora = time.time()
            if ahora - self._json_last_save >= 15.0:
                self._json_last_save = ahora
                self._guardar_json()

        self._actualizar_leds()
        self._dibujar_radar()
        self._dibujar_bateria()
        self._dibujar_mapa_sim()
        self.root.after(100, self._loop)

    # ── Guardado JSON ─────────────────────────────────────────────
    def _guardar_json(self):
        """
        Agrega una muestra de telemetría al archivo telemetria_log.json.
        El archivo contiene una lista de registros; cada registro es un
        dict con timestamp y todos los valores del sensor en ese momento.
        Si el archivo no existe lo crea. Si existe, agrega al final.
        """
        muestra = {
            "timestamp":  datetime.now().isoformat(timespec="seconds"),
            "latitud":    round(self.latitud,   6),
            "longitud":   round(self.longitud,  6),
            "altitud_m":  round(self.altitud,   2),
            "distancia_m":round(self.distancia, 1),
            "velocidad_ms":round(self.velocidad,2),
            "bateria_pct":round(self.bateria,   1),
            "angulo_radar":self.angulo_radar,
            "hora_gps":   self.hora_gps,
        }
        try:
            # Leer registros existentes (si el archivo ya existe)
            if os.path.exists(self._json_path):
                with open(self._json_path, "r", encoding="utf-8") as f:
                    datos = json.load(f)
            else:
                datos = []

            datos.append(muestra)

            with open(self._json_path, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)

            self._log(f">>> JSON guardado — {len(datos)} registros en telemetria_log.json")

        except Exception as e:
            self._log(f">>> ERROR al guardar JSON: {e}")

    def _toggle(self):
        self.sistema_activo = not self.sistema_activo
        if self.sistema_activo:
            self._session_start = datetime.now().isoformat(timespec="milliseconds")
            self._json_buffer = []
            self._json_last_flush = time.time()
            self._btn.config(text="[ DESACTIVAR SISTEMA ]", bg="#1a0000", fg=C["red_alert"])
            self._btn_f.config(bg=C["red_alert"])
            self._sys_lbl.config(text="◉ SISTEMA: ACTIVO", fg=C["green"])
            self.conexion_label.config(text="◉ ENLACE: ESTABLE", fg=C["green"])
            self._log(">>> SISTEMA ACTIVADO — Inicio de seguimiento")
            for key, lbl in self._status_items:
                if key == "SISTEMA":        lbl.config(text="ACTIVO",    fg=C["green"])
                elif key == "COMUNICACION": lbl.config(text="ENLACE",    fg=C["cyan"])
                elif key == "GPS":          lbl.config(text="BLOQUEADO", fg=C["green"])
        else:
            self._btn.config(text="[ ACTIVAR SISTEMA ]", bg="#001a00", fg=C["green"])
            self._btn_f.config(bg=C["green"])
            self._sys_lbl.config(text="● SISTEMA: INACTIVO", fg=C["red_alert"])
            self.conexion_label.config(text="◌ ENLACE: DESCONECTADO", fg=C["red_alert"])
            self._log(">>> SISTEMA DESACTIVADO")
            for key, lbl in self._status_items:
                if key in ("SISTEMA", "COMUNICACION", "GPS"):
                    lbl.config(
                        text={"SISTEMA":"NOMINAL","COMUNICACION":"SIN ENLACE","GPS":"EN ESPERA"}[key],
                        fg=C["amber_dim"])

    def _reiniciar(self):
        self.latitud=22.1475; self.longitud=-102.2783; self.altitud=2500.0
        self.distancia=1500.0; self.bateria=85; self.velocidad=0
        self.angulo_radar=0; self.hora_gps="--:--:--"; self.trayectoria=[]
        self._log(">>> SISTEMA REINICIADO — Valores por defecto restaurados")

    def _borrar_ruta(self):
        self.trayectoria = []
        self._log(">>> Trayectoria borrada")

    def _calibrar(self):
        self.conexion_label.config(text="◈ CALIBRANDO...", fg=C["amber"])
        self._log(">>> Iniciando secuencia de calibración...")
        self.root.after(2000, self._calibrar_ok)

    def _calibrar_ok(self):
        self.conexion_label.config(text="◉ ENLACE: ESTABLE", fg=C["green"])
        self._log(">>> Calibración completa — todos los sensores nominales")

    def _conectar_serial(self):
        self.conexion_label.config(text="◌ Requiere pyserial", fg=C["amber"])
        self._log(">>> Serial: instala pyserial (pip install pyserial)")
