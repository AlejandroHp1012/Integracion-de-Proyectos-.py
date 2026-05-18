"""
╔══════════════════════════════════════════════════════════════════╗
║     ROCKET MISSION CONTROL — PANTALLA UNIFICADA v1.1            ║
║     MISION ALPHA-001 // GROUND CONTROL STATION                  ║
║     + MAVLink / ESP32 (Equipo 1)                                ║
╠══════════════════════════════════════════════════════════════════╣
║  Dependencias:                                                  ║
║    pip install pyserial                                         ║
║                                                                 ║
║  Para agregar un módulo nuevo:                                  ║
║    1. El equipo entrega su archivo modulo_XXX.py                ║
║    2. Descomentar el import correspondiente abajo               ║
║    3. En _build_grid(), reemplazar build_placeholder(...)       ║
║       por ModuloXXX(qN)                                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
import time

# ── Colores globales de la barra principal ────────────────────────
CYAN      = "#00D4FF"
AMBER     = "#FFB800"
BLUE_LT   = "#1E90FF"
TEXT_GRAY = "#4A6080"
TEXT_DARK = "#1E2D40"
MONO      = "Courier New"

# ══════════════════════════════════════════════════════════════════
#  IMPORTS DE MÓDULOS
#  Cuando un equipo entregue su archivo, descomentar su línea
# ══════════════════════════════════════════════════════════════════
from modulo_despegue     import ModuloDespegue       # ✓ Equipo 1 — MAVLink integrado
from modulo_recuperacion import ModuloRecuperacion   # ✓ Equipo 4 — listo
from modulo_despliegue   import ModuloDespliegue     # ✓ Equipo 2 — listo  (D mayúscula)
from modulo_aterrizaje   import ModuloAterrizaje     # ✓ Equipo 3 — listo


# ══════════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════════
class MisionControlCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MISION ALPHA-001 — ROCKET CONTROL CENTER")
        self.geometry("1920x1200")
        self.minsize(1400, 900)
        self.configure(bg="#010408")

        self.rowconfigure(0, weight=0)   # titlebar fija
        self.rowconfigure(1, weight=1)   # módulos se expanden
        self.rowconfigure(2, weight=0)   # footer fijo
        self.columnconfigure(0, weight=1)

        self._build_titlebar()
        self._build_grid()
        self._build_footer()
        self._blink_dot()

    # ── Barra de título ───────────────────────────────────────────
    def _build_titlebar(self):
        bar = tk.Frame(self, bg="#010408", height=38)
        bar.grid(row=0, column=0, sticky="ew")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=CYAN, height=2).pack(fill="x")

        inner = tk.Frame(bar, bg="#010408")
        inner.pack(fill="both", expand=True, padx=16)

        tk.Label(inner,
                 text="◈  ROCKET CONTROL CENTER  //  MISION ALPHA-001",
                 font=(MONO, 12, "bold"), bg="#010408", fg=CYAN).pack(side="left")

        right = tk.Frame(inner, bg="#010408")
        right.pack(side="right")
        self.lbl_clock = tk.Label(right, text="",
                                  font=(MONO, 10, "bold"), bg="#010408", fg=AMBER)
        self.lbl_clock.pack(side="right", padx=(8, 0))
        tk.Label(right, text="MISSION CLOCK:", font=(MONO, 8),
                 bg="#010408", fg=TEXT_GRAY).pack(side="right")
        self._tick_clock()
        tk.Frame(bar, bg=BLUE_LT, height=1).pack(fill="x", side="bottom")

    def _tick_clock(self):
        self.lbl_clock.config(text=time.strftime("T+%H:%M:%S UTC"))
        self.after(1000, self._tick_clock)

    # ── Cuadrícula 2×2 ────────────────────────────────────────────
    def _build_grid(self):
        grid = tk.Frame(self, bg="#0A1020")
        grid.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        # Configurar grid: todas las divisiones iguales (2x2 uniforme)
        grid.rowconfigure(0, weight=1, uniform="row")      
        grid.rowconfigure(1, weight=1, uniform="row")      
        grid.columnconfigure(0, weight=1, uniform="col")
        grid.columnconfigure(1, weight=1, uniform="col")

        # ── Cuadrante 1: DESPEGUE — MAVLink via ESP32 ────────────
        q1 = tk.Frame(grid, bg="#04080F",
                      highlightbackground=CYAN, highlightthickness=2)
        q1.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=(0, 2))
        ModuloDespegue(q1)

        # ── Cuadrante 2: DESPLIEGUE ───────────────────────────────
        q2 = tk.Frame(grid, bg="#04080F",
                      highlightbackground="#FF6B00", highlightthickness=2)
        q2.grid(row=0, column=1, sticky="nsew", padx=(2, 0), pady=(0, 2))
        ModuloDespliegue(q2)

        # ── Cuadrante 3: ATERRIZAJE ───────────────────────────────
        q3 = tk.Frame(grid, bg="#04080F",
                      highlightbackground="#A855F7", highlightthickness=2)
        q3.grid(row=1, column=0, sticky="nsew", padx=(0, 2), pady=(2, 0))
        ModuloAterrizaje(q3)

        # ── Cuadrante 4: RECUPERACIÓN ─────────────────────────────
        q4 = tk.Frame(grid, bg="#080c08",
                      highlightbackground="#2aff2a", highlightthickness=2)
        q4.grid(row=1, column=1, sticky="nsew", padx=(2, 0), pady=(2, 0))
        ModuloRecuperacion(q4)

    # ── Footer ────────────────────────────────────────────────────
    def _build_footer(self):
        f = tk.Frame(self, bg="#010408", height=22)
        f.grid(row=2, column=0, sticky="ew")
        f.pack_propagate(False)
        tk.Frame(f, bg=BLUE_LT, height=1).pack(fill="x", side="top")
        tk.Label(f,
                 text="SISTEMA CRITICO — USO EXCLUSIVO OPERADORES AUTORIZADOS  |  "
                      "MODULOS: DESPEGUE ✓(MAVLink)  DESPLIEGUE ✓  ATERRIZAJE ✓  RECUPERACION ✓",
                 font=(MONO, 7), bg="#010408", fg=TEXT_GRAY).pack(side="left", padx=14)
        self.dot = tk.Label(f, text="●", font=(MONO, 10, "bold"),
                            bg="#010408", fg=TEXT_DARK)
        self.dot.pack(side="right", padx=14)

    def _blink_dot(self):
        c = self.dot.cget("fg")
        self.dot.config(fg=CYAN if c == TEXT_DARK else TEXT_DARK)
        self.after(700, self._blink_dot)


# ══════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = MisionControlCenter()
    app.protocol("WM_DELETE_WINDOW", app.destroy)
    app.mainloop()
