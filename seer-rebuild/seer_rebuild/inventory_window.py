"""当前背包 / 当前装备 展示窗口（tkinter，风格仿雷小伊）。"""
from __future__ import annotations

from typing import Any

try:
    import tkinter as tk
    from tkinter import font as tkfont
except Exception as _exc:  # pragma: no cover
    tk = None  # type: ignore[assignment]
    _TK_ERROR = _exc
else:
    _TK_ERROR = None

from .inventory import InventorySnapshot

BG = "#0f1720"
PANEL = "#16212e"
PANEL_ALT = "#1d2b3a"
FGM = "#d8e6f2"
ACCENT = "#54c0ff"
MUTED = "#8ba3b8"
EQUIP_BAR = "#4ec9a8"


class InventoryWindow:
    def __init__(self, snapshot: InventorySnapshot, *, title: str = "背包与装备"):
        if tk is None:  # pragma: no cover
            raise RuntimeError(f"tkinter 不可用: {_TK_ERROR}")
        self.snapshot = snapshot
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("960x640")
        self.root.minsize(720, 480)
        self.root.configure(bg=BG)
        self._fonts()
        self._build()

    def _fonts(self) -> None:
        try:
            families = set(tkfont.families(self.root))
        except Exception:
            families = set()
        family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else "TkDefaultFont"
        self.f_title = (family, 13, "bold")
        self.f_bold = (family, 10, "bold")
        self.f_body = (family, 10)
        self.f_small = (family, 9)

    def _build(self) -> None:
        head = tk.Frame(self.root, bg=PANEL, height=52)
        head.pack(fill="x", side="top")
        head.pack_propagate(False)
        tk.Label(
            head,
            text=f"背包与装备{('  ·  ' + self.snapshot.source) if self.snapshot.source else ''}",
            bg=PANEL, fg=FGM, font=self.f_title, anchor="w",
        ).pack(side="left", padx=16)
        if self.snapshot.uid:
            tk.Label(head, text=f"UID {self.snapshot.uid}", bg=PANEL, fg=MUTED, font=self.f_small).pack(
                side="right", padx=16
            )

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        tl = tk.Frame(body, bg=PANEL)
        tl.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=(8, 4))
        tr = tk.Frame(body, bg=PANEL)
        tr.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=(8, 4))
        bl = tk.Frame(body, bg=PANEL)
        bl.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(4, 8))
        br = tk.Frame(body, bg=PANEL)
        br.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(4, 8))

        self._equip_panel(tl, "装备（头盔/护甲/武器）", self.snapshot.equipment)
        self._title_panel(tr, "称号（加成）", self.snapshot.titles)
        self._cloth_panel(bl, "装扮（时装/套装外观）", self.snapshot.clothes)
        self._item_panel(br, "背包道具", self.snapshot.items)

    def _equip_panel(self, parent: Any, heading: str, rows: list) -> None:
        tk.Label(parent, text=heading, bg=PANEL, fg="#5ddb8c", font=self.f_bold, anchor="w").pack(
            fill="x", padx=12, pady=(10, 2)
        )
        if not rows:
            tk.Label(parent, text="（无加成装备）", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").pack(
                fill="x", padx=16, pady=10
            )
            return
        table = tk.Frame(parent, bg=PANEL)
        table.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        tk.Label(table, text="部位", bg=PANEL, fg=MUTED, font=self.f_small, width=8, anchor="w").grid(
            row=0, column=0, sticky="w", padx=6, pady=3
        )
        tk.Label(table, text="装备", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").grid(
            row=0, column=1, sticky="w", padx=6, pady=3
        )
        for i, e in enumerate(rows, start=1):
            tk.Label(table, text=e.slot or "—", bg=PANEL, fg=FGM, font=self.f_body, anchor="w").grid(
                row=i, column=0, sticky="w", padx=6, pady=2
            )
            b = ("  →  " + e.bonus) if e.bonus else ""
            if e.suit_bonus:
                b += f"\n  套装[{e.suit}]：{e.suit_bonus}"
            tk.Label(table, text=e.label + b, bg=PANEL, fg=FGM, font=self.f_body, anchor="w", wraplength=280, justify="left").grid(
                row=i, column=1, sticky="w", padx=6, pady=2
            )

    def _cloth_panel(self, parent: Any, heading: str, rows: list) -> None:
        tk.Label(parent, text=heading, bg=PANEL, fg=ACCENT, font=self.f_bold, anchor="w").pack(
            fill="x", padx=12, pady=(10, 2)
        )
        if not rows:
            tk.Label(parent, text="（无外形装扮）", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").pack(
                fill="x", padx=16, pady=10
            )
            return
        table = tk.Frame(parent, bg=PANEL)
        table.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        tk.Label(table, text="部位", bg=PANEL, fg=MUTED, font=self.f_small, width=8, anchor="w").grid(
            row=0, column=0, sticky="w", padx=6, pady=3
        )
        tk.Label(table, text="装扮", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").grid(
            row=0, column=1, sticky="w", padx=6, pady=3
        )
        for i, e in enumerate(rows, start=1):
            tk.Label(table, text=e.slot or "—", bg=PANEL, fg=FGM, font=self.f_body, anchor="w").grid(
                row=i, column=0, sticky="w", padx=6, pady=2
            )
            tk.Label(table, text=e.label, bg=PANEL, fg=FGM, font=self.f_body, anchor="w").grid(
                row=i, column=1, sticky="w", padx=6, pady=2
            )

    def _title_panel(self, parent: Any, heading: str, rows: list) -> None:
        tk.Label(parent, text=heading, bg=PANEL, fg="#e8c14a", font=self.f_bold, anchor="w").pack(
            fill="x", padx=12, pady=(10, 2)
        )
        if not rows:
            tk.Label(parent, text="（无称号）", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").pack(
                fill="x", padx=16, pady=10
            )
            return
        table = tk.Frame(parent, bg=PANEL)
        table.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        tk.Label(table, text="称号", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").grid(
            row=0, column=0, sticky="w", padx=6, pady=3
        )
        for i, t in enumerate(rows, start=1):
            b = ("  →  " + t.bonus) if t.bonus else ""
            if t.desc:
                b += f"\n  {t.desc}"
            tk.Label(table, text=t.label + b, bg=PANEL, fg=FGM, font=self.f_body, anchor="w",
                     wraplength=280, justify="left").grid(row=i, column=0, sticky="w", padx=6, pady=2)

    def _item_panel(self, parent: Any, heading: str, rows: list) -> None:
        tk.Label(parent, text=heading, bg=PANEL, fg=ACCENT, font=self.f_bold, anchor="w").pack(
            fill="x", padx=12, pady=(10, 2)
        )
        if not rows:
            tk.Label(parent, text="（无道具）", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").pack(
                fill="x", padx=16, pady=10
            )
            return
        table = tk.Frame(parent, bg=PANEL)
        table.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        tk.Label(table, text="×数量", bg=PANEL, fg=MUTED, font=self.f_small, width=8, anchor="w").grid(
            row=0, column=0, sticky="w", padx=6, pady=3
        )
        tk.Label(table, text="名称", bg=PANEL, fg=MUTED, font=self.f_small, anchor="w").grid(
            row=0, column=1, sticky="w", padx=6, pady=3
        )
        for i, it in enumerate(rows, start=1):
            tk.Label(table, text=f"×{it.count}", bg=PANEL, fg=FGM, font=self.f_body, anchor="w").grid(
                row=i, column=0, sticky="w", padx=6, pady=2
            )
            tk.Label(table, text=it.label, bg=PANEL, fg=FGM, font=self.f_body, anchor="w").grid(
                row=i, column=1, sticky="w", padx=6, pady=2
            )

    def run(self) -> None:
        self.root.mainloop()