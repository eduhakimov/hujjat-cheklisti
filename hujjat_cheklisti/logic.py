"""Interfeysdan mustaqil mantiq: progress, muddatlar, eslatmalar, fayllarni yig'ish."""
import os
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from .db import DONE_STATUSES, parse_date

STATUS_COLORS = {"need": "#dc2626", "progress": "#d97706", "ready": "#16a34a", "submitted": "#2563eb"}


def progress(statuses: Iterable[str]) -> float:
    """Tayyor yoki topshirilgan hujjatlar ulushi (0..1)."""
    st = list(statuses)
    if not st:
        return 0.0
    return sum(1 for s in st if s in DONE_STATUSES) / len(st)


def counts(statuses: Iterable[str]) -> dict:
    out = {"need": 0, "progress": 0, "ready": 0, "submitted": 0}
    for s in statuses:
        if s in out:
            out[s] += 1
    return out


def days_left(deadline, today: date = None) -> Optional[int]:
    d = parse_date(deadline)
    if d is None:
        return None
    return (d - (today or date.today())).days


def urgency_color(dl: Optional[int], complete: bool = False) -> str:
    if complete:
        return "#16a34a"
    if dl is None:
        return "#64748b"
    if dl < 0:
        return "#dc2626"
    if dl <= 3:
        return "#dc2626"
    if dl <= 14:
        return "#d97706"
    return "#16a34a"


def due_notifications(entries: Sequence[Tuple[str, str, object]], today: date, thresholds: Sequence[int],
                      notified: set) -> List[Tuple[str, str, int]]:
    """Qaysi eslatmalarni hozir ko'rsatish kerak.

    entries: (kalit_prefiksi, sarlavha, sana). Har bir sana uchun eng yaqin chegaraga (masalan 7, 3, 1, 0 kun)
    yetganda bitta eslatma; muddat o'tgan bo'lsa — bitta "overdue" eslatma. Takrorlanmaydi (notified).
    Natija: [(kalit, sarlavha, qolgan_kunlar)].
    """
    th = sorted({int(t) for t in thresholds if int(t) >= 0})
    out = []
    for prefix, title, d in entries:
        dd = parse_date(d)
        if dd is None:
            continue
        dl = (dd - today).days
        if dl < 0:
            if dl < -3:          # juda eski muddatlar haqida eslatmaymiz
                continue
            tag = "over"
        else:
            cands = [t for t in th if t >= dl]
            if not cands:
                continue
            tag = f"d{min(cands)}"
        key = f"{prefix}:{dd.isoformat()}:{tag}"
        if key not in notified:
            out.append((key, title, dl))
    return out


_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, max_len: int = 80) -> str:
    s = _BAD.sub("_", name).strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    s = s[:max_len].rstrip(" .")
    return s or "hujjat"


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    i = 2
    while True:
        cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not cand.exists():
            return cand
        i += 1


def copy_package_files(items: Sequence[dict], dest: str, progress_cb: Callable = None,
                       numbered: bool = True) -> Tuple[List[str], List[str]]:
    """Paket hujjatlariga biriktirilgan fayllarni bitta papkaga nusxalaydi.

    items: [{"name":..., "file_path":...}]. Mavjud fayllar ustiga yozilmaydi (yangi nom beriladi).
    Natija: (nusxalangan_yo'llar, topilmagan_hujjat_nomlari).
    """
    dest_p = Path(dest)
    dest_p.mkdir(parents=True, exist_ok=True)
    attached = [it for it in items if (it.get("file_path") or "").strip()]
    copied, missing = [], []
    n = len(attached)
    for k, it in enumerate(attached, 1):
        if progress_cb is not None and getattr(progress_cb, "cancelled", None) and progress_cb.cancelled():
            break
        src = Path(it["file_path"])
        if not src.is_file():
            missing.append(it["name"])
            continue
        base = safe_filename(it["name"])
        stem = f"{k:02d}_{base}" if numbered else base
        target = unique_path(dest_p / f"{stem}{src.suffix.lower()}")
        shutil.copy2(src, target)
        copied.append(str(target))
        if progress_cb is not None:
            progress_cb(int(k * 100 / max(n, 1)), src.name)
    return copied, missing


def fmt_date(d) -> str:
    dd = parse_date(d)
    return dd.strftime("%d.%m.%Y") if dd else ""


def file_exists(p: str) -> bool:
    return bool(p) and os.path.isfile(p)
