"""Asosiy oyna: umumiy ko'rinish, paketlar, shablonlar, sozlamalar."""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QStyle, QStyleOptionViewItem, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QPlainTextEdit, QProgressDialog,
                               QPushButton, QScrollArea, QSizePolicy, QStyledItemDelegate, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from uzkit import app as appmod
from uzkit.i18n import language, register, tr
from uzkit.paths import resource
from uzkit.widgets import (Card, PathPicker, Worker, ask, danger_button, error, header, info, open_path,
                           primary_button, reveal_in_explorer, run_worker, warn)
from uzkit.window import BaseMainWindow

from . import logic
from .db import DB, DONE_STATUSES, STATUSES, parse_date
from .strings import STRINGS
from .ui_extra import (ProgressRing, icon, Tray, app_data_dir, autostart_command, esc, html_to_pdf, is_autostart,
                       is_demo, pal, set_autostart, soft, write_xlsx)

register(STRINGS)

SLUG = "hujjat-cheklisti"
AUTOSTART_NAME = "BahtiyorSoft.HujjatCheklisti"


def status_name(s: str) -> str:
    return tr(f"st_{s}")


def days_text(dl) -> str:
    if dl is None:
        return tr("no_deadline")
    if dl < 0:
        return tr("overdue_n", n=-dl)
    if dl == 0:
        return tr("today")
    return tr("days_left_n", n=dl)


# =========================================================================== kichik vidjetlar
class Badge(QLabel):
    def __init__(self, text="", color="#64748b"):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.set(text, color)

    def set(self, text, color):
        self.setText(text)
        bg = soft(color, 0.85).name()
        self.setStyleSheet(f"QLabel {{ background: {bg}; color: {color}; border-radius: 9px; padding: 2px 9px;"
                           f" font-weight: 600; font-size: 9pt; }}")


class StatCard(QFrame):
    def __init__(self, title: str, color: str):
        super().__init__()
        self.setObjectName("Card")
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 12, 16, 12)
        l.setSpacing(2)
        self.value = QLabel("0")
        f = self.value.font()
        f.setPointSize(19)
        f.setBold(True)
        self.value.setFont(f)
        self.value.setStyleSheet(f"color: {color}; font-size: 20pt; font-weight: 700;")
        t = QLabel(title)
        t.setObjectName("Muted")
        t.setWordWrap(True)
        l.addWidget(self.value)
        l.addWidget(t)


class StatusDelegate(QStyledItemDelegate):
    """Holat ustunida rangli "chip"."""

    def paint(self, p, opt, idx):
        st = idx.data(Qt.UserRole)
        if not st:
            return super().paint(p, opt, idx)
        o = QStyleOptionViewItem(opt)
        self.initStyleOption(o, idx)
        o.text = ""
        style = o.widget.style() if o.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, o, p, o.widget)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        color = logic.STATUS_COLORS.get(st, "#64748b")
        text = status_name(st)
        f = QFont(opt.font)
        f.setBold(True)
        f.setPointSizeF(8.8)
        p.setFont(f)
        fm = p.fontMetrics()
        w = min(fm.horizontalAdvance(text) + 30, opt.rect.width() - 8)
        r = QRectF(opt.rect.left() + 6, opt.rect.center().y() - 11, w, 22)
        p.setPen(Qt.NoPen)
        p.setBrush(soft(color, 0.84))
        p.drawRoundedRect(r, 11, 11)
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(r.left() + 8, r.center().y() - 3, 6, 6))
        p.setPen(QColor(color))
        p.drawText(r.adjusted(18, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(text, Qt.ElideRight, int(r.width() - 24)))
        p.restore()


class ItemTable(QTableWidget):
    """Hujjatlar jadvali: faylni qatorga sudrab tashlash mumkin."""
    file_dropped = Signal(int, str)   # qator, yo'l

    def __init__(self):
        super().__init__(0, 6)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            row = self.rowAt(int(e.position().y()))
            if row >= 0:
                self.selectRow(row)
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        row = self.rowAt(int(e.position().y()))
        if urls and row >= 0 and os.path.isfile(urls[0]):
            self.file_dropped.emit(row, os.path.normpath(urls[0]))
            e.acceptProposedAction()


def icon_button(name: str, tip: str) -> QPushButton:
    b = QPushButton()
    b.setIcon(icon(name, pal()["text"]))
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    b.setFixedWidth(40)
    return b


class ElidedLabel(QLabel):
    """Sig'maganda uch nuqta bilan qisqartiriladigan yorliq."""

    def __init__(self, text=""):
        super().__init__()
        self._full = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, t):
        self._full = t
        self.setToolTip(t)
        self._apply()

    def _apply(self):
        fm = self.fontMetrics()
        super().setText(fm.elidedText(self._full, Qt.ElideRight, max(20, self.width())))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply()


