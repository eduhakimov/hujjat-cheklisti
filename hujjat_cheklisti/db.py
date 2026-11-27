"""SQLite ma'lumotlar bazasi: shablonlar, paketlar, hujjatlar, eslatmalar jurnali."""
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from .templates import BUILTIN_TEMPLATES

STATUSES = ["need", "progress", "ready", "submitted"]   # kerak / tayyorlanmoqda / tayyor / topshirildi
DONE_STATUSES = ("ready", "submitted")

SCHEMA = """
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT,
    name TEXT NOT NULL,
    builtin INTEGER DEFAULT 0,
    pos INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS template_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    pos INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    kind TEXT DEFAULT '',
    deadline TEXT,
    org TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    archived INTEGER DEFAULT 0,
    created TEXT
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'need',
    file_path TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    due TEXT,
    pos INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notified (
    key TEXT PRIMARY KEY,
    ts TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


def iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def parse_date(s) -> Optional[date]:
    if not s:
        return None
    if isinstance(s, date):
        return s
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


class DB:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._open()
        except sqlite3.DatabaseError:
            # Buzilgan baza fayli: zaxiraga olib, yangisini ochamiz (dastur ishga tushmay qolmasin)
            try:
                self.con.close()
            except Exception:
                pass
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.broken_backup = self.path.with_name(f"{self.path.stem}.broken_{stamp}{self.path.suffix}")
            self.path.replace(self.broken_backup)
            self._open()

    broken_backup = None

    def _open(self):
        self.con = sqlite3.connect(str(self.path))
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(SCHEMA)
        self.con.commit()

    def close(self):
        self.con.close()

    # ------------------------------------------------------------------ meta
    def get_meta(self, k, default=None):
        r = self.con.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else default

    def set_meta(self, k, v):
        self.con.execute("INSERT OR REPLACE INTO meta(k, v) VALUES(?, ?)", (k, str(v)))
        self.con.commit()

    # ------------------------------------------------------------------ shablonlar
    def seed_builtin(self, lang: str = "uz", force: bool = False):
        """O'rnatilgan shablonlarni qo'shadi (birinchi ishga tushirishda yoki 'tiklash'da)."""
        if self.get_meta("seeded") and not force:
            return
        for pos, (key, t) in enumerate(BUILTIN_TEMPLATES.items()):
            if force:
                old = self.con.execute("SELECT id FROM templates WHERE key=?", (key,)).fetchall()
                for r in old:
                    self.con.execute("DELETE FROM templates WHERE id=?", (r["id"],))
            cur = self.con.execute("INSERT INTO templates(key, name, builtin, pos) VALUES(?,?,1,?)",
                                   (key, t["name"].get(lang) or t["name"]["uz"], pos))
            tid = cur.lastrowid
            for i, it in enumerate(t["items"]):
                self.con.execute("INSERT INTO template_items(template_id, name, pos) VALUES(?,?,?)",
                                 (tid, it.get(lang) or it["uz"], i))
        self.set_meta("seeded", "1")
        self.con.commit()

    def templates(self) -> List[sqlite3.Row]:
        return self.con.execute("SELECT * FROM templates ORDER BY pos, id").fetchall()

    def template_items(self, tid: int) -> List[str]:
        return [r["name"] for r in self.con.execute(
            "SELECT name FROM template_items WHERE template_id=? ORDER BY pos, id", (tid,))]

    def add_template(self, name: str, items: List[str] = None) -> int:
        pos = (self.con.execute("SELECT COALESCE(MAX(pos), 0) + 1 FROM templates").fetchone()[0])
        cur = self.con.execute("INSERT INTO templates(key, name, builtin, pos) VALUES(NULL, ?, 0, ?)", (name, pos))
        tid = cur.lastrowid
        self.set_template_items(tid, items or [])
        return tid

    def rename_template(self, tid: int, name: str):
        self.con.execute("UPDATE templates SET name=? WHERE id=?", (name, tid))
        self.con.commit()

    def delete_template(self, tid: int):
        self.con.execute("DELETE FROM templates WHERE id=?", (tid,))
        self.con.commit()

    def set_template_items(self, tid: int, items: List[str]):
        self.con.execute("DELETE FROM template_items WHERE template_id=?", (tid,))
        for i, n in enumerate([x.strip() for x in items if x.strip()]):
            self.con.execute("INSERT INTO template_items(template_id, name, pos) VALUES(?,?,?)", (tid, n, i))
        self.con.commit()

    # ------------------------------------------------------------------ paketlar
    def add_package(self, title: str, kind: str = "", deadline=None, org: str = "", notes: str = "",
                    items: List[str] = None) -> int:
        cur = self.con.execute(
            "INSERT INTO packages(title, kind, deadline, org, notes, created) VALUES(?,?,?,?,?,?)",
            (title, kind, iso(parse_date(deadline)), org, notes, datetime.now().isoformat(timespec="seconds")))
        pid = cur.lastrowid
        for i, n in enumerate(items or []):
            self.con.execute("INSERT INTO items(package_id, name, pos) VALUES(?,?,?)", (pid, n, i))
        self.con.commit()
        return pid

    def update_package(self, pid: int, **kw):
        allowed = {"title", "kind", "deadline", "org", "notes", "archived"}
        sets = {k: v for k, v in kw.items() if k in allowed}
        if "deadline" in sets:
            sets["deadline"] = iso(parse_date(sets["deadline"]))
        if not sets:
            return
        q = ", ".join(f"{k}=?" for k in sets)
        self.con.execute(f"UPDATE packages SET {q} WHERE id=?", (*sets.values(), pid))
        self.con.commit()

    def delete_package(self, pid: int):
        self.con.execute("DELETE FROM packages WHERE id=?", (pid,))
        self.con.commit()

    def packages(self, include_archived: bool = False) -> List[sqlite3.Row]:
        q = "SELECT * FROM packages"
        if not include_archived:
            q += " WHERE archived=0"
        q += " ORDER BY (deadline IS NULL), deadline, id"
        return self.con.execute(q).fetchall()

    def package(self, pid: int) -> Optional[sqlite3.Row]:
        return self.con.execute("SELECT * FROM packages WHERE id=?", (pid,)).fetchone()

    # ------------------------------------------------------------------ hujjatlar
    def items(self, pid: int) -> List[sqlite3.Row]:
        return self.con.execute("SELECT * FROM items WHERE package_id=? ORDER BY pos, id", (pid,)).fetchall()

    def item(self, iid: int) -> Optional[sqlite3.Row]:
        return self.con.execute("SELECT * FROM items WHERE id=?", (iid,)).fetchone()

    def add_item(self, pid: int, name: str, status: str = "need", file_path: str = "", notes: str = "",
                 due=None) -> int:
        pos = self.con.execute("SELECT COALESCE(MAX(pos), -1) + 1 FROM items WHERE package_id=?", (pid,)).fetchone()[0]
        cur = self.con.execute(
            "INSERT INTO items(package_id, name, status, file_path, notes, due, pos) VALUES(?,?,?,?,?,?,?)",
            (pid, name, status if status in STATUSES else "need", file_path or "", notes or "",
             iso(parse_date(due)), pos))
        self.con.commit()
        return cur.lastrowid

    def update_item(self, iid: int, **kw):
        allowed = {"name", "status", "file_path", "notes", "due"}
        sets = {k: v for k, v in kw.items() if k in allowed}
        if "due" in sets:
            sets["due"] = iso(parse_date(sets["due"]))
        if "status" in sets and sets["status"] not in STATUSES:
            raise ValueError(sets["status"])
        if not sets:
            return
        q = ", ".join(f"{k}=?" for k in sets)
        self.con.execute(f"UPDATE items SET {q} WHERE id=?", (*sets.values(), iid))
        self.con.commit()

    def delete_item(self, iid: int):
        self.con.execute("DELETE FROM items WHERE id=?", (iid,))
        self.con.commit()

    def move_item(self, iid: int, delta: int):
        it = self.item(iid)
        if not it:
            return
        rows = [r["id"] for r in self.items(it["package_id"])]
        i = rows.index(iid)
        j = i + delta
        if 0 <= j < len(rows):
            rows[i], rows[j] = rows[j], rows[i]
            for pos, rid in enumerate(rows):
                self.con.execute("UPDATE items SET pos=? WHERE id=?", (pos, rid))
            self.con.commit()

    def all_open_items_with_due(self) -> List[sqlite3.Row]:
        return self.con.execute(
            "SELECT items.*, packages.title AS package_title FROM items JOIN packages ON packages.id=items.package_id "
            "WHERE items.due IS NOT NULL AND items.status NOT IN ('ready','submitted') AND packages.archived=0"
        ).fetchall()

    # ------------------------------------------------------------------ eslatmalar
    def notified_keys(self) -> set:
        return {r["key"] for r in self.con.execute("SELECT key FROM notified")}

    def mark_notified(self, key: str):
        self.con.execute("INSERT OR IGNORE INTO notified(key, ts) VALUES(?, ?)",
                         (key, datetime.now().isoformat(timespec="seconds")))
        self.con.commit()
