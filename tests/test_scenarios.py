"""Chuqur ssenariylar: soxta soat bilan eslatmalar, buzilgan baza, fayl yig'ishni bekor qilish."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from hujjat_cheklisti import logic  # noqa: E402
from hujjat_cheklisti.db import DB  # noqa: E402


def test_reminders_over_a_simulated_month(tmp_path):
    """Muddatdan 10 kun oldindan 5 kun keyingacha har kuni tekshiramiz: har chegara bir marta."""
    deadline = date(2026, 12, 20)
    entries = [("p1", "Magistratura", deadline)]
    notified, log = set(), []
    for k in range(-10, 6):
        today = deadline + timedelta(days=k)
        for _ in range(3):                     # kuniga bir necha marta tekshiriladi (har daqiqa)
            for key, title, dl in logic.due_notifications(entries, today, [7, 3, 1, 0], notified):
                notified.add(key)
                log.append((today, dl, key.rsplit(":", 1)[1]))
    assert [(d.day, dl, tag) for d, dl, tag in log] == [
        (13, 7, "d7"), (17, 3, "d3"), (19, 1, "d1"), (20, 0, "d0"), (21, -1, "over")]


def test_moved_deadline_reminds_again():
    notified = set()
    first = logic.due_notifications([("p1", "A", date(2026, 1, 10))], date(2026, 1, 9), [1], notified)
    notified |= {k for k, _, _ in first}
    again = logic.due_notifications([("p1", "A", date(2026, 1, 12))], date(2026, 1, 11), [1], notified)
    assert len(first) == 1 and len(again) == 1


def test_corrupt_database_is_backed_up(tmp_path):
    f = tmp_path / "cheklist.db"
    f.write_bytes(b"this is not sqlite" * 100)
    db = DB(f)
    assert db.broken_backup is not None and db.broken_backup.exists()
    db.seed_builtin("uz")
    assert db.templates()
    db.close()


def test_copy_cancel_midway_and_unicode(tmp_path):
    src = tmp_path / "manba папка"
    src.mkdir()
    items = []
    for i in range(5):
        f = src / f"hujjat {i} ўзбек.pdf"
        f.write_bytes(b"%PDF" + bytes([i]) * 1000)
        items.append({"name": f"Pasport: nusxa/{i}?", "file_path": str(f)})
    items.append({"name": "Yo'q fayl", "file_path": str(src / "yoq.pdf")})
    items.append({"name": "Biriktirilmagan", "file_path": ""})

    class Cb:
        calls = 0

        def __call__(self, pct, msg=""):
            Cb.calls += 1

        def cancelled(self):
            return Cb.calls >= 2

    copied, missing = logic.copy_package_files(items, str(tmp_path / "out"), Cb())
    assert len(copied) == 2 and missing == []
    assert all(Path(c).name.startswith(("01_Pasport_ nusxa_0_", "02_Pasport_ nusxa_1_")) for c in copied)
    copied, missing = logic.copy_package_files(items, str(tmp_path / "out"))
    assert len(copied) == 5 and missing == ["Yo'q fayl"]
    assert len(list((tmp_path / "out").iterdir())) == 7          # ustiga yozilmadi
    assert all((src / f"hujjat {i} ўзбек.pdf").exists() for i in range(5))


# ----------------------------------------------------------------------------- interfeys + soxta soat
class _FakeDate(date):
    now = date(2026, 12, 13)

    @classmethod
    def today(cls):
        return cls.now


@pytest.fixture
def win(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    from PySide6.QtWidgets import QApplication
    from uzkit import app as appmod
    from uzkit.settings import Settings
    appmod.META = appmod.load_meta()
    appmod.SETTINGS = Settings(appmod.META["slug"] + "_scn")
    QApplication.instance() or QApplication([])
    from hujjat_cheklisti import ui_extra, window as wmod
    monkeypatch.setattr(ui_extra, "_DEMO_DIRS", {})
    monkeypatch.setattr(ui_extra, "set_autostart", lambda *a, **k: pytest.fail("autostart must not be touched"))
    monkeypatch.setattr(wmod, "set_autostart", lambda *a, **k: pytest.fail("autostart must not be touched"))
    monkeypatch.setattr(wmod, "date", _FakeDate)
    w = wmod.MainWindow()
    sent = []
    monkeypatch.setattr(w.tray, "notify", lambda title, text, ms=0: sent.append(text))
    w.sent = sent
    yield w
    w.tray.quitting = True
    w.db.close()
    w.close()


def test_ui_reminders_with_mocked_clock(win):
    db = win.db
    pid = db.add_package("Magistratura hujjatlari", "", date(2026, 12, 20), "", "", ["Pasport", "Diplom"])
    other = db.add_package("Tayyor paket", "", date(2026, 12, 14), "", "", ["A"])
    for it in db.items(other):
        db.update_item(it["id"], status="ready")            # 100% — eslatma kerak emas
    iid = db.items(pid)[1]["id"]
    db.update_item(iid, due=date(2026, 12, 14))
    _FakeDate.now = date(2026, 12, 13)
    win.check_reminders()
    assert len(win.sent) == 1
    assert "Magistratura hujjatlari" in win.sent[0] and "Diplom (Magistratura hujjatlari)" in win.sent[0]
    win.check_reminders()                                     # bir daqiqadan keyin: takror yo'q
    assert len(win.sent) == 1
    db.update_item(iid, status="ready")
    _FakeDate.now = date(2026, 12, 17)
    win.check_reminders()
    assert len(win.sent) == 2 and "Diplom" not in win.sent[1]
    _FakeDate.now = date(2026, 12, 25)                        # muddat 5 kun o'tgan: eski, eslatilmaydi
    win.check_reminders()
    assert len(win.sent) == 2


def test_ui_bad_threshold_setting(win):
    win.settings.set("thresholds", ["x", 3, -1, True, 7])
    assert win.thresholds() == [3, 7]
    win.settings.set("thresholds", "7,3")
    assert win.thresholds() == [7, 3, 1, 0]
    win.check_reminders()
