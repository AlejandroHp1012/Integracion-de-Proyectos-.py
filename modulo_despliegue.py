"""
╔══════════════════════════════════════════════════════╗
║  MÓDULO DESPLIEGUE — Equipo 2                       ║
║  Clase: ModuloDespliegue                            ║
║  Recibe un tk.Frame como contenedor                 ║
╚══════════════════════════════════════════════════════╝

INSTRUCCIONES PARA EL EQUIPO 2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Desarrollen toda su interfaz DENTRO de la clase
     ModuloDespliegue, usando self.parent como
     contenedor raíz (es un tk.Frame, NO una ventana).

  2. NO usen tk.Tk() ni root.mainloop() — eso ya lo
     maneja el archivo principal (main.py).

  3. Para referenciar el frame raíz usen: self.parent
     Ejemplo:
       tk.Label(self.parent, text="Hola").pack()

  4. Para timers/animaciones usen:
       self.parent.after(100, self.mi_funcion)
     en lugar de root.after(...)

  5. Cuando terminen, avisen al integrador para
     conectar este archivo al main.py.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import tkinter as tk
from tkinter import ttk
# Agreguen aquí sus imports adicionales


class ModuloDespliegue:
    """
    Módulo de Despliegue — Equipo 2.
    El integrador llama: ModuloDespliegue(frame)
    donde frame es el cuadrante asignado en pantalla.
    """
    def __init__(self, parent_frame):
        self.parent = parent_frame

        # ── Inicialicen sus variables de estado aquí ──────────────
        # Ejemplo:
        # self.sistema_activo = False
        # self.altitud = 0.0

        # ── Construir la interfaz ─────────────────────────────────
        self._construir_ui()

    def _construir_ui(self):
        """
        Construyan aquí toda su interfaz gráfica.
        Usen self.parent como contenedor principal.
        """

        # ── EJEMPLO DE ESTRUCTURA (borren y reemplacen) ───────────

        # Header
        header = tk.Frame(self.parent, bg="#04080F", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Frame(header, bg="#FF6B00", height=2).pack(fill="x")
        tk.Label(header, text="📡 DESPLIEGUE — Equipo 2",
                 font=("Courier New", 11, "bold"),
                 bg="#04080F", fg="#FF6B00").pack(side="left", padx=10, pady=8)

        # Área de contenido — reemplacen con su interfaz real
        contenido = tk.Frame(self.parent, bg="#04080F")
        contenido.pack(fill="both", expand=True)

        tk.Label(contenido,
                 text="[ Coloquen su interfaz aquí ]",
                 font=("Courier New", 12),
                 bg="#04080F", fg="#4A6080").place(relx=0.5, rely=0.5, anchor="center")

        # ── FIN DEL EJEMPLO ───────────────────────────────────────

    # ── Agreguen sus métodos aquí ─────────────────────────────────
    # Ejemplo:
    # def _actualizar(self):
    #     # lógica de actualización
    #     self.parent.after(100, self._actualizar)
