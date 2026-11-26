import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from hujjat_cheklisti import logic
from hujjat_cheklisti.db import DB
from hujjat_cheklisti.templates import BUILTIN_TEMPLATES


def make_db():
    d = tempfile.mkdtemp()
    return DB(Path(d) / "t.db")


def test_templates_complete():
    assert len(BUILTIN_TEMPLATES) == 5
    for t in BUILTIN_TEMPLATES.values():
        assert all(t["name"][l] for l in ("uz", "ru", "en"))
        assert len(t["items"]) >= 8
        for it in t["items"]:
            assert all(it[l] for l in ("uz", "ru", "en"))


def test_seed_and_package():
    db = make_db()
    db.seed_builtin("ru")
    db.seed_builtin("ru")  # takror qo'shmaydi
    assert len(db.templates()) == 5
    tid = db.templates()[0]["id"]
    names = db.template_items(tid)
    assert names[0].startswith("Заявление")
    pid = db.add_package("Test", "k", date(2026, 12, 1), items=names)
    assert len(db.items(pid)) == len(names)
    db.seed_builtin("uz", force=True)
    assert len(db.templates()) == 5


def test_user_template_and_move():
    db = make_db()
    tid = db.add_template("Mine", ["a", " ", "b", "c"])
    assert db.template_items(tid) == ["a", "b", "c"]
    pid = db.add_package("P", items=["x", "y", "z"])
    ids = [r["id"] for r in db.items(pid)]
    db.move_item(ids[2], -1)
    assert [r["name"] for r in db.items(pid)] == ["x", "z", "y"]
    db.update_item(ids[0], status="ready")
    assert db.item(ids[0])["status"] == "ready"
    db.delete_package(pid)
    assert db.items(pid) == []


def test_progress_and_counts():
    assert logic.progress([]) == 0
    assert logic.progress(["need", "ready", "submitted", "progress"]) == 0.5
    assert logic.counts(["need", "need", "ready"])["need"] == 2


def test_days_left():
    t = date(2026, 1, 10)
    assert logic.days_left("2026-01-15", t) == 5
    assert logic.days_left(None, t) is None
    assert logic.days_left("2026-01-08", t) == -2


def test_due_notifications():
    t = date(2026, 3, 1)
    entries = [("p1", "A", t + timedelta(days=5)), ("p2", "B", t + timedelta(days=1)),
               ("p3", "C", t + timedelta(days=20)), ("p4", "D", t - timedelta(days=1)),
               ("p5", "E", t - timedelta(days=30)), ("p6", "F", t)]
    out = logic.due_notifications(entries, t, [7, 3, 1, 0], set())
    keys = {k for k, _, _ in out}
    assert "p1:2026-03-06:d7" in keys
    assert "p2:2026-03-02:d1" in keys
    assert "p4:2026-02-28:over" in keys
    assert "p6:2026-03-01:d0" in keys
    assert not any(k.startswith("p3") or k.startswith("p5") for k in keys)
    assert logic.due_notifications(entries, t, [7, 3, 1, 0], keys) == []
    later = logic.due_notifications(entries, t + timedelta(days=3), [7, 3, 1, 0], keys)
    assert any(k == "p1:2026-03-06:d3" for k, _, _ in later)


def test_safe_filename():
    assert logic.safe_filename('a/b:c*?"d') == "a_b_c___d"
    assert logic.safe_filename("   ") == "hujjat"


def test_copy_package_files():
    src = Path(tempfile.mkdtemp())
    dst = Path(tempfile.mkdtemp()) / "out"
    (src / "a.PDF").write_text("1")
    (src / "b.docx").write_text("2")
    items = [{"name": "Ariza", "file_path": str(src / "a.PDF")},
             {"name": "CV/rezyume", "file_path": str(src / "b.docx")},
             {"name": "Yo'q", "file_path": str(src / "none.pdf")},
             {"name": "Bo'sh", "file_path": ""}]
    copied, missing = logic.copy_package_files(items, str(dst))
    assert sorted(Path(p).name for p in copied) == ["01_Ariza.pdf", "02_CV_rezyume.docx"]
    assert missing == ["Yo'q"]
    copied2, _ = logic.copy_package_files(items, str(dst))
    assert "01_Ariza (2).pdf" in [Path(p).name for p in copied2]
    assert (src / "a.PDF").exists()


def test_exports():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from hujjat_cheklisti import window
    db = make_db()
    db.seed_builtin("uz")
    pid = db.add_package("Test <&>", "k", date(2026, 12, 1), items=["Ariza", "CV"])
    out = Path(tempfile.mkdtemp())
    window.export_xlsx(db, pid, str(out / "a.xlsx"))
    assert (out / "a.xlsx").stat().st_size > 1000
    from hujjat_cheklisti.ui_extra import html_to_pdf
    html_to_pdf(str(out / "a.pdf"), window.build_pdf_html(db, pid))
    assert (out / "a.pdf").read_bytes()[:4] == b"%PDF"


class _FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeReg:
    HKEY_CURRENT_USER = 1
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.vals = {}

    def OpenKey(self, *a):
        return _FakeKey()

    def SetValueEx(self, k, n, r, t, v):
        self.vals[n] = v

    def DeleteValue(self, k, n):
        del self.vals[n]

    def QueryValueEx(self, k, n):
        return (self.vals[n], 1)


def test_autostart_mock():
    from hujjat_cheklisti import ui_extra
    r = FakeReg()
    assert ui_extra.set_autostart("X", True, '"a.exe" --tray', r)
    assert ui_extra.is_autostart("X", r)
    assert ui_extra.set_autostart("X", False, "", r)
    assert not ui_extra.is_autostart("X", r)


def test_ui_flows():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from uzkit import app as appmod
    from uzkit.settings import Settings
    appmod.META = appmod.load_meta()
    appmod.SETTINGS = Settings(appmod.META["slug"] + "_test")
    from hujjat_cheklisti import window
    w = window.MainWindow()
    pid = window.load_demo(w.db, w.db.path.parent)
    w.data_changed()
    w.open_package(pid)
    w.packages.table.selectRow(2)
    w.packages.set_status("submitted")
    assert w.db.items(pid)[2]["status"] == "submitted"
    w.packages.move(1)
    window.PackageDialog(w).close()
    window.ItemDialog(w, w.db.items(pid)[0]).close()
    w.check_reminders()
    for i in range(4):
        w.set_page(i)
    w.close()
