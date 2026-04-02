"""QSS stylesheets and accent color restyling functions."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from semetra.gui.colors import ACCENT_PRESETS, _tc, _hex_rgba, get_accent_color


# ── QSS ───────────────────────────────────────────────────────────────────

LIGHT_QSS = """
* { font-family: 'Inter', 'Segoe UI', 'Ubuntu', Arial, sans-serif, 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji'; font-size: 13px; }
QWidget { background: transparent; color: #1A1523; }
QMainWindow { background: #F6F5FA; }
QDialog { background: #F6F5FA; border-radius: 16px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── Sidebar ─────────────────────────────── */
QWidget#Sidebar {
    background: #FFFFFF;
    border-right: 1px solid #EAE8F2;
}
QLabel#AppTitle {
    font-size: 14px; font-weight: 800;
    color: #1A1523; letter-spacing: -0.3px;
    padding: 2px 6px;
}
QLabel#AppVersion { font-size: 10px; color: #9B95B5; padding: 0 6px 2px 6px; letter-spacing: 0.3px; }
QLabel#NavSectionLabel {
    font-size: 10px; font-weight: 700; color: #A8A2BE;
    letter-spacing: 1.5px; padding: 0px 14px;
}
QPushButton#NavBtn {
    background: transparent; border: none; border-radius: 9px;
    text-align: left; padding: 10px 14px;
    font-size: 13px; color: #6E6882; font-weight: 500;
}
QPushButton#NavBtn:hover { background: #F3F1FA; color: #1A1523; }
QPushButton#NavBtn[active="true"] {
    background: #EDE9FE; color: #6D28D9; font-weight: 700;
    border-left: 3px solid #7C3AED; padding-left: 11px;
}
QPushButton#QuickAddBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #A78BFA);
    color: white; border: none; border-radius: 10px;
    padding: 10px 14px; font-size: 13px; font-weight: 700; text-align: left;
}
QPushButton#QuickAddBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #8B5CF6);
}
QPushButton#QuickAddBtn:pressed {
    background: #5B21B6;
}

/* ── Page background ─────────────────────── */
QWidget#PageContent { background: #F6F5FA; }

/* ── Cards ───────────────────────────────── */
QFrame#Card {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1px solid #EAE8F2;
}
QFrame#QuoteCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #F0EAFF, stop:0.55 #FAF6FF, stop:1 #FEF3FF);
    border-radius: 16px;
    border: 1px solid #DDD6FE;
}
QFrame#FocusCard {
    background: #FFFFFF;
    border-radius: 16px;
    border: 1.5px solid #DDD6FE;
}
QLabel#CardTitle { font-size: 12px; color: #8C87A3; letter-spacing: 0.3px; font-weight: 600; }
QLabel#CardValue { font-size: 30px; font-weight: 800; letter-spacing: -1px; }
QLabel#CardUnit { font-size: 12px; color: #8C87A3; margin-bottom: 4px; }

/* ── Typography ──────────────────────────── */
QLabel#PageTitle { font-size: 22px; font-weight: 800; color: #1A1523; letter-spacing: -0.5px; }
QLabel#SectionTitle { font-size: 12px; font-weight: 700; color: #6D28D9; letter-spacing: 0.8px; text-transform: uppercase; }
QLabel { color: #1A1523; }

/* ── Buttons ─────────────────────────────── */
QPushButton#PrimaryBtn {
    background: #7C3AED; color: white; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 700;
}
QPushButton#PrimaryBtn:hover { background: #6D28D9; }
QPushButton#PrimaryBtn:pressed { background: #5B21B6; }
QPushButton#DangerBtn {
    background: #EF4444; color: white; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 600;
}
QPushButton#DangerBtn:hover { background: #DC2626; }
QPushButton#SecondaryBtn {
    background: #F0EAFF; color: #7C3AED; border: 1.5px solid #DDD6FE;
    border-radius: 10px; padding: 8px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#SecondaryBtn:hover { background: #EDE9FE; border-color: #C4B5FD; }
