#!/usr/bin/env python3
"""Masaüstü post-it: data/deadlines.json'daki yaklaşan deadline'ları gösterir."""
import datetime as dt
import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT_FILE = DATA / "deadlines.json"
DONE_FILE = DATA / "done.json"
WIN_FILE = DATA / "window.json"
SITES_FILE = DATA / "sites.txt"

YELLOW = "#FFF59D"
EDGE = "#D9C64A"      # kağıdın sağ/alt kenarı (gölge hissi)
TAPE = "#F3EFD9"      # üstteki bant
LINE = "#EBDB6A"
INK = "#3E3A1F"
MUTED = "#7A7350"
RED = "#D84315"
ORANGE = "#EF8F00"
GREEN = "#558B2F"
WIDTH, HEIGHT = 340, 460   # varsayılan boyut (köşeden sürükleyerek değiştirilebilir)
MIN_W, MIN_H = 260, 170
REFRESH_MS = 60_000

TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
TR_DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def hide_dock_icon():
    """Dock'ta roket ikonu çıkmasın (pyobjc kuruluysa)."""
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def pin_to_desktop():
    """Post-it'i masaüstü katmanına koy: uygulama pencerelerinin ALTINDA, masaüstü ikonlarının
    üstünde kalır; tüm masaüstlerinde (Spaces) görünür, Cmd-Tab/Mission Control'de çıkmaz."""
    try:
        from AppKit import NSApplication
        from Quartz import CGWindowLevelForKey, kCGDesktopIconWindowLevelKey
        level = CGWindowLevelForKey(kCGDesktopIconWindowLevelKey) + 1
        behavior = (1 << 0) | (1 << 4) | (1 << 6)  # CanJoinAllSpaces | Stationary | IgnoresCycle
        for w in NSApplication.sharedApplication().windows():
            if w.level() != level:
                w.setLevel_(level)
            w.setCollectionBehavior_(behavior)
            w.setHasShadow_(True)
    except Exception:
        pass


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def item_key(d):
    return f"{d['title'].strip().lower()}|{d['deadline_date']}"