# =========================================================================== dialoglar
class PackageDialog(QDialog):
    def __init__(self, win, pkg=None):
        super().__init__(win)
        self.win = win
        self.db: DB = win.db
        self.setWindowTitle(tr("edit_package") if pkg else tr("new_package"))
        self.setMinimumWidth(520)
        l = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        self.title = QLineEdit()
        self.title.setPlaceholderText(tr("title_ph"))
        self.tpl = QComboBox()
        self.tpl.addItem(tr("empty_template"), None)
        for t in self.db.templates():
            self.tpl.addItem(t["name"], t["id"])
        self.has_dl = QCheckBox(tr("has_deadline"))
        self.has_dl.setChecked(True)
        self.deadline = QDateEdit()
        self.deadline.setCalendarPopup(True)
        self.deadline.setDisplayFormat("dd.MM.yyyy")
        self.deadline.setDate(QDate.currentDate().addDays(30))
        dl_row = QHBoxLayout()
        dl_row.addWidget(self.deadline, 1)
        dl_row.addWidget(self.has_dl)
        self.org = QLineEdit()
        self.org.setPlaceholderText(tr("org_ph"))
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(64)
        form.addRow(tr("pkg_title"), self.title)
        if pkg is None:
            form.addRow(tr("template"), self.tpl)
        form.addRow(tr("deadline"), dl_row)
        form.addRow(tr("organization"), self.org)
        form.addRow(tr("notes"), self.notes)
        l.addLayout(form)
        self.items_list = QListWidget()
        self.items_list.setMinimumHeight(160)
        if pkg is None:
            lab = QLabel(tr("docs_from_template"))
            lab.setObjectName("Muted")
            l.addWidget(lab)
            l.addWidget(self.items_list, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("save"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        self.has_dl.toggled.connect(self.deadline.setEnabled)
        self.tpl.currentIndexChanged.connect(self._tpl_changed)
        if pkg is not None:
            self.title.setText(pkg["title"])
            d = parse_date(pkg["deadline"])
            self.has_dl.setChecked(d is not None)
            if d:
                self.deadline.setDate(QDate(d.year, d.month, d.day))
            self.org.setText(pkg["org"] or "")
            self.notes.setPlainText(pkg["notes"] or "")
            self.kind = pkg["kind"]
        else:
            self.kind = ""
            if self.tpl.count() > 1:
                self.tpl.setCurrentIndex(1)

    def preselect_template(self, tid):
        i = self.tpl.findData(tid)
        if i >= 0:
            self.tpl.setCurrentIndex(i)

    def _tpl_changed(self):
        tid = self.tpl.currentData()
        self.items_list.clear()
        if tid is None:
            return
        for n in self.db.template_items(tid):
            it = QListWidgetItem(n)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.items_list.addItem(it)
        if not self.title.text().strip() or getattr(self, "_auto_title", False):
            self.title.setText(f"{self.tpl.currentText()} {date.today().year}")
            self._auto_title = True

    def _ok(self):
        if not self.title.text().strip():
            warn(self, tr("need_title"))
            return
        self.accept()

    def values(self) -> dict:
        d = self.deadline.date()
        items = [self.items_list.item(i).text() for i in range(self.items_list.count())
                 if self.items_list.item(i).checkState() == Qt.Checked]
        return {
            "title": self.title.text().strip(),
            "kind": self.tpl.currentText() if self.tpl.currentData() is not None else self.kind,
            "deadline": date(d.year(), d.month(), d.day()) if self.has_dl.isChecked() else None,
            "org": self.org.text().strip(),
            "notes": self.notes.toPlainText().strip(),
            "items": items,
        }


class ItemDialog(QDialog):
    def __init__(self, parent, item=None):
        super().__init__(parent)
        self.setWindowTitle(tr("edit_doc") if item else tr("add_doc"))
        self.setMinimumWidth(520)
        l = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        self.name = QLineEdit()
        self.status = QComboBox()
        for s in STATUSES:
            self.status.addItem(status_name(s), s)
        self.has_due = QCheckBox(tr("has_due"))
        self.due = QDateEdit()
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat("dd.MM.yyyy")
        self.due.setDate(QDate.currentDate().addDays(7))
        self.due.setEnabled(False)
        self.has_due.toggled.connect(self.due.setEnabled)
        row = QHBoxLayout()
        row.addWidget(self.due, 1)
        row.addWidget(self.has_due)
        self.file = PathPicker("open", tr("all_files") + " (*.*)", tr("file_ph"))
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(70)
        form.addRow(tr("doc_name"), self.name)
        form.addRow(tr("status"), self.status)
        form.addRow(tr("due_date"), row)
        form.addRow(tr("file"), self.file)
        form.addRow(tr("notes"), self.notes)
        l.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("save"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        if item is not None:
            self.name.setText(item["name"])
            self.status.setCurrentIndex(max(0, self.status.findData(item["status"])))
            d = parse_date(item["due"])
            if d:
                self.has_due.setChecked(True)
                self.due.setDate(QDate(d.year, d.month, d.day))
            self.file.set_path(item["file_path"] or "")
            self.notes.setPlainText(item["notes"] or "")

    def _ok(self):
        if not self.name.text().strip():
            warn(self, tr("need_doc_name"))
            return
        self.accept()

    def values(self) -> dict:
        d = self.due.date()
        return {"name": self.name.text().strip(), "status": self.status.currentData(),
                "due": date(d.year(), d.month(), d.day()) if self.has_due.isChecked() else None,
                "file_path": self.file.path(), "notes": self.notes.toPlainText().strip()}


# =========================================================================== umumiy ko'rinish
class PackageTile(QFrame):
    clicked = Signal(int)

    def __init__(self, pkg, items):
        super().__init__()
        self.pid = pkg["id"]
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(118)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)
        sts = [i["status"] for i in items]
        pr = logic.progress(sts)
        dl = logic.days_left(pkg["deadline"])
        complete = bool(sts) and pr >= 1
        ring = ProgressRing(72, 8)
        ring.set_value(pr, logic.urgency_color(dl, complete) if dl is not None and dl <= 3 and not complete else None)
        h.addWidget(ring, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(4)
        t = QLabel(pkg["title"])
        t.setObjectName("SectionTitle")
        t.setWordWrap(True)
        col.addWidget(t)
        c = logic.counts(sts)
        sub = QLabel(tr("tile_counts", done=c["ready"] + c["submitted"], total=len(sts)))
        sub.setObjectName("Muted")
        col.addWidget(sub)
        brow = QHBoxLayout()
        brow.setSpacing(6)
        dtext = logic.fmt_date(pkg["deadline"]) or tr("no_deadline")
        brow.addWidget(Badge(dtext, "#64748b"))
        if complete:
            brow.addWidget(Badge(tr("complete"), "#16a34a"))
        elif dl is not None:
            brow.addWidget(Badge(days_text(dl), logic.urgency_color(dl)))
        brow.addStretch(1)
        col.addLayout(brow)
        h.addLayout(col, 1)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.pid)


class OverviewPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        top = QHBoxLayout()
        top.addWidget(header(tr("ov_title"), tr("ov_sub")), 1)
        self.new_btn = primary_button(tr("new_package_btn"))
        self.new_btn.clicked.connect(win.new_package)
        top.addWidget(self.new_btn, 0, Qt.AlignTop)
        lay.addLayout(top)
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.s_pk = StatCard(tr("stat_packages"), "#7c3aed")
        self.s_docs = StatCard(tr("stat_docs_ready"), "#16a34a")
        self.s_near = StatCard(tr("stat_nearest"), "#d97706")
        self.s_over = StatCard(tr("stat_overdue"), "#dc2626")
        for s in (self.s_pk, self.s_docs, self.s_near, self.s_over):
            stats.addWidget(s, 1)
        lay.addLayout(stats)

        body = QHBoxLayout()
        body.setSpacing(14)
        left = QVBoxLayout()
        lt = QLabel(tr("active_packages"))
        lt.setObjectName("SectionTitle")
        left.addWidget(lt)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 4, 0)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.grid_host)
        left.addWidget(self.scroll, 1)
        body.addLayout(left, 3)

        up = Card(tr("upcoming"))
        self.up_list = QListWidget()
        self.up_list.setObjectName("Plain")
        self.up_list.setStyleSheet("QListWidget { border: none; background: transparent; }"
                                   "QListWidget::item { padding: 6px 2px; }")
        self.up_list.setWordWrap(True)
        self.up_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.up_list.itemDoubleClicked.connect(self._open_upcoming)
        up.add(self.up_list)
        up.setMinimumWidth(250)
        up.setMaximumWidth(340)
        body.addWidget(up, 2)
        lay.addLayout(body, 1)

    def refresh(self):
        db = self.win.db
        pkgs = sorted(db.packages(), key=lambda p: (
            logic.progress([x["status"] for x in db.items(p["id"])]) >= 1, p["deadline"] or "9999"))
        all_st, near, over = [], None, 0
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        cols = self._columns()
        for i, p in enumerate(pkgs):
            items = db.items(p["id"])
            sts = [x["status"] for x in items]
            all_st += sts
            dl = logic.days_left(p["deadline"])
            if dl is not None and logic.progress(sts) < 1:
                if dl < 0:
                    over += 1
                elif near is None or dl < near[0]:
                    near = (dl, p["title"])
            tile = PackageTile(p, items)
            tile.clicked.connect(self.win.open_package)
            self.grid.addWidget(tile, i // cols, i % cols)
        if not pkgs:
            hint = QLabel(tr("empty_overview"))
            hint.setObjectName("Muted")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            hint.setMinimumHeight(160)
            self.grid.addWidget(hint, 0, 0)
        self.grid.setRowStretch(self.grid.rowCount(), 1)
        c = logic.counts(all_st)
        self.s_pk.value.setText(str(len(pkgs)))
        self.s_docs.value.setText(f"{c['ready'] + c['submitted']} / {len(all_st)}")
        self.s_near.value.setText(days_text(near[0]) if near else "—")
        self.s_near.setToolTip(near[1] if near else "")
        self.s_over.value.setText(str(over))
        # yaqin muddatlar
        self.up_list.clear()
        entries = []
        for p in pkgs:
            sts = [x["status"] for x in db.items(p["id"])]
            if p["deadline"] and logic.progress(sts) < 1:
                entries.append((parse_date(p["deadline"]), p["title"], p["id"], True))
        for it in db.all_open_items_with_due():
            entries.append((parse_date(it["due"]), f"{it['name']} — {it['package_title']}", it["package_id"], False))
        entries.sort(key=lambda x: x[0])
        for d, title, pid, is_pkg in entries[:30]:
            dl = (d - date.today()).days
            li = QListWidgetItem(icon("box" if is_pkg else "file", pal()["muted"]),
                                 f"{title}\n{d.strftime('%d.%m.%Y')} · {days_text(dl)}")
            li.setForeground(QColor(logic.urgency_color(dl)) if dl <= 3 else QColor(pal()["text"]))
            li.setData(Qt.UserRole, pid)
            self.up_list.addItem(li)
        if not entries:
            li = QListWidgetItem(tr("no_upcoming"))
            li.setFlags(Qt.NoItemFlags)
            self.up_list.addItem(li)

    def _open_upcoming(self, it):
        pid = it.data(Qt.UserRole)
        if pid:
            self.win.open_package(pid)

    def _columns(self):
        return max(1, min(3, self.scroll.viewport().width() // 300))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = self._columns()
        if getattr(self, "_cols", None) != cols:
            self._cols = cols
            QTimer.singleShot(0, self.refresh)


# =========================================================================== paketlar
class PackagesPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.db: DB = win.db
        self.pid = None
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(header(tr("pk_title")), 1)
        lab = QLabel(tr("package"))
        lab.setObjectName("Muted")
        top.addWidget(lab)
        self.selector = QComboBox()
        self.selector.setMinimumWidth(280)
        self.selector.currentIndexChanged.connect(self._selected)
        top.addWidget(self.selector)
        nb = QPushButton(tr("new_package_btn"))
        nb.clicked.connect(win.new_package)
        top.addWidget(nb)
        lay.addLayout(top)

        # --- paket kartasi
        self.info_card = Card()
        h = QHBoxLayout()
        h.setSpacing(16)
        self.ring = ProgressRing(92, 10)
        h.addWidget(self.ring, 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(5)
        self.p_title = ElidedLabel()
        self.p_title.setObjectName("Title")
        col.addWidget(self.p_title)
        brow = QHBoxLayout()
        brow.setSpacing(6)
        self.b_kind = Badge()
        self.b_date = Badge()
        self.b_left = Badge()
        for b in (self.b_kind, self.b_date, self.b_left):
            brow.addWidget(b)
        brow.addStretch(1)
        col.addLayout(brow)
        self.p_counts = QLabel()
        self.p_counts.setObjectName("Muted")
        self.p_counts.setWordWrap(True)
        col.addWidget(self.p_counts)
        h.addLayout(col, 1)
        acts = QGridLayout()
        acts.setSpacing(6)
        self.btn_edit = icon_button("edit", tr("edit"))
        self.btn_export = QPushButton(tr("export"))
        em = QMenu(self)
        em.addAction(tr("export_pdf"), self.export_pdf)
        em.addAction(tr("export_xlsx"), self.export_xlsx)
        self.btn_export.setMenu(em)
        self.btn_collect = QPushButton(tr("collect_files"))
        self.btn_collect.setToolTip(tr("collect_tip"))
        self.btn_del = icon_button("trash", tr("delete"))
        self.btn_export.setIcon(icon("export", pal()["text"]))
        self.btn_collect.setIcon(icon("folder", pal()["text"]))
        acts.addWidget(self.btn_collect, 0, 0, 1, 2)
        acts.addWidget(self.btn_export, 1, 0, 1, 2)
        acts.addWidget(self.btn_edit, 0, 2)
        acts.addWidget(self.btn_del, 1, 2)
        h.addLayout(acts)
        self.info_card.add(h)
        lay.addWidget(self.info_card)

        # --- hujjatlar
        docs = Card()
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self.btn_add = primary_button(tr("add_doc_btn"))
        tb.addWidget(self.btn_add)
        self.st_btns = {}
        for s in STATUSES:
            b = QPushButton(status_name(s))
            b.setToolTip(tr("set_status_tip"))
            col_ = logic.STATUS_COLORS[s]
            b.setStyleSheet(f"QPushButton {{ color: {col_}; font-weight: 600; padding: 6px 10px; }}")
            b.clicked.connect(lambda _=False, st=s: self.set_status(st))
            self.st_btns[s] = b
            tb.addWidget(b)
        tb.addStretch(1)
        self.btn_attach = icon_button("paperclip", tr("attach"))
        self.btn_open = icon_button("file", tr("open_file"))
        self.btn_folder = icon_button("folder", tr("open_folder"))
        for b in (self.btn_attach, self.btn_open, self.btn_folder):
            tb.addWidget(b)
        docs.add(tb)
        self.table = ItemTable()
        self.table.setHorizontalHeaderLabels(["№", tr("doc_name"), tr("status"), tr("due_date"), tr("file"),
                                              tr("notes")])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 150)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 140)
        hh.setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 120)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegateForColumn(2, StatusDelegate(self.table))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context)
        self.table.doubleClicked.connect(lambda *_: self.edit_item())
        self.table.file_dropped.connect(self._dropped)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        docs.add(self.table)
        bottom = QHBoxLayout()
        self.hint = QLabel(tr("drop_hint"))
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        bottom.addWidget(self.hint, 1)
        self.btn_up = icon_button("up", tr("move_up"))
        self.btn_down = icon_button("down", tr("move_down"))
        self.btn_up.setToolTip(tr("move_up"))
        self.btn_down.setToolTip(tr("move_down"))
        self.btn_idel = icon_button("trash", tr("delete_doc"))
        for b in (self.btn_up, self.btn_down, self.btn_idel):
            bottom.addWidget(b)
        docs.add(bottom)
        lay.addWidget(docs, 1)

        self.empty = QLabel(tr("empty_packages"))
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty, 1)

        self.btn_edit.clicked.connect(self.edit_package)
        self.btn_del.clicked.connect(self.delete_package)
        self.btn_collect.clicked.connect(self.collect)
        self.btn_add.clicked.connect(self.add_item)
        self.btn_attach.clicked.connect(self.attach)
        self.btn_open.clicked.connect(self.open_file)
        self.btn_folder.clicked.connect(self.open_folder)
        self.btn_up.clicked.connect(lambda: self.move(-1))
        self.btn_down.clicked.connect(lambda: self.move(1))
        self.btn_idel.clicked.connect(self.delete_item)
        for key, fn in (("Delete", self.delete_item), ("F2", self.edit_item), ("Ctrl+D", self.add_item)):
            sc = QShortcut(QKeySequence(key), self.table)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        for i, s in enumerate(STATUSES, 1):
            sc = QShortcut(QKeySequence(str(i)), self.table)
            sc.setContext(Qt.WidgetShortcut)
            sc.activated.connect(lambda st=s: self.set_status(st))

    # ------------------------------------------------------------------ yuklash
    def reload(self, select_pid=None):
        pkgs = self.db.packages()
        if select_pid is None:
            select_pid = self.pid
        self.selector.blockSignals(True)
        self.selector.clear()
        for p in pkgs:
            self.selector.addItem(p["title"], p["id"])
        i = self.selector.findData(select_pid) if select_pid else 0
        self.selector.setCurrentIndex(max(i, 0))
        self.selector.blockSignals(False)
        self.pid = self.selector.currentData()
        has = self.pid is not None
        self.info_card.setVisible(has)
        self.table.parentWidget().setVisible(has)
        self.empty.setVisible(not has)
        self.show_package()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        narrow = self.width() < 900
        self.table.setColumnHidden(5, narrow)
        self.b_kind.setVisible(not narrow)

    def _selected(self):
        self.pid = self.selector.currentData()
        self.show_package()

    def show_package(self):
        if self.pid is None:
            return
        p = self.db.package(self.pid)
        if p is None:
            return
        items = self.db.items(self.pid)
        sts = [i["status"] for i in items]
        pr = logic.progress(sts)
        dl = logic.days_left(p["deadline"])
        complete = bool(sts) and pr >= 1
        self.ring.set_value(pr)
        self.p_title.setText(p["title"])
        self.b_kind.set(p["kind"] or tr("custom"), "#7c3aed")
        self.b_date.set(f"{tr('deadline')}: {logic.fmt_date(p['deadline']) or '—'}", "#64748b")
        if complete:
            self.b_left.set(tr("complete"), "#16a34a")
        else:
            self.b_left.set(days_text(dl), logic.urgency_color(dl))
        c = logic.counts(sts)
        parts = [f"{status_name(s)}: {c[s]}" for s in STATUSES]
        extra = " · ".join(x for x in (p["org"], p["notes"]) if x)
        self.p_counts.setText("   ".join(parts) + (f"\n{extra}" if extra else ""))
        self.fill_table(items)

    def fill_table(self, items):
        sel = self.current_item_id()
        self.table.setRowCount(len(items))
        c = pal()
        for r, it in enumerate(items):
            n = QTableWidgetItem(str(r + 1))
            n.setData(Qt.UserRole, it["id"])
            n.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, n)
            name = QTableWidgetItem(it["name"])
            if it["status"] in DONE_STATUSES:
                f = name.font()
                f.setStrikeOut(it["status"] == "submitted")
                name.setFont(f)
            self.table.setItem(r, 1, name)
            st = QTableWidgetItem(status_name(it["status"]))
            st.setData(Qt.UserRole, it["status"])
            self.table.setItem(r, 2, st)
            d = parse_date(it["due"])
            due = QTableWidgetItem(d.strftime("%d.%m.%Y") if d else "")
            if d and it["status"] not in DONE_STATUSES and (d - date.today()).days <= 3:
                due.setForeground(QColor("#dc2626"))
            self.table.setItem(r, 3, due)
            fp = it["file_path"] or ""
            fi = QTableWidgetItem(os.path.basename(fp) if fp else "—")
            if fp:
                fi.setIcon(icon("paperclip", pal()["muted"], 16))
            fi.setToolTip(fp)
            if fp and not os.path.isfile(fp):
                fi.setForeground(QColor("#dc2626"))
                fi.setToolTip(f"{fp}\n{tr('file_missing')}")
            elif not fp:
                fi.setForeground(QColor(c["muted"]))
            self.table.setItem(r, 4, fi)
            nt = QTableWidgetItem(it["notes"] or "")
            nt.setToolTip(it["notes"] or "")
            self.table.setItem(r, 5, nt)
            if it["id"] == sel:
                self.table.selectRow(r)
        if self.table.currentRow() < 0 and items:
            self.table.selectRow(0)
        self._update_buttons()

    def current_item_id(self):
        r = self.table.currentRow()
        if r < 0 or not self.table.item(r, 0):
            return None
        return self.table.item(r, 0).data(Qt.UserRole)

    def _update_buttons(self):
        iid = self.current_item_id()
        it = self.db.item(iid) if iid else None
        has = it is not None
        fp = it["file_path"] if has else ""
        for b in list(self.st_btns.values()) + [self.btn_attach, self.btn_up, self.btn_down, self.btn_idel]:
            b.setEnabled(has)
        self.btn_open.setEnabled(bool(fp) and os.path.isfile(fp))
        self.btn_folder.setEnabled(bool(fp) and os.path.isdir(os.path.dirname(fp) or "?"))

    def _changed(self):
        self.show_package()
        self.win.data_changed(skip=self)

    # ------------------------------------------------------------------ paket amallari
    def edit_package(self):
        p = self.db.package(self.pid) if self.pid else None
        if not p:
            return
        dlg = PackageDialog(self.win, p)
        if dlg.exec():
            v = dlg.values()
            self.db.update_package(self.pid, title=v["title"], deadline=v["deadline"], org=v["org"], notes=v["notes"])
            self.reload(self.pid)
            self.win.data_changed(skip=self)

    def delete_package(self):
        p = self.db.package(self.pid) if self.pid else None
        if p and ask(self, tr("confirm_delete_pkg", name=p["title"])):
            self.db.delete_package(self.pid)
            self.pid = None
            self.reload()
            self.win.data_changed(skip=self)

    def _items_dicts(self):
        return [dict(r) for r in self.db.items(self.pid)]

    def collect(self):
        if not self.pid:
            return
        items = self._items_dicts()
        if not any((i["file_path"] or "").strip() for i in items):
            info(self, tr("no_attached"))
            return
        p = self.db.package(self.pid)
        base = QFileDialog.getExistingDirectory(self, tr("choose_dest"), str(Path.home() / "Desktop"))
        if not base:
            return
        dest = logic.unique_path(Path(base) / logic.safe_filename(p["title"]))
        dlg = QProgressDialog(tr("copying"), tr("cancel"), 0, 100, self)
        dlg.setWindowTitle(tr("collect_files"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        w = Worker(lambda progress: logic.copy_package_files(items, str(dest), progress))
        w.signals.progress.connect(lambda pct, msg: (dlg.setValue(pct), dlg.setLabelText(msg)))
        dlg.canceled.connect(w.cancel)

        def done(res):
            dlg.close()
            copied, missing = res
            msg = tr("collect_done", n=len(copied), path=str(dest))
            if missing:
                msg += "\n\n" + tr("collect_missing") + "\n• " + "\n• ".join(missing)
            info(self, msg)
            if copied:
                open_path(str(dest))
        w.signals.result.connect(done)
        w.signals.error.connect(lambda m: (dlg.close(), error(self, f"{tr('collect_error')}\n{m}")))
        run_worker(w)

    def _export_rows(self):
        rows = []
        for i, it in enumerate(self.db.items(self.pid), 1):
            rows.append((i, it["name"], status_name(it["status"]), logic.fmt_date(it["due"]),
                         os.path.basename(it["file_path"] or ""), it["notes"] or "", it["status"]))
        return rows

    def export_pdf(self):
        if not self.pid:
            return
        p = self.db.package(self.pid)
        path, _ = QFileDialog.getSaveFileName(self, tr("export_pdf"),
                                              str(Path.home() / f"{logic.safe_filename(p['title'])}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            html_to_pdf(path, build_pdf_html(self.db, self.pid))
            self.win.status(tr("saved_to", path=path))
            open_path(path)
        except Exception as ex:
            appmod.log_exception(ex)
            error(self, tr("export_error"))

    def export_xlsx(self):
        if not self.pid:
            return
        p = self.db.package(self.pid)
        path, _ = QFileDialog.getSaveFileName(self, tr("export_xlsx"),
                                              str(Path.home() / f"{logic.safe_filename(p['title'])}.xlsx"),
                                              "Excel (*.xlsx)")
        if not path:
            return
        try:
            export_xlsx(self.db, self.pid, path)
            self.win.status(tr("saved_to", path=path))
            open_path(path)
        except Exception as ex:
            appmod.log_exception(ex)
            error(self, tr("export_error"))

    # ------------------------------------------------------------------ hujjat amallari
    def add_item(self):
        if not self.pid:
            return
        dlg = ItemDialog(self)
        if dlg.exec():
            v = dlg.values()
            self.db.add_item(self.pid, v["name"], v["status"], v["file_path"], v["notes"], v["due"])
            self._changed()
            self.table.selectRow(self.table.rowCount() - 1)

    def edit_item(self):
        iid = self.current_item_id()
        if not iid:
            return
        dlg = ItemDialog(self, self.db.item(iid))
        if dlg.exec():
            self.db.update_item(iid, **dlg.values())
            self._changed()

    def delete_item(self):
        iid = self.current_item_id()
        if iid and ask(self, tr("confirm_delete_doc", name=self.db.item(iid)["name"])):
            self.db.delete_item(iid)
            self._changed()

    def set_status(self, st):
        iid = self.current_item_id()
        if iid:
            self.db.update_item(iid, status=st)
            self._changed()

    def attach(self):
        iid = self.current_item_id()
        if not iid:
            return
        cur = self.db.item(iid)["file_path"] or str(Path.home())
        p, _ = QFileDialog.getOpenFileName(self, tr("select_file"), cur, tr("all_files") + " (*.*)")
        if p:
            self._attach_path(iid, os.path.normpath(p))

    def _attach_path(self, iid, path):
        it = self.db.item(iid)
        kw = {"file_path": path}
        if it["status"] == "need":
            kw["status"] = "progress"
        self.db.update_item(iid, **kw)
        self._changed()
        self.win.status(tr("attached", name=os.path.basename(path)))

    def _dropped(self, row, path):
        it = self.table.item(row, 0)
        if it:
            self._attach_path(it.data(Qt.UserRole), path)

    def open_file(self):
        iid = self.current_item_id()
        fp = self.db.item(iid)["file_path"] if iid else ""
        if fp and os.path.isfile(fp):
            open_path(fp)
        elif fp:
            warn(self, tr("file_missing"))

    def open_folder(self):
        iid = self.current_item_id()
        fp = self.db.item(iid)["file_path"] if iid else ""
        if fp and os.path.isfile(fp):
            reveal_in_explorer(fp)
        elif fp and os.path.isdir(os.path.dirname(fp)):
            open_path(os.path.dirname(fp))

    def move(self, delta):
        iid = self.current_item_id()
        if iid:
            self.db.move_item(iid, delta)
            self._changed()

    def _context(self, pos):
        if self.current_item_id() is None:
            return
        m = QMenu(self)
        sm = m.addMenu(tr("status"))
        for s in STATUSES:
            sm.addAction(status_name(s), lambda st=s: self.set_status(st))
        m.addAction(tr("edit"), self.edit_item)
        m.addAction(tr("attach"), self.attach)
        m.addAction(tr("open_file"), self.open_file)
        m.addAction(tr("open_folder"), self.open_folder)
        m.addSeparator()
        m.addAction(tr("delete_doc"), self.delete_item)
        m.exec(self.table.viewport().mapToGlobal(pos))


# =========================================================================== eksport funksiyalari
def build_pdf_html(db: DB, pid: int) -> str:
    p = db.package(pid)
    items = db.items(pid)
    sts = [i["status"] for i in items]
    pr = logic.progress(sts)
    dl = logic.days_left(p["deadline"])
    rows = []
    for i, it in enumerate(items, 1):
        col = logic.STATUS_COLORS[it["status"]]
        rows.append(
            f"<tr><td align='center'>{i}</td><td>{esc(it['name'])}</td>"
            f"<td><span style='color:{col}; font-weight:600'>{esc(status_name(it['status']))}</span></td>"
            f"<td>{esc(logic.fmt_date(it['due']))}</td><td>{esc(os.path.basename(it['file_path'] or ''))}</td>"
            f"<td>{esc(it['notes'] or '')}</td></tr>")
    c = logic.counts(sts)
    summary = " &nbsp;·&nbsp; ".join(f"{esc(status_name(s))}: <b>{c[s]}</b>" for s in STATUSES)
    return f"""
<html><body style="font-family:'Segoe UI'; font-size:10pt;">
<h2 style="color:#7c3aed; margin-bottom:2px;">{esc(p['title'])}</h2>
<p style="color:#555; margin-top:0;">{esc(p['kind'] or '')}{(' · ' + esc(p['org'])) if p['org'] else ''}</p>
<p><b>{esc(tr('deadline'))}:</b> {esc(logic.fmt_date(p['deadline']) or '—')} ({esc(days_text(dl))})
 &nbsp;&nbsp; <b>{esc(tr('progress'))}:</b> {round(pr * 100)}% ({c['ready'] + c['submitted']} / {len(sts)})</p>
<p>{summary}</p>
<table width="100%" cellspacing="0" cellpadding="5" border="1" style="border-collapse:collapse; border-color:#ccc;">
<tr style="background:#ede9fe;"><th width="4%">№</th><th>{esc(tr('doc_name'))}</th>
<th width="14%">{esc(tr('status'))}</th><th width="11%">{esc(tr('due_date'))}</th><th width="18%">{esc(tr('file'))}</th>
<th width="18%">{esc(tr('notes'))}</th></tr>
{''.join(rows)}
</table>
{('<p><b>' + esc(tr('notes')) + ':</b> ' + esc(p['notes']) + '</p>') if p['notes'] else ''}
<p style="color:#888; font-size:8pt;">{esc(tr('generated'))}: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
</body></html>"""


def export_xlsx(db: DB, pid: int, path: str):
    p = db.package(pid)
    items = db.items(pid)
    rows, fills = [], []
    fill_map = {"need": "FEE2E2", "progress": "FEF3C7", "ready": "DCFCE7", "submitted": "DBEAFE"}
    for i, it in enumerate(items, 1):
        rows.append((i, it["name"], status_name(it["status"]), logic.fmt_date(it["due"]), it["file_path"] or "",
                     it["notes"] or ""))
        fills.append(fill_map[it["status"]])
    pr = logic.progress([i["status"] for i in items])
    title = f"{p['title']} — {tr('deadline')}: {logic.fmt_date(p['deadline']) or '—'} — {round(pr * 100)}%"
    write_xlsx(path, tr("checklist"), ["№", tr("doc_name"), tr("status"), tr("due_date"), tr("file"), tr("notes")],
               rows, widths=[6, 48, 18, 14, 50, 36], title=title, accent_hex="#7c3aed", fills=fills)


# =========================================================================== shablonlar
class TemplatesPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.db: DB = win.db
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.addWidget(header(tr("tpl_title"), tr("tpl_sub")))
        body = QHBoxLayout()
        body.setSpacing(14)
        left = Card(tr("templates"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show)
        left.add(self.list)
        lb = QHBoxLayout()
        self.btn_new = QPushButton(tr("new_template"))
        self.btn_restore = QPushButton(tr("restore_builtin"))
        lb.addWidget(self.btn_new)
        lb.addWidget(self.btn_restore)
        left.add(lb)
        left.setMaximumWidth(330)
        body.addWidget(left, 2)
        right = Card(tr("tpl_edit"))
        form = QFormLayout()
        self.name = QLineEdit()
        form.addRow(tr("name"), self.name)
        right.add(form)
        lab = QLabel(tr("tpl_items_hint"))
        lab.setObjectName("Muted")
        right.add(lab)
        self.items = QPlainTextEdit()
        right.add(self.items)
        rb = QHBoxLayout()
        self.btn_del = danger_button(tr("delete"))
        self.btn_use = QPushButton(tr("use_template"))
        self.btn_save = primary_button(tr("save"))
        rb.addWidget(self.btn_del)
        rb.addStretch(1)
        rb.addWidget(self.btn_use)
        rb.addWidget(self.btn_save)
        right.add(rb)
        body.addWidget(right, 3)
        lay.addLayout(body, 1)
        self.btn_new.clicked.connect(self._new)
        self.btn_restore.clicked.connect(self._restore)
        self.btn_del.clicked.connect(self._delete)
        self.btn_save.clicked.connect(self._save)
        self.btn_use.clicked.connect(self._use)
        self.reload()

    def reload(self, select=None):
        self.list.blockSignals(True)
        self.list.clear()
        for t in self.db.templates():
            it = QListWidgetItem(icon("layers" if t["builtin"] else "file", pal()["muted"], 16), t["name"])
            it.setData(Qt.UserRole, t["id"])
            it.setToolTip(tr("n_docs", n=len(self.db.template_items(t["id"]))))
            self.list.addItem(it)
        self.list.blockSignals(False)
        row = 0
        if select is not None:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) == select:
                    row = i
        if self.list.count():
            self.list.setCurrentRow(row)
            self._show(row)

    def _tid(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _show(self, row):
        tid = self._tid()
        if tid is None:
            self.name.clear()
            self.items.clear()
            return
        t = [x for x in self.db.templates() if x["id"] == tid][0]
        self.name.setText(t["name"])
        self.items.setPlainText("\n".join(self.db.template_items(tid)))

    def _new(self):
        tid = self.db.add_template(tr("new_template_name"), [])
        self.reload(tid)
        self.name.setFocus()
        self.name.selectAll()

    def _save(self):
        tid = self._tid()
        if tid is None:
            return
        name = self.name.text().strip()
        if not name:
            warn(self, tr("need_title"))
            return
        self.db.rename_template(tid, name)
        self.db.set_template_items(tid, self.items.toPlainText().splitlines())
        self.reload(tid)
        self.win.status(tr("saved"))

    def _delete(self):
        tid = self._tid()
        if tid and ask(self, tr("confirm_delete_tpl", name=self.name.text())):
            self.db.delete_template(tid)
            self.reload()

    def _restore(self):
        if ask(self, tr("confirm_restore")):
            self.db.seed_builtin(language(), force=True)
            self.reload()

    def _use(self):
        tid = self._tid()
        if tid:
            self._save()
            self.win.new_package(template_id=tid)


# =========================================================================== sozlamalar
class SettingsPage(QWidget):
    THRESHOLDS = [30, 14, 7, 3, 1, 0]

    def __init__(self, win):
        super().__init__()
        self.win = win
        s = win.settings
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.addWidget(header(tr("set_title"), tr("set_sub")))
        rc = Card(tr("reminders"))
        lab = QLabel(tr("remind_before"))
        rc.add(lab)
        row = QHBoxLayout()
        self.th_boxes = {}
        cur = set(win.thresholds())
        for t in self.THRESHOLDS:
            cb = QCheckBox(tr("day0") if t == 0 else tr("n_days", n=t))
            cb.setChecked(t in cur)
            cb.toggled.connect(self._save_th)
            self.th_boxes[t] = cb
            row.addWidget(cb)
        row.addStretch(1)
        rc.add(row)
        self.items_cb = QCheckBox(tr("notify_items"))
        self.items_cb.setChecked(s.get("notify_items", True))
        self.items_cb.toggled.connect(lambda v: self._set("notify_items", v))
        rc.add(self.items_cb)
        test = QPushButton(tr("test_notification"))
        test.clicked.connect(lambda: win.tray.notify(tr("app_short"), tr("test_text")))
        tr_row = QHBoxLayout()
        tr_row.addWidget(test)
        tr_row.addStretch(1)
        rc.add(tr_row)
        lay.addWidget(rc)
        tc = Card(tr("background"))
        self.tray_cb = QCheckBox(tr("minimize_to_tray"))
        self.tray_cb.setChecked(s.get("minimize_to_tray", True))
        self.tray_cb.toggled.connect(lambda v: (self._set("minimize_to_tray", v), win.apply_tray_mode()))
        tc.add(self.tray_cb)
        self.auto_cb = QCheckBox(tr("autostart"))
        self.auto_cb.setChecked(is_autostart(AUTOSTART_NAME))
        self.auto_cb.toggled.connect(self._autostart)
        tc.add(self.auto_cb)
        h = QLabel(tr("autostart_hint"))
        h.setObjectName("Muted")
        h.setWordWrap(True)
        tc.add(h)
        lay.addWidget(tc)
        dc = Card(tr("data"))
        p = QLabel(str(win.db.path))
        p.setObjectName("Muted")
        p.setTextInteractionFlags(Qt.TextSelectableByMouse)
        p.setWordWrap(True)
        dc.add(p)
        ob = QPushButton(tr("open_data_folder"))
        ob.clicked.connect(lambda: open_path(str(win.db.path.parent)))
        r2 = QHBoxLayout()
        r2.addWidget(ob)
        r2.addStretch(1)
        dc.add(r2)
        lay.addWidget(dc)
        lay.addStretch(1)

    def _set(self, k, v):
        if not is_demo():
            self.win.settings.set(k, v)

    def _save_th(self):
        self._set("thresholds", [t for t, cb in self.th_boxes.items() if cb.isChecked()])

    def _autostart(self, v):
        if is_demo():
            return
        if not set_autostart(AUTOSTART_NAME, v, autostart_command("--tray")):
            error(self, tr("autostart_failed"))
            self.auto_cb.blockSignals(True)
            self.auto_cb.setChecked(not v)
            self.auto_cb.blockSignals(False)


# =========================================================================== demo
def load_demo(db: DB, folder: Path):
    """Skrinshot rejimi uchun namunaviy ma'lumotlar (vaqtinchalik bazada)."""
    today = date.today()
    files = folder / "hujjatlar"
    files.mkdir(exist_ok=True)

    def f(name):
        p = files / name
        p.write_bytes(b"%PDF-1.4 demo")
        return str(p)
    tpls = {t["key"]: t["id"] for t in db.templates()}
    names = db.template_items(tpls["president"])
    pid = db.add_package(f"{tr('demo_president')} 2026", tr("demo_president"), today + timedelta(days=19),
                         tr("demo_org"), "", names)
    plan = ["submitted", "ready", "ready", "ready", "ready", "progress", "ready", "progress", "need", "need",
            "ready", "progress", "need"]
    for it, st in zip(db.items(pid), plan):
        kw = {"status": st}
        if st in ("ready", "submitted"):
            kw["file_path"] = f(logic.safe_filename(it["name"]) + ".pdf")
        db.update_item(it["id"], **kw)
    its = db.items(pid)
    db.update_item(its[8]["id"], due=today + timedelta(days=2), notes=tr("demo_note1"))
    db.update_item(its[9]["id"], due=today + timedelta(days=9))
    db.update_item(its[10]["id"], notes="IELTS 7.0")
    names = db.template_items(tpls["conference"])
    pid2 = db.add_package("ICAIIT 2026 — " + tr("demo_conf"), tr("demo_conf"), today + timedelta(days=6),
                          "TATU", "", names)
    for it, st in zip(db.items(pid2), ["ready", "ready", "ready", "ready", "progress", "need", "need", "need",
                                        "need"]):
        db.update_item(it["id"], status=st)
    names = db.template_items(tpls["attestation"])
    pid3 = db.add_package(tr("demo_att"), tr("demo_att"), today + timedelta(days=48), "", "", names)
    for it, st in zip(db.items(pid3), ["ready", "ready", "progress", "need", "need", "need", "need", "need",
                                        "need", "ready"]):
        db.update_item(it["id"], status=st)
    names = db.template_items(tpls["grant"])
    pid4 = db.add_package(tr("demo_grant"), tr("demo_grant"), today - timedelta(days=12), "", "", names)
    for it in db.items(pid4):
        db.update_item(it["id"], status="submitted")
    return pid


# =========================================================================== asosiy oyna
class MainWindow(BaseMainWindow):
    def __init__(self):
        super().__init__()
        data = app_data_dir(SLUG)
        self.db = DB(data / "cheklist.db")
        self.db.seed_builtin(language())
        demo_pid = None
        if is_demo():
            demo_pid = load_demo(self.db, data)

        act = QAction(tr("new_package"), self)
        act.setShortcut("Ctrl+N")
        act.triggered.connect(lambda: self.new_package())
        first = self.menu_file.actions()[0] if self.menu_file.actions() else None
        self.menu_file.insertAction(first, act)
        self.menu_file.insertSeparator(first)

        self.overview = OverviewPage(self)
        self.packages = PackagesPage(self)
        self.templates = TemplatesPage(self)
        self.add_page(tr("page_overview"), self.overview, icon("home", "#7c3aed"))
        self.add_page(tr("page_packages"), self.packages, icon("box", "#7c3aed"))
        self.add_page(tr("page_templates"), self.templates, icon("layers", "#7c3aed"))
        self.tray = Tray(self, self.windowIcon() if not self.windowIcon().isNull() else
                         QIcon(str(resource("assets", "icon.ico"))))
        self.settings_page = SettingsPage(self)
        self.add_page(tr("page_settings"), self.settings_page, icon("gear", "#7c3aed"))
        self._nav.setFixedWidth(196)
        self.overview.refresh()
        self.packages.reload(demo_pid)

        self._hint_shown = False
        if not is_demo() and "--selftest" not in sys.argv:
            self.tray.show()
            self.apply_tray_mode()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.check_reminders)
            self.timer.start(60_000)
            QTimer.singleShot(4000, self.check_reminders)
            if "--tray" in sys.argv and self.settings.get("minimize_to_tray", True) and self.tray.available():
                QTimer.singleShot(0, self.hide)

    # ------------------------------------------------------------------ umumiy
    def thresholds(self):
        return self.settings.get("thresholds", [7, 3, 1, 0])

    def apply_tray_mode(self):
        from PySide6.QtWidgets import QApplication
        on = self.settings.get("minimize_to_tray", True) and self.tray.available()
        QApplication.instance().setQuitOnLastWindowClosed(not on)

    def data_changed(self, skip=None):
        if skip is not self.overview:
            self.overview.refresh()
        if skip is not self.packages:
            self.packages.reload()

    def open_package(self, pid):
        self.packages.reload(pid)
        self.set_page(1)

    def new_package(self, template_id=None):
        dlg = PackageDialog(self)
        if template_id:
            dlg.preselect_template(template_id)
        if dlg.exec():
            v = dlg.values()
            pid = self.db.add_package(v["title"], v["kind"], v["deadline"], v["org"], v["notes"], v["items"])
            self.overview.refresh()
            self.open_package(pid)

    def on_theme_changed(self):
        self.overview.refresh()
        self.packages.reload()
        self.update()

    # ------------------------------------------------------------------ eslatmalar
    def check_reminders(self):
        try:
            today = date.today()
            entries = []
            for p in self.db.packages():
                sts = [i["status"] for i in self.db.items(p["id"])]
                if p["deadline"] and logic.progress(sts) < 1:
                    entries.append((f"p{p['id']}", p["title"], p["deadline"]))
            if self.settings.get("notify_items", True):
                for it in self.db.all_open_items_with_due():
                    entries.append((f"i{it['id']}", f"{it['name']} ({it['package_title']})", it["due"]))
            due = logic.due_notifications(entries, today, self.thresholds(), self.db.notified_keys())
            if not due:
                return
            lines = []
            for key, title, dl in due:
                self.db.mark_notified(key)
                lines.append(f"• {title}: {days_text(dl)}")
            text = "\n".join(lines[:4]) + (f"\n… +{len(lines) - 4}" if len(lines) > 4 else "")
            self.tray.notify(tr("reminder_title"), text)
            self.overview.refresh()
        except Exception as ex:
            appmod.log_exception(ex)

    def closeEvent(self, e):
        if (not self.tray.quitting and self.settings.get("minimize_to_tray", True) and self.tray.available()
                and self.tray.icon.isVisible()):
            e.ignore()
            self.hide()
            if not self.settings.get("tray_hint_shown"):
                self.tray.notify(tr("app_short"), tr("tray_hint"))
                self.settings.set("tray_hint_shown", True)
            try:
                self.settings.set("geometry", bytes(self.saveGeometry().toBase64()).decode())
            except Exception:
                pass
            return
        super().closeEvent(e)