QPushButton#CoachBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7C3AED, stop:1 #A78BFA);
    color: white; border: none; border-radius: 10px;
    padding: 9px 16px; font-size: 13px; font-weight: 700;
}
QPushButton#CoachBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6D28D9, stop:1 #7C3AED);
}
QComboBox#SemesterFilter {
    background: #F0EAFF; border: 1.5px solid #DDD6FE; border-radius: 12px;
    padding: 5px 12px; font-size: 12px; color: #6D28D9; font-weight: 700;
    selection-background-color: #7C3AED;
}
QComboBox#SemesterFilter::drop-down { border: none; width: 20px; }
QComboBox#SemesterFilter:hover { border-color: #7C3AED; background: #EDE9FE; }

/* ── Inputs ──────────────────────────────── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #FFFFFF; border: 1.5px solid #E2DEF0; border-radius: 10px;
    padding: 8px 12px; font-size: 13px; color: #1A1523; selection-background-color: #7C3AED;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus {
    border-color: #7C3AED; background: #FDFBFF;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { width: 10px; height: 10px; }
QComboBox QAbstractItemView {
    background: #FFFFFF; color: #1A1523;
    selection-background-color: #7C3AED; selection-color: #FFFFFF;
    border: 1px solid #E2DEF0; border-radius: 10px;
}
QComboBox QAbstractItemView::item { min-height: 30px; padding: 5px 12px; }
QComboBox QAbstractItemView::item:selected { background: #7C3AED; color: #FFFFFF; }
QComboBox QAbstractItemView::item:hover { background: #F0EAFF; }

/* ── Checkboxes & Radiobuttons ───────────── */
QCheckBox { color: #1A1523; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px;
    border: 1.5px solid #D4D0E3; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #7C3AED; border-color: #7C3AED; }
QCheckBox::indicator:hover { border-color: #7C3AED; }
QRadioButton { color: #1A1523; spacing: 8px; }
QRadioButton::indicator { width: 17px; height: 17px; border-radius: 9px;
    border: 1.5px solid #D4D0E3; background: #FFFFFF; }
QRadioButton::indicator:checked { background: #7C3AED; border-color: #7C3AED; }

/* ── Scrollbar ───────────────────────────── */
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #E2DEF0; border-radius: 3px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: #C4B5FD; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: #E2DEF0; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress ────────────────────────────── */
QProgressBar { background: #EDE9FE; border-radius: 5px; border: none; max-height: 6px; text-align: center; }
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #A78BFA);
    border-radius: 5px;
}

/* ── Table ───────────────────────────────── */
QTableWidget {
    background: #FFFFFF; border: 1px solid #EAE8F2;
    border-radius: 14px; gridline-color: #F3F1FA; outline: none;
}
QTableWidget::item { padding: 10px 8px; color: #1A1523; border: none; }
QTableWidget::item:selected { background: #F0EAFF; color: #6D28D9; }
QTableWidget::item:hover { background: #FAF8FF; }
QHeaderView::section {
    background: #FAF8FF; border: none; border-bottom: 1px solid #EAE8F2;
    padding: 10px 8px; font-weight: 700; color: #8C87A3; font-size: 12px; letter-spacing: 0.3px;
}
QHeaderView { border: none; }

/* ── List ────────────────────────────────── */
QListWidget { border: 1px solid #EAE8F2; border-radius: 14px; background: #FFFFFF; outline: none; }
QListWidget::item { padding: 8px 12px; border-radius: 8px; }
QListWidget::item:selected { background: #F0EAFF; color: #6D28D9; }
QListWidget::item:hover { background: #FAF8FF; }

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1.5px solid #EAE8F2; border-radius: 14px;
    margin-top: 14px; padding-top: 8px; font-weight: 700; color: #6D28D9; font-size: 12px;
    background: transparent;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; background: transparent; color: #6D28D9; }

/* ── Calendar ────────────────────────────── */
QCalendarWidget QAbstractItemView { background: #FFFFFF; selection-background-color: #7C3AED; border-radius: 8px; }
QCalendarWidget QWidget { background: #FFFFFF; border-radius: 8px; }

/* ── Dialog ──────────────────────────────── */
QDialog { background: #F6F5FA; border-radius: 16px; }
QDialog QFrame { background: #F6F5FA; }
QDialogButtonBox QPushButton {
    background: #7C3AED; color: white; border: none;
    border-radius: 10px; padding: 8px 22px; min-width: 90px; font-weight: 700;
}
QDialogButtonBox QPushButton:hover { background: #6D28D9; }
QDialogButtonBox QPushButton[text="Cancel"],
QDialogButtonBox QPushButton[text="Abbrechen"] {
    background: #F0EAFF; color: #7C3AED; border: 1.5px solid #DDD6FE;
}
QDialogButtonBox QPushButton[text="Cancel"]:hover,
QDialogButtonBox QPushButton[text="Abbrechen"]:hover { background: #EDE9FE; }

/* ── Panel / Splitter ────────────────────── */
QWidget#ModuleLeftPanel { background: #FFFFFF; border-right: 1px solid #EAE8F2; }
QSplitter::handle { background: #EAE8F2; width: 1px; }
QTextEdit#NotesArea { background: #FDFBFF; border: 1px solid #EAE8F2; border-radius: 10px; }
QFrame#ResourceRow { background: #FAF8FF; border: 1px solid #EAE8F2; border-radius: 10px; }

/* ── Combo Popup Overlay ─────────────────── */
QFrame#ComboPopupOverlay {
    background: #FFFFFF; border: 1.5px solid #E2DEF0; border-radius: 12px;
}
QFrame#ComboPopupOverlay QListWidget {
    background: transparent; border: none; border-radius: 8px; outline: none;
}
QFrame#ComboPopupOverlay QListWidget::item { padding: 7px 14px; border-radius: 7px; color: #1A1523; }
QFrame#ComboPopupOverlay QListWidget::item:selected { background: #7C3AED; color: #FFFFFF; }
QFrame#ComboPopupOverlay QListWidget::item:hover { background: #F0EAFF; }

/* ── Tab Widget ──────────────────────────── */
QTabWidget::pane { border: 1px solid #EAE8F2; border-radius: 12px; background: #FFFFFF; top: -1px; }
QTabBar::tab {
    background: transparent; border: none; padding: 8px 18px;
    font-size: 13px; font-weight: 600; color: #ABA6C2; border-radius: 8px 8px 0 0;
}
QTabBar::tab:selected { color: #7C3AED; border-bottom: 2px solid #7C3AED; background: #FAFAFF; }
QTabBar::tab:hover { color: #6D28D9; background: #F6F4FF; }

/* ── Dock Widget (Sidebar) ──────────────── */
QDockWidget#SidebarDock { border: none; }
QDockWidget#SidebarDock::title { background: transparent; padding: 0; }
"""

DARK_QSS = """
* { font-family: 'Inter', 'Segoe UI', 'Ubuntu', Arial, sans-serif, 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI Emoji'; font-size: 13px; }
QWidget { background: transparent; color: #EAE6F4; }
QMainWindow { background: #0D0B12; }
QDialog { background: #0D0B12; border-radius: 16px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget { background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ── Sidebar ─────────────────────────────── */
QWidget#Sidebar {
    background: #111019;
    border-right: 1px solid #1E1B2C;
}
QLabel#AppTitle { font-size: 14px; font-weight: 800; color: #EAE6F4; letter-spacing: -0.3px; padding: 2px 6px; }
QLabel#AppVersion { font-size: 10px; color: #6B657E; padding: 0 6px 2px 6px; letter-spacing: 0.3px; }
QLabel#NavSectionLabel {
    font-size: 10px; font-weight: 700; color: #5E5876;
    letter-spacing: 1.5px; padding: 0px 14px;
}
QPushButton#NavBtn {
    background: transparent; border: none; border-radius: 9px;
    text-align: left; padding: 10px 14px; font-size: 13px; color: #7A7492; font-weight: 500;
}
QPushButton#NavBtn:hover { background: #1A1728; color: #EAE6F4; }
QPushButton#NavBtn[active="true"] {
    background: #281E48; color: #C4B5FD; font-weight: 700;
    border-left: 3px solid #7C3AED; padding-left: 11px;
}
QPushButton#QuickAddBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #8B5CF6);
    color: white; border: none; border-radius: 10px;
    padding: 10px 14px; font-size: 13px; font-weight: 700; text-align: left;
}
QPushButton#QuickAddBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5B21B6, stop:1 #7C3AED);
}
QPushButton#QuickAddBtn:pressed { background: #4C1D95; }

/* ── Page background ─────────────────────── */
QWidget#PageContent { background: #0D0B12; }

/* ── Cards ───────────────────────────────── */
QFrame#Card { background: #15121E; border-radius: 16px; border: 1px solid #1E1B2C; }
QFrame#QuoteCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1A1535, stop:0.55 #15121E, stop:1 #1A1030);
    border-radius: 16px; border: 1px solid #322860;
}
QFrame#FocusCard { background: #15121E; border-radius: 16px; border: 1.5px solid #322860; }
QLabel#CardTitle { font-size: 12px; color: #7A7492; letter-spacing: 0.3px; font-weight: 600; }
QLabel#CardValue { font-size: 30px; font-weight: 800; letter-spacing: -1px; color: #EAE6F4; }
QLabel#CardUnit { font-size: 12px; color: #7A7492; margin-bottom: 4px; }

/* ── Typography ──────────────────────────── */
QLabel#PageTitle { font-size: 22px; font-weight: 800; color: #EAE6F4; letter-spacing: -0.5px; }
QLabel#SectionTitle { font-size: 12px; font-weight: 700; color: #A78BFA; letter-spacing: 0.8px; }
QLabel { color: #EAE6F4; background: transparent; }

/* ── Buttons ─────────────────────────────── */
QPushButton { color: #EAE6F4; background: #1D1A2A; border: 1px solid #2D2040; border-radius: 8px; padding: 6px 14px; }
QPushButton:hover { background: #251E3A; border-color: #4C3D78; }
QPushButton#PrimaryBtn {
    background: #7C3AED; color: #FFFFFF; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 700;
}
QPushButton#PrimaryBtn:hover { background: #6D28D9; }
QPushButton#PrimaryBtn:pressed { background: #5B21B6; }
QPushButton#DangerBtn {
    background: #DC2626; color: #FFFFFF; border: none;
    border-radius: 10px; padding: 9px 22px; font-size: 13px; font-weight: 600;
}
QPushButton#DangerBtn:hover { background: #B91C1C; }
QPushButton#SecondaryBtn {
    background: #1D1A2A; color: #C4B5FD; border: 1px solid #2D2040;
    border-radius: 10px; padding: 8px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#SecondaryBtn:hover { background: #251E3A; border-color: #4C3D78; }
QPushButton#CoachBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6D28D9, stop:1 #8B5CF6);
    color: white; border: none; border-radius: 10px;
    padding: 9px 16px; font-size: 13px; font-weight: 700;
}
QPushButton#CoachBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5B21B6, stop:1 #7C3AED);
}
QToolButton { background: transparent; border: none; color: #EAE6F4; }
QToolButton:hover { background: #1D1A2A; border-radius: 6px; }
QComboBox#SemesterFilter {
    background: #1D1A2A; border: 1.5px solid #2D2040; border-radius: 12px;
    padding: 5px 12px; font-size: 12px; color: #C4B5FD; font-weight: 700;
    selection-background-color: #7C3AED;
}
QComboBox#SemesterFilter::drop-down { border: none; width: 20px; }
QComboBox#SemesterFilter:hover { border-color: #7C3AED; background: #251E3A; }

/* ── Inputs ──────────────────────────────── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #15121E; border: 1.5px solid #232035; border-radius: 10px;
    padding: 8px 12px; font-size: 13px; color: #EAE6F4; selection-background-color: #7C3AED;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus { border-color: #7C3AED; background: #1D1A2A; }
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled { color: #5E5876; background: #111019; border-color: #1E1B2C; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #15121E; color: #EAE6F4;
    selection-background-color: #7C3AED; selection-color: #FFFFFF;
    border: 1px solid #232035; border-radius: 10px;
}
QComboBox QAbstractItemView::item { min-height: 30px; padding: 5px 12px; color: #EAE6F4; }
QComboBox QAbstractItemView::item:selected { background: #7C3AED; color: #FFFFFF; }
QComboBox QAbstractItemView::item:hover { background: #1D1A2A; color: #EAE6F4; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { background: #1D1A2A; border: none; width: 16px; }
QSpinBox::up-arrow, QSpinBox::down-arrow,
QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow { width: 8px; height: 8px; }
QDateEdit::drop-down { border: none; width: 20px; background: #1D1A2A; }

/* ── Checkboxes & Radiobuttons ───────────── */
QCheckBox { color: #EAE6F4; spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px;
    border: 1.5px solid #2D2040; background: #15121E; }
QCheckBox::indicator:checked { background: #7C3AED; border-color: #7C3AED; }
QCheckBox::indicator:hover { border-color: #8B5CF6; }
QRadioButton { color: #EAE6F4; spacing: 8px; background: transparent; }
QRadioButton::indicator { width: 17px; height: 17px; border-radius: 9px;
    border: 1.5px solid #2D2040; background: #15121E; }
QRadioButton::indicator:checked { background: #7C3AED; border-color: #7C3AED; }

/* ── Scrollbar ───────────────────────────── */
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #232035; border-radius: 3px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: #3D3060; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: #232035; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress ────────────────────────────── */
QProgressBar { background: #1D1A2A; border-radius: 5px; border: none; max-height: 6px; text-align: center; color: #EAE6F4; }
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #A78BFA);
    border-radius: 5px;
}

/* ── Table ───────────────────────────────── */
QTableWidget { background: #15121E; border: 1px solid #1E1B2C; border-radius: 14px; gridline-color: #1A1728; outline: none; color: #EAE6F4; }
QTableWidget::item { padding: 10px 8px; color: #EAE6F4; border: none; background: transparent; }
QTableWidget::item:selected { background: #281E48; color: #C4B5FD; }
QTableWidget::item:hover { background: #1A1728; }
QHeaderView { border: none; background: transparent; }
QHeaderView::section { background: #111019; border: none; border-bottom: 1px solid #1E1B2C; padding: 10px 8px; font-weight: 700; color: #7A7492; font-size: 12px; letter-spacing: 0.3px; }

/* ── List ────────────────────────────────── */
QListWidget { border: 1px solid #1E1B2C; border-radius: 14px; background: #15121E; outline: none; color: #EAE6F4; }
QListWidget::item { padding: 8px 12px; border-radius: 8px; color: #EAE6F4; background: transparent; }
QListWidget::item:selected { background: #281E48; color: #C4B5FD; }
QListWidget::item:hover { background: #1A1728; }

/* ── GroupBox ────────────────────────────── */
QGroupBox {
    border: 1.5px solid #1E1B2C; border-radius: 14px;
    margin-top: 14px; padding-top: 8px; font-weight: 700; color: #A78BFA; font-size: 12px;
    background: transparent;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; background: transparent; color: #A78BFA; }

/* ── Calendar ────────────────────────────── */
QCalendarWidget { background: #15121E; color: #EAE6F4; }
QCalendarWidget QAbstractItemView { background: #15121E; selection-background-color: #7C3AED; color: #EAE6F4; border-radius: 8px; }
QCalendarWidget QWidget { background: #15121E; color: #EAE6F4; }
QCalendarWidget QToolButton { background: transparent; color: #EAE6F4; border: none; }
QCalendarWidget QToolButton:hover { background: #1D1A2A; }
QCalendarWidget QSpinBox { background: #15121E; color: #EAE6F4; border: 1px solid #232035; }
QCalendarWidget QMenu { background: #15121E; color: #EAE6F4; border: 1px solid #232035; }

/* ── Dialog content ──────────────────────── */
QDialog QWidget { background: transparent; color: #EAE6F4; }
QDialog QFrame { background: transparent; }
QDialog QScrollArea { background: transparent; border: none; }
QDialog QGroupBox { border-color: #1E1B2C; }
QDialogButtonBox QPushButton {
    background: #7C3AED; color: #FFFFFF; border: none;
    border-radius: 10px; padding: 8px 22px; min-width: 90px; font-weight: 700;
}
QDialogButtonBox QPushButton:hover { background: #6D28D9; }
QDialogButtonBox QPushButton[text="Cancel"],
QDialogButtonBox QPushButton[text="Abbrechen"] {
    background: #1D1A2A; color: #C4B5FD; border: 1px solid #2D2040;
}
QDialogButtonBox QPushButton[text="Cancel"]:hover,
QDialogButtonBox QPushButton[text="Abbrechen"]:hover { background: #251E3A; }

/* ── Panel / Splitter ────────────────────── */
QWidget#ModuleLeftPanel { background: #15121E; border-right: 1px solid #1E1B2C; }
QSplitter::handle { background: #1E1B2C; width: 1px; }
QTextEdit#NotesArea { background: #15121E; border: 1px solid #1E1B2C; border-radius: 10px; color: #EAE6F4; }
QFrame#ResourceRow { background: #1A1728; border: 1px solid #1E1B2C; border-radius: 10px; }

/* ── Message Box ─────────────────────────── */
QMessageBox { background: #0D0B12; }
QMessageBox QLabel { color: #EAE6F4; background: transparent; }

/* ── Combo Popup Overlay ─────────────────── */
QFrame#ComboPopupOverlay {
    background: #15121E; border: 1.5px solid #232035; border-radius: 12px;
}
QFrame#ComboPopupOverlay QListWidget {
    background: transparent; border: none; border-radius: 8px; outline: none;
}
QFrame#ComboPopupOverlay QListWidget::item { padding: 7px 14px; border-radius: 7px; color: #EAE6F4; }
QFrame#ComboPopupOverlay QListWidget::item:selected { background: #7C3AED; color: #FFFFFF; }
QFrame#ComboPopupOverlay QListWidget::item:hover { background: #1D1A2A; }

/* ── Tab Widget ──────────────────────────── */
QTabWidget::pane { border: 1px solid #1E1B2C; border-radius: 12px; background: #15121E; top: -1px; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent; border: none; padding: 8px 18px;
    font-size: 13px; font-weight: 600; color: #7A7492; border-radius: 8px 8px 0 0;
}
QTabBar::tab:selected { color: #A78BFA; border-bottom: 2px solid #8B5CF6; background: #1D1A2A; }
QTabBar::tab:hover { color: #C4B5FD; background: #1A1728; }

/* ── Dock Widget (Sidebar) ──────────────── */
QDockWidget#SidebarDock { border: none; background: transparent; }
QDockWidget#SidebarDock::title { background: transparent; padding: 0; }

/* ── Misc ─────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #1E1B2C; background: transparent; }
"""


def _accent_replace_pairs(old_preset: dict, new_preset: dict) -> list:
    """Build ordered (old, new) hex substitution pairs: most-specific first."""
    return [
        (old_preset["l5"], new_preset["l5"]),
        (old_preset["l4"], new_preset["l4"]),
        (old_preset["l3"], new_preset["l3"]),
        (old_preset["l2"], new_preset["l2"]),
        (old_preset["l1"], new_preset["l1"]),
        (old_preset["d4"], new_preset["d4"]),
        (old_preset["d3"], new_preset["d3"]),
        (old_preset["d2"], new_preset["d2"]),
        (old_preset["d1"], new_preset["d1"]),
        (old_preset["base"], new_preset["base"]),
    ]


def restyle_widgets_accent(root: QWidget, old_preset: dict, new_preset: dict) -> None:
    """Walk every widget under *root* and swap old accent hex values for new ones
    in their individual inline stylesheets.  This is needed because hundreds of
    widgets use setStyleSheet() with hard-coded violet values that are not covered
    by QApplication.setStyleSheet()."""
    if old_preset is new_preset:          # same object → no-op
        return
    pairs = _accent_replace_pairs(old_preset, new_preset)
    for widget in root.findChildren(QWidget):
        ss = widget.styleSheet()
        if not ss:
            continue
        new_ss = ss
        for old, new in pairs:
            if old in new_ss:
                new_ss = new_ss.replace(old, new)
            old_l = old.lower()
            if old_l in new_ss:
                new_ss = new_ss.replace(old_l, new)
        if new_ss != ss:
            widget.setStyleSheet(new_ss)


def get_qss(theme: str) -> str:
    """Return QSS with the currently selected accent palette applied."""
    from semetra.gui import state

    base_qss = DARK_QSS if theme == "dark" else LIGHT_QSS
    violet  = ACCENT_PRESETS["violet"]
    chosen  = ACCENT_PRESETS.get(state._ACCENT_PRESET, violet)
    if chosen is violet:
        return base_qss
    result = base_qss
    for old, new in _accent_replace_pairs(violet, chosen):
        result = result.replace(old, new)
        result = result.replace(old.lower(), new)
    return result
