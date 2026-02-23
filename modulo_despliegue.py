"""
╔══════════════════════════════════════════════════════╗
║  MÓDULO DESPLIEGUE — Equipo 2                       ║
║  Clase: ModuloDespliegue                            ║
║  Recibe un tk.Frame como contenedor                 ║
╠══════════════════════════════════════════════════════╣
║  RESPONSABILIDADES DE ESTE MÓDULO:                  ║
║   • Detector de fase de vuelo                       ║
║   • Indicador de activación de paracaídas           ║
║   • Registro de eventos                             ║
║   • Confirmación de despliegue                      ║
╠══════════════════════════════════════════════════════╣
║  COMUNICACIÓN CON OTROS MÓDULOS:                    ║
║                                                     ║
║  RECIBE de Telemetría:                              ║
║    modulo.recibir_datos(datos: dict)                ║
║    → datos = {                                      ║
║        "altitud_m": float,                          ║
║        "velocidad_ms": float,                       ║
║        "fase": str,   ← "ASCENSO"|"APOGEO"|etc.    ║
║        "bateria_pct": float,                        ║
║      }                                              ║
║                                                     ║
║  ENVÍA a Recuperación:                              ║
║    on_despliegue_confirmado(payload: dict)          ║
║    → El integrador asigna este callback:            ║
║      despliegue.on_despliegue_confirmado =          ║
║          recuperacion.recibir_estado_final          ║
╚══════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk
import time
import math

# ── Paleta de colores (consistente con los otros módulos) ─────────────────────
BG_ROOT   = "#04080F"
BG_CARD   = "#0C1624"
BG_CARD2  = "#0A1220"
BG_INPUT  = "#060D18"
CYAN      = "#00D4FF"
GREEN     = "#00FF88"
RED       = "#FF2D55"
AMBER     = "#FFB800"
ORANGE    = "#FF6B00"
BLUE_LT   = "#1E90FF"
TEXT_GRAY = "#4A6080"
TEXT_DARK = "#1E2D40"
BORDER    = "#122035"
BORDER_C  = "#0A4060"
MONO      = "Courier New"

# ── Fases de vuelo ────────────────────────────────────────────────────────────
FASES_ORDEN = ["STANDBY", "ASCENSO", "APOGEO", "DESPLIEGUE", "DESCENSO", "ATERRIZAJE"]
FASES_COLOR = {
    "STANDBY":    TEXT_GRAY,
    "ASCENSO":    CYAN,
    "APOGEO":     AMBER,
    "DESPLIEGUE": ORANGE,
    "DESCENSO":   GREEN,
    "ATERRIZAJE": "#A855F7",
}

# ── Datos de demo para prueba local ──────────────────────────────────────────
TELEM_DEMO = [
    {"altitud_m":   0, "velocidad_ms":  0.0, "fase": "STANDBY",    "bateria_pct": 98.0},
    {"altitud_m":  45, "velocidad_ms": 28.5, "fase": "ASCENSO",    "bateria_pct": 97.8},
    {"altitud_m": 120, "velocidad_ms": 55.2, "fase": "ASCENSO",    "bateria_pct": 97.5},
    {"altitud_m": 230, "velocidad_ms": 42.1, "fase": "ASCENSO",    "bateria_pct": 97.1},
    {"altitud_m": 310, "velocidad_ms": 18.4, "fase": "ASCENSO",    "bateria_pct": 96.8},
    {"altitud_m": 387, "velocidad_ms":  3.2, "fase": "APOGEO",     "bateria_pct": 96.5},
    {"altitud_m": 391, "velocidad_ms":  0.8, "fase": "APOGEO",     "bateria_pct": 96.4},
    {"altitud_m": 388, "velocidad_ms": -1.1, "fase": "DESPLIEGUE", "bateria_pct": 96.2},
    {"altitud_m": 375, "velocidad_ms": -5.5, "fase": "DESCENSO",   "bateria_pct": 96.0},
    {"altitud_m": 290, "velocidad_ms": -7.0, "fase": "DESCENSO",   "bateria_pct": 95.4},
    {"altitud_m": 120, "velocidad_ms": -6.5, "fase": "DESCENSO",   "bateria_pct": 94.8},
    {"altitud_m":   5, "velocidad_ms": -2.1, "fase": "ATERRIZAJE", "bateria_pct": 94.3},
]


def _make_card(parent, title, accent=CYAN):
    """Panel con header — mismo estilo visual que modulo_despegue.py del Equipo 1."""
    outer = tk.Frame(parent, bg=accent, bd=1)
    outer.pack(fill="x", pady=3)
    hdr = tk.Frame(outer, bg="#061020", height=28)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Frame(hdr, bg=accent, width=4).pack(side="left", fill="y")
    tk.Label(hdr, text=f"  {title}", font=(MONO, 8, "bold"),
             bg="#061020", fg=accent, anchor="w").pack(side="left", fill="y")
    tk.Frame(outer, bg=accent, height=1).pack(fill="x")
    inner = tk.Frame(outer, bg=BG_CARD, padx=10, pady=8)
    inner.pack(fill="both", expand=True)
    return inner


class ModuloDespliegue:
    """
    Módulo de Despliegue — Equipo 2.
    El integrador llama: ModuloDespliegue(frame)

    CALLBACK para comunicarse con Recuperación:
        despliegue.on_despliegue_confirmado = recuperacion.recibir_estado_final

    MÉTODO PÚBLICO para recibir datos de Telemetría:
        despliegue.recibir_datos(datos: dict)
    """

    def __init__(self, parent_frame):
        self.parent = parent_frame

        # ── Estado interno ────────────────────────────────────────
        self.fase_actual      = "STANDBY"
        self.altitud          = 0.0
        self.velocidad        = 0.0
        self.bateria          = 0.0
        self.paracaidas_ok    = False
        self.despliegue_conf  = False
        self._alt_historial   = []
        self._paracaidas_anim = 0.0
        self._tick            = 0
        self._blink           = True
        self._demo_idx        = 0

        # ── Callback → Recuperación (integrador lo asigna) ────────
        self.on_despliegue_confirmado = None

        # ── Construir UI ──────────────────────────────────────────
        self._construir_ui()
        self._loop()

    # ══════════════════════════════════════════════════════════════
    #  CONSTRUCCIÓN DE UI
    # ══════════════════════════════════════════════════════════════

    def _construir_ui(self):
        self.parent.configure(bg=BG_ROOT)

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(self.parent, bg="#020609", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=ORANGE, height=2).pack(fill="x")

        row = tk.Frame(hdr, bg="#020609")
        row.pack(fill="both", expand=True, padx=10)
        tk.Label(row, text="🪂 DESPLIEGUE",
                 font=(MONO, 11, "bold"), bg="#020609", fg=ORANGE).pack(side="left")
        tk.Label(row, text="  MISION ALPHA-001",
                 font=(MONO, 7), bg="#020609", fg=TEXT_GRAY).pack(side="left")

        r = tk.Frame(row, bg="#020609")
        r.pack(side="right")
        self.lbl_clock = tk.Label(r, text="", font=(MONO, 7),
                                  bg="#020609", fg=TEXT_GRAY)
        self.lbl_clock.pack(anchor="e")
        self.lbl_fase_hdr = tk.Label(r, text="● STANDBY",
                                     font=(MONO, 8, "bold"),
                                     bg="#020609", fg=TEXT_GRAY)
        self.lbl_fase_hdr.pack(anchor="e")
        tk.Frame(hdr, bg=BLUE_LT, height=1).pack(fill="x", side="bottom")

        # ── Cuerpo ────────────────────────────────────────────────
        main = tk.Frame(self.parent, bg=BG_ROOT)
        main.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self.left = tk.Frame(main, bg=BG_ROOT)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self.right = tk.Frame(main, bg=BG_ROOT, width=210)
        self.right.pack(side="right", fill="both")
        self.right.pack_propagate(False)

        self._panel_fase()
        self._panel_paracaidas()
        self._panel_eventos()
        self._panel_datos()
        self._panel_grafica()
        self._panel_confirmacion()

    # ── Panel: Detector de fase ───────────────────────────────────
    def _panel_fase(self):
        inner = _make_card(self.left, "DETECTOR DE FASE DE VUELO", ORANGE)

        # Fase actual (grande)
        fase_box = tk.Frame(inner, bg=BG_INPUT,
                            highlightbackground=BORDER_C, highlightthickness=1)
        fase_box.pack(fill="x", pady=(0, 8))
        top = tk.Frame(fase_box, bg=BG_INPUT)
        top.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(top, text="FASE ACTUAL", font=(MONO, 7),
                 bg=BG_INPUT, fg=TEXT_GRAY).pack(side="left")
        self.lbl_fase_num = tk.Label(top, text="1 / 6",
                                     font=(MONO, 7), bg=BG_INPUT, fg=TEXT_GRAY)
        self.lbl_fase_num.pack(side="right")
        self.lbl_fase_grande = tk.Label(fase_box, text="STANDBY",
                                        font=(MONO, 18, "bold"),
                                        bg=BG_INPUT, fg=TEXT_GRAY)
        self.lbl_fase_grande.pack(pady=(2, 8))

        # Barra de progreso por fases
        prog = tk.Frame(inner, bg=BG_CARD)
        prog.pack(fill="x", pady=(0, 6))
        self.fase_dots = {}
        for i, fase in enumerate(FASES_ORDEN):
            col = tk.Frame(prog, bg=BG_CARD)
            col.pack(side="left", expand=True)
            dot = tk.Label(col, text="○", font=(MONO, 10, "bold"),
                           bg=BG_CARD, fg=TEXT_DARK)
            dot.pack()
            tk.Label(col, text=fase[:3], font=(MONO, 6),
                     bg=BG_CARD, fg=TEXT_DARK).pack()
            self.fase_dots[fase] = dot
            if i < len(FASES_ORDEN) - 1:
                tk.Label(prog, text="─", font=(MONO, 8),
                         bg=BG_CARD, fg=TEXT_DARK).pack(side="left")

        # Celdas de condición
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=4)
        cond_row = tk.Frame(inner, bg=BG_CARD)
        cond_row.pack(fill="x")
        for attr, label in [("lbl_cond_alt", "ALT"),
                             ("lbl_cond_vel", "VEL"),
                             ("lbl_cond_fase","FASE")]:
            cell = tk.Frame(cond_row, bg=BG_CARD2,
                            highlightbackground=BORDER, highlightthickness=1)
            cell.pack(side="left", expand=True, fill="x",
                      padx=2, ipady=4, ipadx=4)
            tk.Label(cell, text=label, font=(MONO, 6),
                     bg=BG_CARD2, fg=TEXT_GRAY).pack()
            lbl = tk.Label(cell, text="---", font=(MONO, 8, "bold"),
                           bg=BG_CARD2, fg=TEXT_DARK)
            lbl.pack()
            setattr(self, attr, lbl)

    # ── Panel: Paracaídas ─────────────────────────────────────────
    def _panel_paracaidas(self):
        inner = _make_card(self.left, "INDICADOR DE PARACAÍDAS", AMBER)

        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x")

        self.canvas_chute = tk.Canvas(row, width=80, height=70,
                                      bg=BG_CARD, highlightthickness=0)
        self.canvas_chute.pack(side="left", padx=(0, 12))
        self._dibujar_paracaidas(False, 0)

        info = tk.Frame(row, bg=BG_CARD)
        info.pack(side="left", fill="both", expand=True)
        self.lbl_chute_estado = tk.Label(info, text="EN ESPERA",
                                         font=(MONO, 12, "bold"),
                                         bg=BG_CARD, fg=TEXT_GRAY)
        self.lbl_chute_estado.pack(anchor="w")
        self.lbl_chute_sub = tk.Label(
            info,
            text="Aguardando condiciones\nde despliegue.",
            font=(MONO, 7), bg=BG_CARD, fg=TEXT_GRAY, justify="left")
        self.lbl_chute_sub.pack(anchor="w", pady=(4, 0))

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=6)
        self.chute_conds = {}
        for texto, key in [("Altitud en rango",      "alt"),
                            ("Velocidad decreciente", "vel"),
                            ("Apogeo detectado",      "apo"),
                            ("Comando recibido",      "cmd")]:
            f = tk.Frame(inner, bg=BG_CARD)
            f.pack(fill="x", pady=1)
            lbl = tk.Label(f, text="✗  " + texto,
                           font=(MONO, 7), bg=BG_CARD, fg=RED)
            lbl.pack(side="left")
            self.chute_conds[key] = (lbl, texto)

    # ── Panel: Eventos ────────────────────────────────────────────
    def _panel_eventos(self):
        inner = _make_card(self.left, "REGISTRO DE EVENTOS", BLUE_LT)
        self.eventos_text = tk.Text(
            inner, bg="#020A14", fg=TEXT_GRAY,
            font=(MONO, 7), relief="flat",
            height=7, state="disabled",
            insertbackground=CYAN)
        sb = ttk.Scrollbar(inner, orient="vertical",
                           command=self.eventos_text.yview)
        self.eventos_text.configure(yscrollcommand=sb.set)
        self.eventos_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._log("MÓDULO DESPLIEGUE v1.0 INICIADO", "SYS", CYAN)
        self._log("Aguardando datos de Telemetría.", "SYS", TEXT_GRAY)

    # ── Panel: Datos (columna derecha) ────────────────────────────
    def _panel_datos(self):
        inner = _make_card(self.right, "DATOS DE VUELO", CYAN)
        for label, attr, color in [("ALTITUD",   "lbl_d_alt",  CYAN),
                                    ("VELOCIDAD", "lbl_d_vel",  GREEN),
                                    ("BATERÍA",   "lbl_d_batt", AMBER)]:
            row = tk.Frame(inner, bg=BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=(MONO, 7),
                     bg=BG_CARD, fg=TEXT_GRAY).pack(side="left")
            lbl = tk.Label(row, text="---", font=(MONO, 10, "bold"),
                           bg=BG_CARD, fg=color)
            lbl.pack(side="right")
            setattr(self, attr, lbl)

    # ── Panel: Gráfica (columna derecha) ──────────────────────────
    def _panel_grafica(self):
        inner = _make_card(self.right, "PERFIL DE ALTITUD", BLUE_LT)
        self.canvas_graf = tk.Canvas(inner, bg="#020A14", height=80,
                                     highlightthickness=0)
        self.canvas_graf.pack(fill="x")

    # ── Panel: Confirmación (columna derecha) ─────────────────────
    def _panel_confirmacion(self):
        inner = _make_card(self.right, "CONFIRMACIÓN DE DESPLIEGUE", GREEN)

        self.lbl_auth = tk.Label(inner, text="  DENEGADA",
                                 font=(MONO, 7, "bold"), bg=BG_CARD, fg=RED)
        self.lbl_auth.pack(anchor="w", pady=(0, 4))

        self.btn_desplegar = tk.Button(
            inner,
            text="▶ DESPLEGAR\n   PARACAÍDAS",
            font=(MONO, 9, "bold"),
            bg="#1A0A00", fg=TEXT_DARK,
            relief="flat", bd=0, pady=10,
            cursor="hand2", state="disabled",
            command=self._confirmar_despliegue)
        self.btn_desplegar.pack(fill="x", pady=(0, 4))

        self.btn_manual = tk.Button(
            inner,
            text="⚠ DESPLIEGUE MANUAL",
            font=(MONO, 8, "bold"),
            bg="#1A0800", fg=AMBER,
            relief="flat", bd=0, pady=6,
            cursor="hand2",
            command=self._despliegue_manual)
        self.btn_manual.pack(fill="x")

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=6)
        tk.Label(inner, text="PAYLOAD → RECUPERACIÓN",
                 font=(MONO, 7), bg=BG_CARD, fg=TEXT_GRAY).pack(anchor="w")
        self.lbl_payload = tk.Label(
            inner, text='{ "status": "waiting" }',
            font=(MONO, 7), bg="#020A14", fg=TEXT_GRAY,
            justify="left", anchor="w", wraplength=180)
        self.lbl_payload.pack(fill="x", ipady=4, ipadx=4)

    # ══════════════════════════════════════════════════════════════
    #  GRÁFICAS Y ANIMACIONES
    # ══════════════════════════════════════════════════════════════

    def _dibujar_paracaidas(self, desplegado=False, animacion=0.0):
        c = self.canvas_chute
        c.delete("all")
        cx = 40

        if not desplegado:
            c.create_oval(32, 20, 48, 36, outline=TEXT_GRAY, fill=BG_CARD2, width=2)
            for lx in [36, 40, 44]:
                c.create_line(lx, 36, lx, 55, fill=TEXT_GRAY, dash=(2, 2))
            c.create_rectangle(34, 55, 46, 65, fill=BORDER, outline=TEXT_GRAY)
        else:
            swing = math.sin(animacion) * 6
            color = GREEN if self.despliegue_conf else AMBER
            pts = []
            for i in range(13):
                angle = math.radians(180 + i * 15)
                r = 28 + 4 * math.sin(animacion * 2 + i * 0.5)
                px = cx + swing * 0.3 + r * math.cos(angle)
                py = 15 + r * math.sin(angle) * 0.5
                pts.append((px, py))
            if len(pts) >= 3:
                flat = [v for p in pts for v in p]
                c.create_polygon(flat, fill=BG_CARD2, outline=color, width=2)
            for i in range(0, len(pts), 3):
                c.create_line(pts[i][0], pts[i][1],
                              cx + swing * 0.5, 55,
                              fill=color, width=1)
            c.create_rectangle(cx - 6 + swing * 0.5, 55,
                                cx + 6 + swing * 0.5, 67,
                                fill=BORDER, outline=color, width=1)

    def _actualizar_grafica(self):
        c = self.canvas_graf
        w = c.winfo_width() or 180
        h = c.winfo_height() or 80
        c.delete("all")
        hist = self._alt_historial[-40:]
        if len(hist) < 2:
            c.create_text(w // 2, h // 2, text="SIN DATOS",
                          fill=TEXT_DARK, font=(MONO, 8))
            return
        max_a = max(hist) or 1
        pts = []
        for i, a in enumerate(hist):
            x = int(i / (len(hist) - 1) * (w - 4)) + 2
            y = int(h - 6 - (a / max_a) * (h - 12))
            pts.append((x, y))
        area = [pts[0][0], h - 4] + [v for p in pts for v in p] + [pts[-1][0], h - 4]
        c.create_polygon(area, fill="#001428", outline="")
        flat = [v for p in pts for v in p]
        c.create_line(flat, fill=CYAN, width=2)
        lx, ly = pts[-1]
        c.create_oval(lx - 3, ly - 3, lx + 3, ly + 3, fill=ORANGE, outline=ORANGE)
        c.create_text(4, 4, text=f"{int(max_a)}m",
                      fill=TEXT_GRAY, font=(MONO, 6), anchor="nw")

    # ══════════════════════════════════════════════════════════════
    #  LOOP PRINCIPAL
    # ══════════════════════════════════════════════════════════════

    def _loop(self):
        self._tick += 1
        self.lbl_clock.config(text=time.strftime("T+%H:%M:%S"))

        # Parpadeo header
        if self._tick % 8 == 0:
            self._blink = not self._blink
        color_fase = FASES_COLOR[self.fase_actual]
        dot = "●" if self._blink or self.fase_actual == "STANDBY" else "○"
        self.lbl_fase_hdr.config(text=f"{dot} {self.fase_actual}", fg=color_fase)

        # Animación paracaídas
        if self.paracaidas_ok:
            self._paracaidas_anim += 0.12
            self._dibujar_paracaidas(True, self._paracaidas_anim)

        self._actualizar_grafica()
        self.parent.after(120, self._loop)

    # ══════════════════════════════════════════════════════════════
    #  LÓGICA DE DATOS
    # ══════════════════════════════════════════════════════════════

    def _actualizar_con_datos(self, datos: dict):
        self.altitud   = datos.get("altitud_m",    self.altitud)
        self.velocidad = datos.get("velocidad_ms", self.velocidad)
        self.bateria   = datos.get("bateria_pct",  self.bateria)
        nueva_fase     = datos.get("fase",         self.fase_actual).upper()

        self._alt_historial.append(self.altitud)
        if len(self._alt_historial) > 200:
            self._alt_historial = self._alt_historial[-200:]

        # Datos numéricos
        self.lbl_d_alt.config(text=f"{self.altitud:.1f} m")
        self.lbl_d_vel.config(
            text=f"{self.velocidad:+.1f} m/s",
            fg=GREEN if self.velocidad <= 0 else CYAN)
        self.lbl_d_batt.config(
            text=f"{self.bateria:.1f}%",
            fg=GREEN if self.bateria > 50 else AMBER if self.bateria > 20 else RED)

        # Celdas de condición
        self.lbl_cond_alt.config(
            text=f"{self.altitud:.0f}m",
            fg=GREEN if self.altitud > 50 else TEXT_GRAY)
        self.lbl_cond_vel.config(
            text=f"{self.velocidad:+.1f}",
            fg=GREEN if self.velocidad <= 0 else CYAN)
        self.lbl_cond_fase.config(
            text=nueva_fase[:4],
            fg=FASES_COLOR.get(nueva_fase, TEXT_GRAY))

        # Cambio de fase
        if nueva_fase != self.fase_actual and nueva_fase in FASES_ORDEN:
            self._cambiar_fase(nueva_fase)

        # Condiciones del paracaídas
        self._actualizar_condiciones_chute()

    def _cambiar_fase(self, nueva_fase: str):
        anterior = self.fase_actual
        self.fase_actual = nueva_fase
        color = FASES_COLOR[nueva_fase]
        idx = FASES_ORDEN.index(nueva_fase) + 1

        self.lbl_fase_grande.config(text=nueva_fase, fg=color)
        self.lbl_fase_num.config(text=f"{idx} / {len(FASES_ORDEN)}", fg=color)

        for fase in FASES_ORDEN:
            fi = FASES_ORDEN.index(fase)
            ni = FASES_ORDEN.index(nueva_fase)
            if fi < ni:
                self.fase_dots[fase].config(text="●", fg=GREEN)
            elif fi == ni:
                self.fase_dots[fase].config(text="◉", fg=color)
            else:
                self.fase_dots[fase].config(text="○", fg=TEXT_DARK)

        self._log(f"FASE: {anterior} → {nueva_fase}", "FASE", color)

        if nueva_fase == "DESPLIEGUE":
            self._activar_paracaidas()

    def _actualizar_condiciones_chute(self):
        cond_alt = self.altitud > 50
        cond_vel = self.velocidad <= 0
        cond_apo = self.fase_actual in ("APOGEO", "DESPLIEGUE", "DESCENSO", "ATERRIZAJE")
        cond_cmd = self.fase_actual in ("DESPLIEGUE", "DESCENSO", "ATERRIZAJE")

        for key, ok in [("alt", cond_alt), ("vel", cond_vel),
                         ("apo", cond_apo), ("cmd", cond_cmd)]:
            lbl, texto = self.chute_conds[key]
            lbl.config(text=("✓  " if ok else "✗  ") + texto,
                       fg=GREEN if ok else RED)

        # Habilitar botón de despliegue
        if cond_alt and cond_vel and cond_apo and not self.paracaidas_ok:
            self.btn_desplegar.config(state="normal", fg=GREEN,
                                      bg="#001800", cursor="hand2")
            self.lbl_auth.config(text="  AUTORIZADO", fg=GREEN)

    def _activar_paracaidas(self):
        self.paracaidas_ok = True
        self.lbl_chute_estado.config(text="ACTIVADO", fg=GREEN)
        self.lbl_chute_sub.config(
            text="Paracaídas desplegado.\nDescenso controlado.", fg=GREEN)
        self._log("PARACAÍDAS ACTIVADO AUTOMÁTICAMENTE", "CHT", GREEN)

    # ══════════════════════════════════════════════════════════════
    #  ACCIONES DE BOTONES
    # ══════════════════════════════════════════════════════════════

    def _confirmar_despliegue(self):
        if self.despliegue_conf:
            return
        self.despliegue_conf = True
        self.paracaidas_ok   = True

        self.btn_desplegar.config(text="✓ CONFIRMADO",
                                  state="disabled", fg=CYAN, bg="#001428")
        self.lbl_chute_estado.config(text="CONFIRMADO", fg=GREEN)
        self.lbl_chute_sub.config(
            text="Despliegue confirmado\npor operador.", fg=GREEN)
        self.lbl_auth.config(text="  CONFIRMADO ✓", fg=GREEN)
        self._log("DESPLIEGUE CONFIRMADO POR OPERADOR", "CHT", GREEN)

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
            fg=GREEN)

        # ── Notificar a Recuperación ──────────────────────────────
        if callable(self.on_despliegue_confirmado):
            self.on_despliegue_confirmado(payload)

    def _despliegue_manual(self):
        self._log("⚠ DESPLIEGUE MANUAL ACTIVADO", "EMRG", AMBER)
        self._activar_paracaidas()
        self.btn_desplegar.config(state="normal", fg=GREEN, bg="#001800")
        self.lbl_auth.config(text="  MANUAL", fg=AMBER)

    # ══════════════════════════════════════════════════════════════
    #  MÉTODO PÚBLICO — Telemetría llama esto con cada dato
    # ══════════════════════════════════════════════════════════════

    def recibir_datos(self, datos: dict):
        """
        Telemetría llama este método con cada actualización.
        datos = {
            "altitud_m":    float,
            "velocidad_ms": float,
            "fase":         str,
            "bateria_pct":  float,
        }
        """
        self._actualizar_con_datos(datos)

    # ══════════════════════════════════════════════════════════════
    #  LOG
    # ══════════════════════════════════════════════════════════════

    def _log(self, msg, tag="SYS", color=None):
        color = color or TEXT_GRAY
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}][{tag}] {msg}\n"
        t = self.eventos_text
        t.config(state="normal")
        t.insert("end", line)
        t.see("end")
        t.config(state="disabled")

    # ══════════════════════════════════════════════════════════════
    #  DEMO LOCAL
    # ══════════════════════════════════════════════════════════════

    def _demo_tick(self):
        """Simula llegada de datos de Telemetría para prueba local."""
        if self._demo_idx < len(TELEM_DEMO):
            self.recibir_datos(TELEM_DEMO[self._demo_idx])
            self._demo_idx += 1
            self.parent.after(1200, self._demo_tick)
        else:
            self._log("Demo completo.", "SYS", AMBER)


# ══════════════════════════════════════════════════════════════════
#  PRUEBA LOCAL — el main.py NO usa este bloque.
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    def simular_recuperacion(payload):
        print("\n[RECUPERACIÓN recibió estado final de despliegue]")
        for k, v in payload.items():
            print(f"  {k}: {v}")

    root = tk.Tk()
    root.title("PRUEBA — Módulo Despliegue (Equipo 2)")
    root.geometry("1000x640")
    root.configure(bg=BG_ROOT)
    frame = tk.Frame(root, bg=BG_ROOT)
    frame.pack(fill="both", expand=True)
    modulo = ModuloDespliegue(frame)
    modulo.on_despliegue_confirmado = simular_recuperacion
    root.after(1000, modulo._demo_tick)
    root.mainloop()


