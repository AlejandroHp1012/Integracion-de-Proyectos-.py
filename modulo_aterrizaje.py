"""
╔══════════════════════════════════════════════════════╗
║  MÓDULO ATERRIZAJE — Equipo 3                       ║
║  Clase: ModuloAterrizaje                            ║
║  Recibe un tk.Frame como contenedor                 ║
╠══════════════════════════════════════════════════════╣
║  MODOS DE OPERACIÓN:                                ║
║   AUTO   → arranca solo al iniciar (como Despliegue)║
║   MANUAL → espera que el operador presione ACTIVAR  ║
╚══════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk
import math
import random
from datetime import datetime

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
#  MÓDULO PRINCIPAL
# ══════════════════════════════════════════════════════
class ModuloAterrizaje:
    """
    Módulo de control de Aterrizaje — Equipo 3.
    Llamar: ModuloAterrizaje(frame)
    """

    FASE_NOMBRES   = ["STANDBY", "DESORBIT", "REENTRADA",
                      "BURN INICIO", "BURN FINAL", "TOUCHDOWN", "ASEGURADO"]
    ALTITUD_INICIO = 8000.0
    VEL_INICIAL    = -95.0

    def __init__(self, parent_frame):
        self.parent = parent_frame

        # ── Modo de operación ────────────────────────
        # "AUTO"   → arranca solo al iniciar
        # "MANUAL" → espera botón del operador
        self.modo           = "MANUAL"
        self.sistema_activo = False

        # ── Telemetría ───────────────────────────────
        self.fase        = 0
        self.altitud     = self.ALTITUD_INICIO
        self.vel_vert    = self.VEL_INICIAL
        self.vel_horiz   = 12.0
        self.aceleracion = 0.0
        self.combustible = 100.0
        self.empuje      = 0.0
        self.temperatura = 38.0
        self.presion     = 1.0
        self.pitch       = 0.0
        self.roll        = 0.0
        self.yaw         = 0.0
        self.patas       = [False] * 4
        self.aletas      = True
        self.touchdown   = False
        self.error_lat   = 0.0
        self.error_lon   = 0.0
        self._tick       = 0
        self._pulse      = 0.0
        self._trayectoria= []

        self._construir_ui()
        self._loop()

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

        # Controles derecha
        rf = tk.Frame(row_h, bg=C["bg"])
        rf.pack(side="right")

        # Reloj
        self._lbl_clock = tk.Label(rf, text="T+00:00:00",
                                   font=(MONO, 9, "bold"),
                                   bg=C["bg"], fg=C["amber"])
        self._lbl_clock.pack(side="right", padx=(8, 0))

        # ── Botón ACTIVAR/DESACTIVAR (solo en modo MANUAL) ──
        self._btn_frame = tk.Frame(rf, bg=C["border_hi"], padx=1, pady=1)
        self._btn_frame.pack(side="right", padx=6)
        self._btn_sys = tk.Button(
            self._btn_frame, text="[ ACTIVAR ]",
            font=MONO_S, bg=C["purple_dk"], fg=C["purple"],
            relief="flat", bd=0, padx=8, pady=5, cursor="hand2",
            command=self._toggle)
        self._btn_sys.pack()

        # ── Botones de modo AUTO / MANUAL ──────────────
        sep = tk.Frame(rf, bg=C["purple_dim"], width=1)
        sep.pack(side="right", fill="y", padx=6, pady=4)

        modo_f = tk.Frame(rf, bg=C["bg"])
        modo_f.pack(side="right")

        tk.Label(modo_f, text="MODO:", font=(MONO, 6, "bold"),
                 bg=C["bg"], fg=C["text_gray"]).pack(side="left", padx=(0, 4))

        self._btn_auto = tk.Button(
            modo_f, text="⟳ AUTO",
            font=MONO_S, bg=C["text_dark"], fg=C["text_gray"],
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            command=self._set_modo_auto)
        self._btn_auto.pack(side="left", padx=(0, 2))

        self._btn_manual = tk.Button(
            modo_f, text="◎ MANUAL",
            font=MONO_S, bg=C["purple_dk"], fg=C["purple"],
            relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
            command=self._set_modo_manual)
        self._btn_manual.pack(side="left")

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
                ("MODO",        "MANUAL",  C["amber"]),
                ("ALTITUD",     "8000m",   C["purple"]),
                ("VEL.VERT",    "-95m/s",  C["purple"]),
                ("COMBUSTIBLE", "100%",    C["purple"]),
                ("EMPUJE",      "0%",      C["purple"]),
                ("PATAS",       "0/4",     C["purple"]),
                ("TOUCHDOWN",   "NO",      C["purple"])]:
            f = tk.Frame(sbar, bg=C["panel"])
            f.pack(side="left", padx=6)
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

        # Estado visual inicial
        self._aplicar_visual_modo()

    # ── COLUMNA IZQUIERDA ─────────────────────────────
    def _build_left(self, p):
        self._card(p, "◈ ALTÍMETRO / VELOCIDAD", self._ui_altimeter)
        self._card(p, "◈ ORIENTACIÓN IMU",        self._ui_attitude)
        self._card(p, "◈ SISTEMAS MECÁNICOS",     self._ui_mecanicos)

    def _ui_altimeter(self, f):
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        tk.Label(f, text="ALTITUD", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).grid(row=0, column=0,
                 columnspan=2, sticky="w")
        self._lbl_alt = tk.Label(f, text="8000.0 m",
                                 font=(MONO, 18, "bold"),
                                 bg=C["panel"], fg=C["purple"])
        self._lbl_alt.grid(row=1, column=0, columnspan=2, sticky="w")
        tk.Frame(f, bg=C["border"], height=1).grid(row=2, column=0,
                 columnspan=2, sticky="ew", pady=4)
        for col, (lbl, attr) in enumerate([("VEL. VERT.", "_lbl_vv"),
                                            ("VEL. HORIZ.", "_lbl_vh")]):
            tk.Label(f, text=lbl, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(row=3, column=col, sticky="w")
            lv = tk.Label(f, text="---", font=(MONO, 11, "bold"),
                          bg=C["panel"], fg=C["cyan"])
            lv.grid(row=4, column=col, sticky="w")
            setattr(self, attr, lv)
        tk.Frame(f, bg=C["border"], height=1).grid(row=5, column=0,
                 columnspan=2, sticky="ew", pady=4)
        for col, (lbl, attr, unit) in enumerate([
                ("ACELER.",    "_lbl_acel", "m/s²"),
                ("TEMP.MOTOR", "_lbl_temp", "°C")]):
            tk.Label(f, text=lbl, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(row=6, column=col, sticky="w")
            lv = tk.Label(f, text=f"--- {unit}", font=MONO_S,
                          bg=C["panel"], fg=C["amber"])
            lv.grid(row=7, column=col, sticky="w")
            setattr(self, attr, lv)

    def _ui_attitude(self, f):
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

    def _ui_mecanicos(self, f):
        tk.Label(f, text="PATAS DE ATERRIZAJE", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).pack(anchor="w")
        lf = tk.Frame(f, bg=C["panel"])
        lf.pack(fill="x", pady=(2, 4))
        self._pata_leds = []
        for i in range(4):
            ff = tk.Frame(lf, bg=C["panel"])
            ff.pack(side="left", expand=True)
            cv = tk.Canvas(ff, width=20, height=20, bg=C["panel"], highlightthickness=0)
            cv.pack()
            tk.Label(ff, text=f"P{i+1}", font=(MONO, 6),
                     bg=C["panel"], fg=C["text_gray"]).pack()
            self._pata_leds.append(cv)
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=3)
        ar = tk.Frame(f, bg=C["panel"])
        ar.pack(fill="x", pady=2)
        tk.Label(ar, text="ALETAS REJILLA:", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).pack(side="left")
        self._lbl_aletas = tk.Label(ar, text="DESPLEGADAS", font=MONO_S,
                                    bg=C["panel"], fg=C["green"])
        self._lbl_aletas.pack(side="left", padx=4)
        tk.Label(f, text="PRESIÓN HIDRÁULICA", font=(MONO, 6, "bold"),
                 bg=C["panel"], fg=C["text_gray"]).pack(anchor="w", pady=(4, 0))
        self._lbl_presion = tk.Label(f, text="1.00 bar", font=MONO_M,
                                     bg=C["panel"], fg=C["cyan"])
        self._lbl_presion.pack(anchor="w")

    # ── COLUMNA CENTRAL ───────────────────────────────
    def _build_center(self, p):
        self._card(p, "◈ PERFIL DE DESCENSO  //  ZONA DE ATERRIZAJE",
                   self._ui_descent, expand=True)
        self._card(p, "◈ PROPULSIÓN", self._ui_propulsion)

    def _ui_descent(self, f):
        self._descent_canvas = tk.Canvas(f, bg="#020408", highlightthickness=0)
        self._descent_canvas.pack(fill="both", expand=True)

    def _ui_propulsion(self, f):
        bf = tk.Frame(f, bg=C["panel"])
        bf.pack(fill="x")
        self._bar_empuje = _VBar(bf, C["purple"], "EMPUJE")
        self._bar_empuje.pack(side="left", padx=(0, 6), pady=2)
        self._bar_comb = _VBar(bf, C["amber"], "COMB")
        self._bar_comb.pack(side="left", padx=(0, 6), pady=2)
        nf = tk.Frame(bf, bg=C["panel"])
        nf.pack(side="left", fill="both", expand=True)
        for row, (lbl, attr, unit, color) in enumerate([
                ("EMPUJE",      "_lbl_empuje", "%",    C["purple"]),
                ("COMB. REST.", "_lbl_comb",   "%",    C["amber"]),
                ("Δv QUEMA",    "_lbl_deltav", "m/s",  C["cyan"]),
                ("T-TOUCHDOWN", "_lbl_ttd",    "s",    C["green"])]):
            tk.Label(nf, text=lbl, font=(MONO, 6, "bold"),
                     bg=C["panel"], fg=C["text_gray"]).grid(
                     row=row*2, column=0, sticky="w", padx=4)
            lv = tk.Label(nf, text=f"--- {unit}", font=MONO_M,
                          bg=C["panel"], fg=color)
            lv.grid(row=row*2+1, column=0, sticky="w", padx=4, pady=(0, 2))
            setattr(self, attr, lv)

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
        tk.Button(f.master, text="REINICIAR",
                  font=(MONO, 6, "bold"), bg=C["purple_dk"],
                  fg=C["purple"], relief="flat", cursor="hand2",
                  command=self._reiniciar).pack(pady=(2, 0))

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
    #  GESTIÓN DE MODO
    # ══════════════════════════════════════════════════
    def _set_modo_auto(self):
        """Cambia a modo AUTO — arranca inmediatamente sin botón."""
        if self.modo == "AUTO":
            return
        self.modo = "AUTO"
        self._aplicar_visual_modo()
        if not self.sistema_activo:
            self.sistema_activo = True
            self._log(">>> MODO AUTO seleccionado — sistema activado automáticamente")
        self._status_labels["MODO"].config(text="AUTO", fg=C["green"])

    def _set_modo_manual(self):
        """Cambia a modo MANUAL — el operador controla el inicio."""
        if self.modo == "MANUAL":
            return
        self.modo = "MANUAL"
        self._aplicar_visual_modo()
        self._log(">>> MODO MANUAL seleccionado — esperando operador")
        self._status_labels["MODO"].config(text="MANUAL", fg=C["amber"])

    def _aplicar_visual_modo(self):
        """
        Actualiza colores de botones de modo y muestra/oculta
        el botón ACTIVAR según el modo seleccionado.
        """
        if self.modo == "AUTO":
            # Botón AUTO activo (verde)
            self._btn_auto.config(bg=C["green_dim"], fg=C["green"])
            # Botón MANUAL inactivo
            self._btn_manual.config(bg=C["text_dark"], fg=C["text_gray"])
            # Ocultar botón ACTIVAR — no se necesita en AUTO
            self._btn_frame.pack_forget()
        else:
            # Botón MANUAL activo (púrpura)
            self._btn_manual.config(bg=C["purple_dk"], fg=C["purple"])
            # Botón AUTO inactivo
            self._btn_auto.config(bg=C["text_dark"], fg=C["text_gray"])
            # Mostrar botón ACTIVAR
            self._btn_frame.pack(side="right", padx=6)

    def _toggle(self):
        """Activar / desactivar manualmente (solo en modo MANUAL)."""
        self.sistema_activo = not self.sistema_activo
        if self.sistema_activo:
            self._btn_sys.config(text="[ DESACTIVAR ]",
                                 bg=C["red_dim"], fg=C["red"])
            self._log(">>> SISTEMA ACTIVADO por operador")
        else:
            self._btn_sys.config(text="[ ACTIVAR ]",
                                 bg=C["purple_dk"], fg=C["purple"])
            self._log(">>> Sistema detenido por operador")

    # ══════════════════════════════════════════════════
    #  SIMULACIÓN
    #  ─────────────────────────────────────────────────
    #  Para datos reales: reemplazar este método.
    #  Leer del sensor y asignar los mismos atributos.
    # ══════════════════════════════════════════════════
    def _simular(self):
        if not self.sistema_activo or self.touchdown:
            return
        dt = 0.1

        if self.altitud > 5000:
            self.fase = 1;  empuje = 0.0;   self.patas = [False]*4
        elif self.altitud > 3000:
            self.fase = 2;  empuje = random.uniform(5, 15)
        elif self.altitud > 1500:
            self.fase = 3;  empuje = random.uniform(40, 65)
            if not any(self.patas):
                self.patas = [True, True, False, False]
        elif self.altitud > 400:
            self.fase = 4;  empuje = random.uniform(65, 85)
            self.patas = [True]*4
        elif self.altitud > 0:
            self.fase = 4;  empuje = random.uniform(72, 90)
        else:
            self.fase = 5;  self.touchdown = True
            self.altitud = self.vel_vert = self.empuje = 0.0
            self._log(">>> ⬇  TOUCHDOWN CONFIRMADO")
            self.parent.after(1500, lambda: setattr(self, "fase", 6))
            return

        acel = -9.81 + (empuje / 100) * 22.0
        self.aceleracion = acel
        self.empuje      = empuje
        self.vel_vert    = max(self.vel_vert + acel * dt, -200.0)
        self.altitud     = max(0.0, self.altitud + self.vel_vert * dt)
        self.vel_horiz   = max(0.0, self.vel_horiz - random.uniform(0.05, 0.25))
        self.combustible = max(0.0, self.combustible - (empuje/100) * 0.08)
        self.temperatura = 38 + (empuje/100) * 680 + random.uniform(-5, 5)
        self.presion     = 1.0 + random.uniform(-0.05, 0.05)
        self.pitch       = random.gauss(0, 0.8)
        self.roll        = random.gauss(0, 0.6)
        self.yaw         = random.gauss(0, 0.4)
        drift            = 1.0 - (empuje/100) * 0.9
        self.error_lat   = (self.error_lat + random.gauss(0, drift*0.3)) * 0.97
        self.error_lon   = (self.error_lon + random.gauss(0, drift*0.3)) * 0.97
        self._trayectoria.append((max(0, self.altitud), self.vel_vert))
        if len(self._trayectoria) > 300:
            self._trayectoria.pop(0)

    # ══════════════════════════════════════════════════
    #  LOOP PRINCIPAL
    # ══════════════════════════════════════════════════
    def _loop(self):
        self._simular()
        self._pulse += 0.15
        self._tick  += 1
        self._update_labels()
        self._draw_descent()
        self._draw_zona()
        self._draw_attitude()
        self._draw_patas()
        self._update_fases()
        self._update_statusbar()
        if self.sistema_activo and self._tick % 20 == 0:
            self._log_telem()
        self.parent.after(100, self._loop)

    # ══════════════════════════════════════════════════
    #  ACTUALIZACIÓN DE LABELS
    # ══════════════════════════════════════════════════
    def _update_labels(self):
        self._lbl_alt.config(
            text=f"{self.altitud:7.1f} m",
            fg=C["red"] if self.altitud < 500 else C["purple"])
        vv_c = (C["green"] if abs(self.vel_vert) < 5 else
                C["amber"] if abs(self.vel_vert) < 30 else C["red"])
        self._lbl_vv.config(text=f"{self.vel_vert:+.1f} m/s", fg=vv_c)
        self._lbl_vh.config(text=f"{self.vel_horiz:.1f} m/s")
        self._lbl_acel.config(text=f"{self.aceleracion:+.2f} m/s²")
        tmp_c = (C["red"] if self.temperatura > 600 else
                 C["amber"] if self.temperatura > 200 else C["cyan"])
        self._lbl_temp.config(text=f"{self.temperatura:.0f} °C", fg=tmp_c)

        self._lbl_empuje.config(text=f"{self.empuje:.1f} %")
        self._lbl_comb.config(text=f"{self.combustible:.1f} %")
        self._bar_empuje.update_val(self.empuje)
        self._bar_comb.update_val(self.combustible)
        if self.vel_vert < -0.1:
            t_td = abs(self.altitud / self.vel_vert)
            self._lbl_ttd.config(text=f"{t_td:.0f} s",
                                 fg=C["red"] if t_td < 30 else C["green"])
        else:
            self._lbl_ttd.config(text="--- s")
        self._lbl_deltav.config(text=f"{abs(self.vel_vert):.1f} m/s")

        self._lbl_presion.config(text=f"{self.presion:.2f} bar")
        self._lbl_aletas.config(
            text="DESPLEGADAS" if self.aletas else "RETRAÍDAS",
            fg=C["green"] if self.aletas else C["red"])
        self._lbl_err_lat.config(
            text=f"{self.error_lat:.1f} m",
            fg=C["green"] if abs(self.error_lat) < 5 else C["amber"])
        self._lbl_err_lon.config(
            text=f"{self.error_lon:.1f} m",
            fg=C["green"] if abs(self.error_lon) < 5 else C["amber"])

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

        self._lbl_clock.config(text=datetime.now().strftime("T+%H:%M:%S"))

    # ══════════════════════════════════════════════════
    #  DIBUJADO
    # ══════════════════════════════════════════════════
    def _draw_descent(self):
        c = self._descent_canvas
        c.delete("all")
        w = c.winfo_width();  h = c.winfo_height()
        if w < 10 or h < 10:
            return
        for y in range(0, h, max(1, h//8)):
            c.create_line(0, y, w, y, fill=C["grid"])
        for x in range(0, w, max(1, w//8)):
            c.create_line(x, 0, x, h, fill=C["grid"])
        for alt_m in [0, 1000, 2000, 4000, 6000, 8000]:
            py = max(10, h - int((alt_m/self.ALTITUD_INICIO)*(h-20)) - 10)
            c.create_line(0, py, w, py, fill="#0d0a20", dash=(4, 6))
            c.create_text(4, py, text=f"{alt_m}m",
                          fill=C["purple_dim"], font=(MONO, 6), anchor="w")
        if len(self._trayectoria) >= 2:
            pts = []
            for i, (alt, _) in enumerate(self._trayectoria):
                px = int(w*0.15 + (i/len(self._trayectoria))*w*0.7)
                py = max(5, h - int((alt/self.ALTITUD_INICIO)*(h-20)) - 10)
                pts.extend([px, py])
            if len(pts) >= 4:
                c.create_line(pts, fill=C["purple_dim"], width=1, smooth=True)
        pct_alt = max(0, min(1, self.altitud/self.ALTITUD_INICIO))
        rx = w // 2
        ry = max(10, min(h-10, h - int(pct_alt*(h-20)) - 10))
        pulse = 6 + int(3*abs(math.sin(self._pulse)))
        c.create_line(rx, h, rx, ry, fill=C["purple_dim"], dash=(3, 5))
        if self.empuje > 10 and not self.touchdown:
            fl = int(8 + self.empuje/10)
            for _ in range(6):
                fx = rx + random.randint(-4, 4)
                fy = ry + random.randint(8, 8+fl)
                c.create_oval(fx-2, fy-2, fx+2, fy+2, fill=C["amber"], outline="")
        if not self.touchdown:
            c.create_polygon(rx-6, ry+12, rx+6, ry+12, rx, ry-12,
                             fill=C["purple"], outline=C["white"], width=1)
            c.create_oval(rx-pulse, ry-pulse, rx+pulse, ry+pulse,
                          outline=C["purple_dim"], width=1)
        else:
            c.create_text(rx, ry, text="✓ TOUCHDOWN", fill=C["green"], font=MONO_M)
        zw = 24
        c.create_rectangle(rx-zw, h-14, rx+zw, h-2,
                           fill=C["green_dim"], outline=C["green"], width=1)
        c.create_text(rx, h-8, text="ZONA", fill=C["green"], font=(MONO, 6))
        c.create_text(8, 8, text=f"ALT {self.altitud:.0f}m",
                      fill=C["purple"], font=(MONO, 7, "bold"), anchor="nw")
        c.create_text(w-8, 8, text=self.FASE_NOMBRES[self.fase],
                      fill=C["amber"], font=(MONO, 7, "bold"), anchor="ne")
        # Indicador de modo en el canvas
        modo_color = C["green"] if self.modo == "AUTO" else C["amber"]
        c.create_text(8, h-8, text=f"⟳ {self.modo}",
                      fill=modo_color, font=(MONO, 6, "bold"), anchor="sw")

    def _draw_zona(self):
        c = self._zona_canvas
        c.delete("all")
        w = c.winfo_width() or 160;  h = c.winfo_height() or 88
        if w < 10 or h < 10:
            return
        cx, cy = w//2, h//2
        for r, lbl in [(38, "50m"), (24, "25m"), (10, "10m")]:
            c.create_oval(cx-r, cy-r, cx+r, cy+r,
                          outline=C["purple_dim"], dash=(4, 4))
            c.create_text(cx+r+2, cy, text=lbl,
                          fill=C["text_gray"], font=(MONO, 5), anchor="w")
        c.create_line(cx-5, cy, cx+5, cy, fill=C["green"], width=2)
        c.create_line(cx, cy-5, cx, cy+5, fill=C["green"], width=2)
        scale = 38/50
        bx = max(5, min(w-5, int(cx + self.error_lat*scale)))
        by = max(5, min(h-5, int(cy - self.error_lon*scale)))
        p = 4 + int(2*abs(math.sin(self._pulse)))
        c.create_oval(bx-p, by-p, bx+p, by+p, outline=C["amber"], width=1)
        c.create_oval(bx-2, by-2, bx+2, by+2, fill=C["amber"], outline="")
        err = math.sqrt(self.error_lat**2 + self.error_lon**2)
        c.create_text(4, h-5, text=f"Δ {err:.1f}m",
                      fill=C["cyan"], font=(MONO, 6), anchor="sw")

    def _draw_attitude(self):
        c = self._att_canvas
        c.delete("all")
        w = c.winfo_width() or 110;  h = c.winfo_height() or 86
        if w < 10:
            return
        cx, cy = w//2, h//2
        r = min(cx, cy) - 4
        ang = math.radians(self.roll)
        dx = r*math.sin(ang);  dy = r*math.cos(ang)
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#0a0520", outline=C["border"])
        po = int((self.pitch/45)*r*0.5)
        c.create_rectangle(cx-r, cy+po, cx+r, cy+r+r, fill=C["purple_dk"], outline="")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill="", outline=C["border"])
        c.create_line(cx-dx, cy-dy+po, cx+dx, cy+dy+po, fill=C["amber"], width=2)
        c.create_line(cx-12, cy, cx+12, cy, fill=C["purple"], width=2)
        c.create_line(cx, cy-8, cx, cy+8, fill=C["purple"], width=2)
        c.create_oval(cx-3, cy-3, cx+3, cy+3, fill=C["purple"], outline="")
        c.create_text(4, 4, text="ATT", fill=C["purple_dim"],
                      font=(MONO, 6, "bold"), anchor="nw")

    def _draw_patas(self):
        for cv, dep in zip(self._pata_leds, self.patas):
            cv.delete("all")
            fill = C["green"]  if dep else C["red_dim"]
            ring = "#66cc00"   if dep else "#550011"
            cv.create_oval(0, 0, 20, 20, fill=C["bg"], outline="")
            cv.create_oval(2, 2, 18, 18, fill=ring, outline="")
            cv.create_oval(5, 5, 15, 15, fill=fill, outline="")

    def _update_fases(self):
        for i, (ind, lbl) in enumerate(self._fase_labels):
            ind.delete("all")
            if i < self.fase:
                ind.create_oval(1, 1, 9, 9, fill=C["green"], outline="")
                lbl.config(fg=C["text_gray"])
            elif i == self.fase:
                b = 0.6 + 0.4*abs(math.sin(self._pulse))
                ind.create_oval(1, 1, 9, 9,
                                fill=_hex_blend(C["purple"], b), outline="")
                lbl.config(fg=C["purple"])
            else:
                ind.create_oval(1, 1, 9, 9, fill=C["text_dark"], outline="")
                lbl.config(fg=C["text_dark"])
        self._lbl_fase.config(text=f"● {self.FASE_NOMBRES[self.fase]}")

    def _update_statusbar(self):
        s = self._status_labels
        s["ALTITUD"].config(text=f"{self.altitud:.0f}m",
                            fg=C["red"] if self.altitud < 500 else C["purple"])
        s["VEL.VERT"].config(text=f"{self.vel_vert:+.1f}m/s")
        s["COMBUSTIBLE"].config(text=f"{self.combustible:.0f}%",
                                fg=C["red"] if self.combustible < 20 else C["purple"])
        s["EMPUJE"].config(text=f"{self.empuje:.0f}%")
        ok = sum(self.patas)
        s["PATAS"].config(text=f"{ok}/4",
                          fg=C["green"] if ok == 4 else C["amber"])
        if self.touchdown:
            s["TOUCHDOWN"].config(text="✓ SÍ", fg=C["green"])

    # ══════════════════════════════════════════════════
    #  REINICIO Y LOG
    # ══════════════════════════════════════════════════
    def _reiniciar(self):
        # Detener antes de reiniciar
        if self.sistema_activo and self.modo == "MANUAL":
            self._toggle()
        elif self.modo == "AUTO":
            self.sistema_activo = False

        self.fase = 0;  self.altitud = self.ALTITUD_INICIO
        self.vel_vert = self.VEL_INICIAL;  self.vel_horiz = 12.0
        self.aceleracion = self.empuje = self.error_lat = self.error_lon = 0.0
        self.combustible = 100.0;  self.temperatura = 38.0;  self.presion = 1.0
        self.pitch = self.roll = self.yaw = 0.0
        self.patas = [False]*4;  self.touchdown = False
        self._trayectoria = [];  self._tick = 0
        self._log(">>> SIMULACIÓN REINICIADA — valores por defecto")

        # Si es AUTO, reanudar solo
        if self.modo == "AUTO":
            self.sistema_activo = True
            self._log(">>> MODO AUTO — reanudando automáticamente")

    def _log_telem(self):
        ts = datetime.now().strftime("%H:%M:%S")
        msg = (f"[{ts}] ALT={self.altitud:.0f}m  VV={self.vel_vert:+.1f}"
               f"  EMP={self.empuje:.0f}%  COMB={self.combustible:.1f}%"
               f"  T={self.temperatura:.0f}°C\n")
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
