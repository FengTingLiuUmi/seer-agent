"""战斗窗口：逐回合复刻 2.0.9 的对战展示（tkinter，标准库，零依赖）。

数据来源两种：

1. 本地模拟（`battle.simulate`）→ `ReplayModel.from_result()`
2. 2.0.9 真实出招记录（`applog.parse_battle_record`）→ `ReplayModel.from_record()`

窗口布局与雷小伊的战斗窗口一致：上方回合/控制，左右双方阵容与血条，
下方逐回合战报。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:  # 延迟到实例化才需要显示环境
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk
except Exception as _exc:  # pragma: no cover
    tk = None  # type: ignore[assignment]
    _TK_ERROR = _exc
else:
    _TK_ERROR = None


BG = "#0f1720"
PANEL = "#16212e"
PANEL_ALT = "#1d2b3a"
FGM = "#d8e6f2"
ACCENT = "#54c0ff"
WIN = "#5ddb8c"
LOSE = "#ff6b6b"
SELF_BAR = "#4ec9a8"
ENEMY_BAR = "#e0665f"
MUTED = "#8ba3b8"

_PLAYER_RE = re.compile(r"【我方[^】]*】\s*(?P<name>[^\[]+?)\s*\[(?P<id>\d+)\]")
_ENEMY_RE = re.compile(r"\(对方[^)]*\)\s*(?P<name>[^\[]+?)\s*\[(?P<id>\d+)\]")
_PLAYER_HP_RE = re.compile(r"我方剩余\s*(\d+)\s*/\s*(\d+)")
_ENEMY_HP_RE = re.compile(r"对方剩余\s*(\d+)\s*/\s*(\d+)")


@dataclass(slots=True)
class Fighter:
    id: int
    name: str
    hp: int = 0
    max_hp: int = 0
    alive: bool = True
    boosts: dict[str, int] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        if self.max_hp <= 0:
            return 0.0
        return max(0.0, min(1.0, self.hp / self.max_hp))


@dataclass(slots=True)
class ReplayTurn:
    turn: int
    texts: list[str] = field(default_factory=list)
    player: list[Fighter] = field(default_factory=list)
    enemy: list[Fighter] = field(default_factory=list)


@dataclass(slots=True)
class ReplayModel:
    title: str = "本地战斗"
    turns: list[ReplayTurn] = field(default_factory=list)
    result: str = ""
    boss_traits: list[str] = field(default_factory=list)
    header: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    @classmethod
    def from_result(cls, result: Any, *, title: str | None = None) -> "ReplayModel":
        model = cls(title=title or "本地战斗", result=_result_label(result.winner))
        model.header = list(result.log_lines[:0])
        for snap in result.snapshots:
            model.turns.append(
                ReplayTurn(
                    turn=snap.turn,
                    texts=list(snap.texts),
                    player=[_fighter(p) for p in snap.player],
                    enemy=[_fighter(p) for p in snap.enemy],
                )
            )
        return model

    @classmethod
    def from_record(cls, record: Any, *, title: str | None = None) -> "ReplayModel":
        """把 2.0.9 的 `出招记录/*.txt` 还原成逐回合画面（血量为 best-effort）。"""
        model = cls(title=title or "出招记录回放")
        players: dict[int, Fighter] = {}
        enemies: dict[int, Fighter] = {}
        for pid in record.player:
            players[pid] = Fighter(id=pid, name=str(pid))
        for eid in record.enemy:
            enemies[eid] = Fighter(id=eid, name=str(eid))
        model.boss_traits = list(record.boss_traits)
        model.result = _record_result(record)

        current = ReplayTurn(turn=0)
        for tr in record.turns:
            turn = ReplayTurn(turn=tr.turn)
            active_player: Fighter | None = None
            active_enemy: Fighter | None = None
            for line in tr.lines:
                turn.texts.append(line)
                if m := _PLAYER_RE.search(line):
                    pid = int(m.group("id"))
                    fighter = players.setdefault(pid, Fighter(id=pid, name=m.group("name").strip()))
                    fighter.name = m.group("name").strip()
                    active_player = fighter
                if m := _ENEMY_RE.search(line):
                    eid = int(m.group("id"))
                    fighter = enemies.setdefault(eid, Fighter(id=eid, name=m.group("name").strip()))
                    fighter.name = m.group("name").strip()
                    active_enemy = fighter
                if (m := _PLAYER_HP_RE.search(line)) and active_player is not None:
                    active_player.hp, active_player.max_hp = int(m.group(1)), int(m.group(2))
                    active_player.alive = active_player.hp > 0
                if (m := _ENEMY_HP_RE.search(line)) and active_enemy is not None:
                    active_enemy.hp, active_enemy.max_hp = int(m.group(1)), int(m.group(2))
                    active_enemy.alive = active_enemy.hp > 0
            turn.player = [_copy_fighter(f) for f in players.values()]
            turn.enemy = [_copy_fighter(f) for f in enemies.values()]
            model.turns.append(turn)
        if not model.turns:
            model.turns.append(current)
        return model


def _copy_fighter(f: Fighter) -> Fighter:
    return Fighter(f.id, f.name, f.hp, f.max_hp, f.alive, dict(f.boosts))


def _fighter(state: Any) -> Fighter:
    return Fighter(
        id=int(state.id),
        name=str(state.name),
        hp=int(state.hp),
        max_hp=int(state.max_hp),
        alive=bool(state.alive),
        boosts=dict(getattr(state, "boosts", {}) or {}),
    )


def _result_label(winner: str) -> str:
    return {"player": "胜利", "enemy": "失败", "draw": "平局"}.get(winner, "")


def _record_result(record: Any) -> str:
    return str(record.result or "")


# ---------------------------------------------------------------------------
class BattleWindow:
    """逐回合战斗窗口。"""

    def __init__(
        self,
        model: ReplayModel,
        *,
        interval_ms: int = 900,
        auto_play: bool = True,
        on_close: Any | None = None,
    ):
        if tk is None:  # pragma: no cover
            raise RuntimeError(f"tkinter 不可用: {_TK_ERROR}")
        self.model = model
        self.interval_ms = interval_ms
        self.speed = 1.0
        self.auto_play = auto_play
        self.on_close = on_close
        self.index = -1
        self._job: str | None = None
        self._bars: dict[tuple[str, int], tuple[Any, Any, Any]] = {}
        self._roster_sig: dict[str, tuple] = {}

        self.root = tk.Tk()
        self.root.title(f"战斗窗口 - {model.title}")
        self.root.geometry("1000x720")
        self.root.minsize(860, 600)
        self.root.configure(bg=BG)
        self._ui_font = tkfont.nametofont("TkDefaultFont")
        self._setup_fonts()
        self._build()
        self._render(len(self.model.turns) - 1 if not auto_play else -1)
        if auto_play:
            self.next_turn()

    # ------------------------------------------------------------------
    def _setup_fonts(self) -> None:
        family = "Microsoft YaHei UI"
        try:
            available = set(tkfont.families(self.root))
        except Exception:
            available = set()
        if family not in available:
            family = "Microsoft YaHei" if "Microsoft YaHei" in available else "TkDefaultFont"
        self.f_body = (family, 10)
        self.f_small = (family, 9)
        self.f_bold = (family, 10, "bold")
        self.f_title = (family, 13, "bold")
        self.f_hp = (family, 9, "bold")

    def _build(self) -> None:
        root = self.root
        header = tk.Frame(root, bg=PANEL, height=52)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        self.title_var = tk.StringVar(value=self.model.title)
        tk.Label(header, textvariable=self.title_var, bg=PANEL, fg=FGM, font=self.f_title).pack(
            side="left", padx=14
        )
        self.turn_var = tk.StringVar(value="回合 0/0")
        tk.Label(header, textvariable=self.turn_var, bg=PANEL, fg=ACCENT, font=self.f_bold).pack(
            side="left", padx=(4, 16)
        )
        self.result_var = tk.StringVar(value="")
        self.result_label = tk.Label(header, textvariable=self.result_var, bg=PANEL, fg=WIN, font=self.f_bold)
        self.result_label.pack(side="left", padx=6)

        ctrl = tk.Frame(header, bg=PANEL)
        ctrl.pack(side="right", padx=10)

        self.btn_play = self._button(ctrl, "播放", self.play)
        self.btn_pause = self._button(ctrl, "暂停", self.pause)
        self._button(ctrl, "上一回合", self.prev_turn)
        self._button(ctrl, "下一回合", self.next_turn)
        self._button(ctrl, "重播", self.restart)

        tk.Label(ctrl, text="速度", bg=PANEL, fg=MUTED, font=self.f_small).pack(side="left", padx=(8, 2))
        self.speed_var = tk.StringVar(value="1x")
        box = ttk.Combobox(ctrl, textvariable=self.speed_var, width=5, state="readonly",
                           values=("0.5x", "1x", "2x", "4x"))
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda _e: self._apply_speed())

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True)

        teams = tk.Frame(body, bg=BG)
        teams.pack(fill="x", side="top", padx=8, pady=6)
        left = tk.Frame(teams, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        right = tk.Frame(teams, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, padx=(4, 0))

        tk.Label(left, text="我方", bg=PANEL, fg=ACCENT, font=self.f_bold, anchor="w").pack(
            fill="x", padx=10, pady=(6, 2)
        )
        tk.Label(right, text="对方", bg=PANEL, fg=ENEMY_BAR, font=self.f_bold, anchor="w").pack(
            fill="x", padx=10, pady=(6, 2)
        )
        self.left_box = tk.Frame(left, bg=PANEL)
        self.left_box.pack(fill="x", padx=6, pady=(0, 6))
        self.right_box = tk.Frame(right, bg=PANEL)
        self.right_box.pack(fill="x", padx=6, pady=(0, 6))

        if self.model.boss_traits:
            traits = tk.Frame(body, bg=PANEL_ALT)
            traits.pack(fill="x", padx=8, pady=(0, 6))
            tk.Label(
                traits,
                text="BOSS 特性：" + "；".join(self.model.boss_traits),
                bg=PANEL_ALT,
                fg=MUTED,
                font=self.f_small,
                anchor="w",
                justify="left",
                wraplength=960,
            ).pack(fill="x", padx=10, pady=6)

        log_frame = tk.Frame(body, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tk.Label(log_frame, text="战报", bg=PANEL, fg=ACCENT, font=self.f_bold, anchor="w").pack(
            fill="x", padx=10, pady=(6, 0)
        )
        self.log = tk.Text(
            log_frame,
            bg="#0b1018",
            fg=FGM,
            insertbackground=FGM,
            font=self.f_body,
            relief="flat",
            wrap="word",
            padx=10,
            pady=8,
            spacing1=1,
            spacing3=3,
        )
        self.log.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.log.configure(state="disabled")
        self.log.tag_configure("turn", foreground=ACCENT, font=self.f_bold)
        self.log.tag_configure("win", foreground=WIN, font=self.f_bold)
        self.log.tag_configure("lose", foreground=LOSE, font=self.f_bold)
        self.log.tag_configure("muted", foreground=MUTED, font=self.f_small)

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Right>", lambda _e: self.next_turn())
        self.root.bind("<Left>", lambda _e: self.prev_turn())
        self.root.bind("<space>", lambda _e: self.pause() if self._job else self.play())

    def _button(self, parent: Any, text: str, command: Any) -> Any:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=PANEL_ALT,
            fg=FGM,
            activebackground=ACCENT,
            activeforeground=BG,
            relief="flat",
            font=self.f_small,
            padx=10,
            pady=3,
            cursor="hand2",
            borderwidth=0,
        )
        btn.pack(side="left", padx=3)
        return btn

    # ------------------------------------------------------------------
    def _roster(self, box: Any, fighters: list[Fighter], side: str) -> None:
        for child in box.winfo_children():
            child.destroy()
        for key in [k for k in self._bars if k[0] == side]:
            del self._bars[key]
        for f in fighters:
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill="x", pady=2)
            name = f"{f.name} [{f.id}]" if f.name and f.name != str(f.id) else f"[{f.id}]"
            label = tk.Label(row, text=name, bg=PANEL, fg=FGM if f.alive else MUTED,
                             font=self.f_bold, anchor="w", width=22)
            label.pack(side="left")
            canvas = tk.Canvas(row, height=14, width=260, bg="#0b1018", highlightthickness=0)
            canvas.pack(side="left", padx=6)
            fill = canvas.create_rectangle(0, 0, 0, 14, fill=SELF_BAR if side == "player" else ENEMY_BAR,
                                           width=0)
            hp_text = tk.Label(row, text="", bg=PANEL, fg=MUTED, font=self.f_hp, width=12, anchor="w")
            hp_text.pack(side="left")
            self._bars[(side, f.id)] = (canvas, fill, hp_text)
            self._paint(side, f)

    def _paint(self, side: str, f: Fighter) -> None:
        entry = self._bars.get((side, f.id))
        if not entry:
            return
        canvas, fill, hp_text = entry
        width = int(canvas.winfo_width())
        if width <= 1:
            width = 260
        ratio = f.ratio if f.max_hp else (1.0 if f.alive else 0.0)
        color = SELF_BAR if side == "player" else ENEMY_BAR
        if ratio <= 0.2:
            color = LOSE
        elif ratio <= 0.5:
            color = "#e8c14a"
        if not f.alive:
            ratio = 0.0
        canvas.coords(fill, 0, 0, int(width * ratio), 14)
        canvas.itemconfigure(fill, fill=color)
        if f.max_hp:
            hp_text.configure(text=f"{f.hp}/{f.max_hp}", fg=FGM if f.alive else LOSE)
        else:
            hp_text.configure(text="—", fg=MUTED)

    # ------------------------------------------------------------------
    def _render(self, index: int, *, force: bool = False) -> None:
        total = len(self.model.turns)
        if total == 0:
            return
        index = max(0, min(index, total - 1))
        if index == self.index and not force:
            return
        prev = self.index
        self.index = index
        turn = self.model.turns[index]
        self.turn_var.set(f"回合 {turn.turn}/{self.model.turns[-1].turn}")

        if prev < 0 or force:
            self._roster(self.left_box, turn.player, "player")
            self._roster(self.right_box, turn.enemy, "enemy")
            self._roster_sig["player"] = tuple((f.id, f.name) for f in turn.player)
            self._roster_sig["enemy"] = tuple((f.id, f.name) for f in turn.enemy)
        else:
            self._paint_all(turn.player, "player")
            self._paint_all(turn.enemy, "enemy")

        self.log.configure(state="normal")
        if prev < 0:
            self.log.delete("1.0", "end")
            for line in self.model.header:
                self.log.insert("end", line + "\n", "muted")
        self.log.insert("end", f"—— 第 {turn.turn} 回合 ——\n", "turn")
        for line in turn.texts:
            tag = ()
            if "【胜利】" in line or "胜利" == line.strip("【】"):
                tag = ("win",)
            elif "【失败】" in line:
                tag = ("lose",)
            elif line.startswith("BOSS特性"):
                tag = ("muted",)
            self.log.insert("end", line + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

        if index >= total - 1:
            self.pause()
            label = self.model.result or ""
            if label:
                self.result_var.set(f"结果：{label}")
                self.result_label.configure(fg=WIN if label == "胜利" else LOSE if label == "失败" else MUTED)
            self.btn_pause.configure(state="disabled")
        else:
            self.result_var.set("")

    def _paint_all(self, fighters: list[Fighter], side: str) -> None:
        sig = tuple((f.id, f.name) for f in fighters)
        if self._roster_sig.get(side) == sig:
            for f in fighters:
                self._paint(side, f)
            return
        box = self.left_box if side == "player" else self.right_box
        self._roster(box, fighters, side)
        self._roster_sig[side] = sig

    # ------------------------------------------------------------------
    def play(self) -> None:
        if self._job is not None:
            return
        if self.index >= len(self.model.turns) - 1:
            return
        self.btn_pause.configure(state="normal")
        self._tick()

    def pause(self) -> None:
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None

    def next_turn(self) -> None:
        self.pause()
        self._render(self.index + 1)

    def prev_turn(self) -> None:
        self.pause()
        if self.index > 0:
            self._render(self.index - 1, force=True)

    def restart(self) -> None:
        self.pause()
        self.index = -1
        self.result_var.set("")
        self.btn_pause.configure(state="normal")
        self.play()

    def _tick(self) -> None:
        if self.index >= len(self.model.turns) - 1:
            self.pause()
            return
        self._render(self.index + 1)
        if self.index >= len(self.model.turns) - 1:
            self.pause()
            return
        delay = max(80, int(self.interval_ms / max(0.25, self.speed)))
        self._job = self.root.after(delay, self._tick)

    def _apply_speed(self) -> None:
        text = self.speed_var.get().rstrip("x")
        try:
            self.speed = float(text)
        except ValueError:
            self.speed = 1.0
        if self._job is not None:
            self.pause()
            self.play()

    def _close(self) -> None:
        self.pause()
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()