class PostIt:
    def __init__(self, root):
        self.root = root
        self.done = set(read_json(DONE_FILE, []))
        self.last_mtime = None

        self.collapsed = False
        root.title("Deadline'lar")
        root.overrideredirect(True)          # başlık çubuğu yok: gerçek post-it gibi
        root.configure(bg=EDGE)
        root.resizable(False, False)
        self.w, self.h = WIDTH, HEIGHT
        self.place_window()

        # Kenar (gölge hissi) + kağıt
        self.paper = tk.Frame(root, bg=YELLOW)
        self.paper.pack(fill="both", expand=True, padx=(0, 2), pady=(0, 2))

        # Üstte bant
        tape_row = tk.Frame(self.paper, bg=YELLOW, height=14)
        tape_row.pack(fill="x")
        tk.Frame(tape_row, bg=TAPE, width=90, height=14).place(relx=0.5, y=0, anchor="n")

        header = tk.Frame(self.paper, bg=YELLOW)
        header.pack(fill="x")
        self.title_lbl = tk.Label(header, text="Yaklaşan Deadline'lar", bg=YELLOW, fg=INK,
                                  font=("Marker Felt", 18))
        self.title_lbl.pack(side="left", padx=12, pady=(0, 2))
        self.btn_collapse = self.icon_button(header, "–", self.toggle_collapse)
        self.btn_refresh = self.icon_button(header, "⟳", self.refresh_mail)
        tk.Frame(self.paper, bg=LINE, height=1).pack(fill="x", padx=12)

        # Alt bilgi en alta sabit (pencere küçülünce önce liste küçülsün)
        self.footer = tk.Label(self.paper, text="", bg=YELLOW, fg=MUTED, font=("Helvetica", 10),
                               anchor="w")
        self.footer.pack(side="bottom", fill="x", padx=(12, 22), pady=(0, 10))

        # Kaydırılabilir liste: Canvas içinde çerçeve + ince kaydırma çubuğu
        self.body_wrap = tk.Frame(self.paper, bg=YELLOW)
        self.body_wrap.pack(fill="both", expand=True, padx=(12, 4), pady=(6, 2))
        self.canvas = tk.Canvas(self.body_wrap, bg=YELLOW, highlightthickness=0, bd=0,
                                width=10, height=10, yscrollincrement=12)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb = tk.Scrollbar(self.body_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.body = tk.Frame(self.canvas, bg=YELLOW)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.scrollable = False
        root.bind_all("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Configure>", lambda e: self.fit_list())

        # Sağ alt köşede boyutlandırma tutamacı
        self.grip = tk.Label(self.paper, text="◢", bg=YELLOW, fg=EDGE, font=("Helvetica", 13))
        try:
            self.grip.config(cursor="bottom_right_corner")
        except tk.TclError:
            pass
        self.grip.place(relx=1.0, rely=1.0, anchor="se", x=-3, y=-2)
        self.grip.bind("<ButtonPress-1>", self.resize_start)
        self.grip.bind("<B1-Motion>", self.resize_move)
        self.grip.bind("<ButtonRelease-1>", self.resize_end)

        # Sağ tık menüsü
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Mailleri şimdi tara", command=self.refresh_mail)
        self.menu.add_command(label="Ders sitesi ekle…", command=self.add_site)
        self.menu.add_command(label="Ders sitelerini düzenle", command=self.edit_sites)
        self.menu.add_separator()
        self.menu.add_command(label="Bitti işaretlenenleri geri getir", command=self.restore_done)
        self.menu.add_separator()
        self.menu.add_command(label="Kapat (bir sonraki açılışta geri gelir)", command=self.on_close)
        # Sürükleyerek taşıma: kağıdın herhangi bir yerinden
        self.drag_from = None
        self.resize_from = None
        for w in (self.paper, tape_row, header, self.title_lbl, self.footer, self.body, self.canvas):
            self.make_draggable(w)

        self.render(force=True)
        self.root.update_idletasks()
        pin_to_desktop()
        self.root.after(300, pin_to_desktop)
        self.root.after(REFRESH_MS, self.tick)

    def make_draggable(self, w):
        w.bind("<ButtonPress-1>", self.drag_start, add="+")
        w.bind("<B1-Motion>", self.drag_move, add="+")
        w.bind("<ButtonRelease-1>", lambda e: self.save_window(), add="+")
        w.bind("<Button-2>", self.show_menu, add="+")
        w.bind("<Button-3>", self.show_menu, add="+")
        w.bind("<Control-Button-1>", self.show_menu, add="+")

    def drag_start(self, e):
        self.drag_from = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def drag_move(self, e):
        if self.drag_from:
            self.root.geometry(f"+{e.x_root - self.drag_from[0]}+{e.y_root - self.drag_from[1]}")

    def resize_start(self, e):
        self.resize_from = (e.x_root, e.y_root, self.w, self.h)

    def resize_move(self, e):
        if not self.resize_from:
            return
        x0, y0, w0, h0 = self.resize_from
        self.w = max(MIN_W, w0 + e.x_root - x0)
        self.h = max(MIN_H, h0 + e.y_root - y0)
        self.root.geometry(f"{self.w}x{self.h}")

    def resize_end(self, e):
        self.resize_from = None
        self.save_window()
        self.render(force=True)   # yazıları yeni genişliğe göre yeniden sar

    def show_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)


    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body_wrap.pack_forget()
            self.footer.pack_forget()
            self.grip.place_forget()
            self.root.update_idletasks()
            self.root.geometry(f"{self.w}x{self.paper.winfo_reqheight() + 8}")
        else:
            self.footer.pack(side="bottom", fill="x", padx=(12, 22), pady=(0, 10))
            self.body_wrap.pack(fill="both", expand=True, padx=(12, 4), pady=(6, 2))
            self.grip.place(relx=1.0, rely=1.0, anchor="se", x=-3, y=-2)
            self.root.geometry(f"{self.w}x{self.h}")
        self.btn_collapse.config(text="+" if self.collapsed else "–")
        self.update_title()

    def on_wheel(self, e):
        if not self.scrollable or self.collapsed:
            return
        d = e.delta if abs(e.delta) < 120 else e.delta // 120
        self.canvas.yview_scroll(-d if d else 0, "units")

    def fit_list(self):
        """Liste pencereye sığmazsa kaydırma çubuğunu göster."""
        if getattr(self, "_fitting", False):
            return
        self._fitting = True
        try:
            self.root.update_idletasks()
            avail = self.canvas.winfo_height()
            h = self.body.winfo_reqheight()
            want = h > avail + 1
            if want != self.scrollable:
                self.scrollable = want
                if want:
                    self.sb.pack(side="right", fill="y")
                else:
                    self.sb.pack_forget()
                self.root.update_idletasks()
            w = self.canvas.winfo_width()
            self.canvas.itemconfigure(self.body_id, width=w)
            self.canvas.configure(scrollregion=(0, 0, w, max(h, avail)))
        finally:
            self._fitting = False

    def undo_done(self, d):
        self.done.discard(item_key(d))
        DONE_FILE.write_text(json.dumps(sorted(self.done), ensure_ascii=False))
        self.render(force=True)

    def restore_done(self):
        self.done.clear()
        DONE_FILE.write_text("[]")
        self.render(force=True)

    def update_title(self):
        n = getattr(self, "count", 0)
        urgent = getattr(self, "urgent", 0)
        txt = "Yaklaşan Deadline'lar"
        if self.collapsed:
            txt = f"{n} deadline" + (f" · {urgent} acil!" if urgent else "")
        self.title_lbl.config(text=txt, fg=RED if self.collapsed and urgent else INK)

    # ---- pencere --------------------------------------------------------
    def place_window(self):
        pos = read_json(WIN_FILE, {})
        self.w = max(MIN_W, int(pos.get("w", WIDTH)))
        self.h = max(MIN_H, int(pos.get("h", HEIGHT)))
        if "x" in pos:
            self.root.geometry(f"{self.w}x{self.h}+{pos['x']}+{pos['y']}")
        else:
            sw = self.root.winfo_screenwidth()
            self.root.geometry(f"{self.w}x{self.h}+{sw - self.w - 30}+60")

    def save_window(self):
        WIN_FILE.write_text(json.dumps({"x": self.root.winfo_x(), "y": self.root.winfo_y(),
                                        "w": self.w, "h": self.h}))

    def on_close(self):
        self.save_window()
        self.root.destroy()

    def icon_button(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=YELLOW, fg=MUTED, font=("Helvetica", 16), cursor="hand2")
        b.pack(side="right", padx=(0, 10))
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.config(fg=INK))
        b.bind("<Leave>", lambda e: b.config(fg=MUTED))
        return b


    # ---- veri -----------------------------------------------------------
    def refresh_mail(self, sites_now=False):
        self.footer.config(text="Mailler taranıyor…")
        cmd = [sys.executable, str(BASE / "deadline_reminder.py")] + (["--sites-now"] if sites_now else [])
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE)

    def add_site(self):
        """Mac'in kendi diyalog penceresiyle link sor, data/sites.txt'ye ekle, hemen kontrol et."""
        script = ('text returned of (display dialog "Dersin web sitesinin linkini yapıştır:" '
                  'default answer "https://" with title "Deadline Hatırlatıcı")')
        try:
            out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return
        url = out.stdout.strip()
        if out.returncode != 0 or not url.startswith(("http://", "https://")) or url in ("http://", "https://"):
            return
        existing = SITES_FILE.read_text() if SITES_FILE.exists() else ""
        if url not in existing.split():
            with open(SITES_FILE, "a") as f:
                f.write(("" if existing.endswith("\n") or not existing else "\n") + url + "\n")
        self.footer.config(text="Ders sitesi okunuyor…")
        self.refresh_mail(sites_now=True)

    def edit_sites(self):
        if not SITES_FILE.exists():
            SITES_FILE.write_text("# Takip edilen ders siteleri: her satıra bir link. Silmek için satırı sil.\n")
        subprocess.Popen(["open", "-e", str(SITES_FILE)])

    def mark_done(self, d):
        self.done.add(item_key(d))
        DONE_FILE.write_text(json.dumps(sorted(self.done), ensure_ascii=False))
        self.render(force=True)

    def open_mail(self, d):
        mid = d.get("mail_id")
        if not mid:
            return
        if str(mid).startswith("site:"):   # web sitesinden gelen deadline: sayfayı tarayıcıda aç
            subprocess.Popen(["open", str(mid)[5:]])
            return
        script = (f'const M=Application("Mail"); const m=M.inbox.messages.whose({{id:{int(mid)}}});'
                  f' if (m.length) {{ m[0].open(); M.activate(); }}')
        subprocess.Popen(["osascript", "-l", "JavaScript", "-e", script])

    def tick(self):
        self.render()
        pin_to_desktop()
        self.root.after(REFRESH_MS, self.tick)

    # ---- çizim ----------------------------------------------------------
    def render(self, force=False):
        mtime = OUT_FILE.stat().st_mtime if OUT_FILE.exists() else None
        today = dt.date.today()
        if not force and mtime == self.last_mtime and getattr(self, "_drawn_day", None) == today:
            return
        self.last_mtime, self._drawn_day = mtime, today

        for w in self.body.winfo_children():
            w.destroy()

        data = read_json(OUT_FILE, None)
        if data is None:
            log = DATA / "reminder.log"
            last = log.read_text().strip().splitlines()[-1] if log.exists() and log.stat().st_size else ""
            if "girişi yok" in last or "API anahtarı" in last:
                self.empty("Claude girişi yapılmamış.\nTerminalde: claude auth login")
            else:
                self.empty("İlk tarama sürüyor…\nBirkaç dakika içinde burada görünecek.")
            self.footer.config(text="sağ tık: menü")
            self.fit_list()
            return

        items, finished = [], []
        for d in data.get("items", []):
            day = dt.date.fromisoformat(d["deadline_date"])
            if day < today:
                continue
            (finished if item_key(d) in self.done else items).append((day, d))

        if not items:
            self.empty("Hepsi tamam 🎉" if finished else "Önümüzdeki 30 günde deadline yok 🎉")
        for day, d in items:
            self.row(day, d, (day - today).days)
        if finished:
            sep = tk.Frame(self.body, bg=YELLOW)
            sep.pack(fill="x", pady=(14, 2))
            tk.Frame(sep, bg=LINE, height=1).pack(fill="x", pady=(0, 6))
            tk.Label(sep, text=f"Tamamlananlar ({len(finished)})", bg=YELLOW, fg=MUTED,
                     font=("Helvetica", 11, "bold"), anchor="w").pack(fill="x")
            self.make_draggable(sep)
            for day, d in finished:
                self.done_row(day, d)
        self.count = len(items)
        self.urgent = sum(1 for day, _ in items if (day - today).days <= 3)
        self.update_title()

        upd = data.get("updated", "")[11:16]
        self.footer.config(text=f"Son tarama {upd}  ·  çift tık: kaynağı aç  ·  sağ tık: menü")
        self.fit_list()

    def empty(self, text):
        tk.Label(self.body, text=text, bg=YELLOW, fg=MUTED, font=("Helvetica", 13),
                 justify="center").pack(pady=18)

    def done_row(self, day, d):
        f = tk.Frame(self.body, bg=YELLOW)
        f.pack(fill="x", pady=2)
        undo = tk.Label(f, text="↺", bg=YELLOW, fg=MUTED, font=("Helvetica", 14), cursor="hand2")
        undo.pack(side="right", anchor="n")
        undo.bind("<Button-1>", lambda e, d=d: self.undo_done(d))
        undo.bind("<Enter>", lambda e: undo.config(fg=INK))
        undo.bind("<Leave>", lambda e: undo.config(fg=MUTED))
        txt = f"✓ {d['title']}  ·  {day.day} {TR_MONTHS[day.month - 1]}"
        lbl = tk.Label(f, text=txt, bg=YELLOW, fg=MUTED, font=("Helvetica", 12, "overstrike"),
                       wraplength=self.w - 80, justify="left", anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        for w in (f, lbl):
            self.make_draggable(w)
            w.bind("<Double-Button-1>", lambda e, d=d: self.open_mail(d))

    def row(self, day, d, left):
        color = RED if left <= 3 else ORANGE if left <= 7 else GREEN
        when = "BUGÜN" if left == 0 else "YARIN" if left == 1 else f"{left} gün"

        f = tk.Frame(self.body, bg=YELLOW)
        f.pack(fill="x", pady=4)

        tk.Label(f, text=when, bg=color, fg="white", font=("Helvetica", 11, "bold"),
                 width=6, padx=2).pack(side="left", anchor="n", pady=2)

        mid = tk.Frame(f, bg=YELLOW)
        mid.pack(side="left", fill="x", expand=True, padx=8)
        title = tk.Label(mid, text=d["title"], bg=YELLOW, fg=INK, font=("Helvetica", 13, "bold"),
                         wraplength=self.w - 145, justify="left", anchor="w")
        title.pack(fill="x")
        date_txt = f"{day.day} {TR_MONTHS[day.month - 1]} {TR_DAYS[day.weekday()]}"
        if d.get("deadline_time"):
            date_txt += f" · {d['deadline_time']}"
        if d.get("source"):
            date_txt += f"  —  {d['source']}"
        sub = tk.Label(mid, text=date_txt, bg=YELLOW, fg=MUTED, font=("Helvetica", 11),
                       wraplength=self.w - 145, justify="left", anchor="w")
        sub.pack(fill="x")

        chk = tk.Label(f, text="✓", bg=YELLOW, fg=MUTED, font=("Helvetica", 16), cursor="hand2")
        chk.pack(side="right", anchor="n")
        chk.bind("<Button-1>", lambda e, d=d: self.mark_done(d))
        chk.bind("<Enter>", lambda e: chk.config(fg=GREEN))
        chk.bind("<Leave>", lambda e: chk.config(fg=MUTED))

        for w in (f, mid, title, sub):
            self.make_draggable(w)
            w.bind("<Double-Button-1>", lambda e, d=d: self.open_mail(d))


def main():
    DATA.mkdir(exist_ok=True)
    root = tk.Tk()
    hide_dock_icon()
    PostIt(root)
    root.mainloop()


if __name__ == "__main__":
    main()
