from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt

from semetra.gui.colors import _tc
from semetra.gui.platform import _open_url


class ProFeatureDialog(QDialog):
    """
    Wird gezeigt wenn ein Free-User ein Pro-Feature nutzen will.
    Zeigt die 3 Abo-Optionen (monatl./halbjährl./jährl.) und ermöglicht
    die Aktivierung eines bereits gekauften Lizenzcodes.
    Returns Accepted wenn eine Lizenz erfolgreich aktiviert wurde.
    """
    def __init__(self, feature_name: str, repo, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.repo = repo
        self.feature_name = feature_name
        self.setWindowTitle("Semetra Pro")
        self.setMinimumWidth(500)
        self.setMaximumWidth(560)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        # ── Header ──────────────────────────────────────────────────────────
        top = QHBoxLayout()
        icon = QLabel("⭐")
        icon.setStyleSheet("font-size:36px;")
        top.addWidget(icon)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title_lbl = QLabel("Semetra Pro")
        title_lbl.setStyleSheet("font-size:20px;font-weight:bold;")
        sub_lbl = QLabel(f"Um <b>\"{self.feature_name}\"</b> zu nutzen,\nbenötigst du Semetra Pro.")
        sub_lbl.setStyleSheet(f"color:{_tc('#555','#AAA')};font-size:13px;")
        sub_lbl.setWordWrap(True)
        sub_lbl.setTextFormat(Qt.RichText)
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        top.addLayout(title_col, 1)
        lay.addLayout(top)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{_tc('#DDE3F0','#383850')};")
        lay.addWidget(sep)

        # ── Feature-Liste ────────────────────────────────────────────────────
        features_lbl = QLabel(
            "<b>Pro beinhaltet:</b><br>"
            "🤖 &nbsp;KI-Studien-Coach (unbegrenzt)<br>"
            "📄 &nbsp;PDF-Import (Modulplan direkt einlesen)<br>"
            "⏱️ &nbsp;Lern-Timer mit Statistiken &amp; Streaks<br>"
            "📊 &nbsp;Lernplan-Generator &amp; Prognosen<br>"
            "🏅 &nbsp;Erweiterte Notenanalyse &amp; Trends<br>"
            "🔮 &nbsp;Alle zukünftigen Pro-Features inklusive"
        )
        features_lbl.setTextFormat(Qt.RichText)
        features_lbl.setWordWrap(True)
        features_lbl.setStyleSheet("font-size:13px;line-height:1.8;")
        lay.addWidget(features_lbl)

        # ── Pricing Cards (simplified) ────────────────────────────────────
        pricing_lbl = QLabel("<b>Plan wählen:</b>")
        pricing_lbl.setTextFormat(Qt.RichText)
        lay.addWidget(pricing_lbl)

        plans_row = QHBoxLayout()
        plans_row.setSpacing(8)
        self._plan_btns: list = []
        plans = [
            ("Monatlich",   "CHF 4.90",  "monthly"),
            ("Halbjährlich","CHF 24.90", "halfyear"),
            ("Jährlich",    "CHF 39.90", "yearly"),
        ]
        for label, price, key in plans:
            card = QFrame()
            card.setFixedHeight(80)
            card.setCursor(Qt.PointingHandCursor)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(10, 8, 10, 8)
            lbl_plan = QLabel(label)
            lbl_plan.setStyleSheet("font-size:11px;font-weight:bold;")
            lbl_price = QLabel(price)
            lbl_price.setStyleSheet("font-size:16px;font-weight:bold;")
            c_lay.addWidget(lbl_plan)
            c_lay.addWidget(lbl_price)
            buy_btn = QPushButton("Kaufen →")
            buy_btn.setFixedHeight(26)
            buy_btn.clicked.connect(lambda checked, k=key: self._open_buy(k))
            c_lay.addWidget(buy_btn)
            plans_row.addWidget(card)
        lay.addLayout(plans_row)

        # ── Lizenzcode Eingabe ───────────────────────────────────────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        lay.addWidget(sep2)

        already_lbl = QLabel("Hast du bereits einen Lizenzcode?")
        already_lbl.setStyleSheet("font-size:12px;font-weight:bold;")
        lay.addWidget(already_lbl)

        code_row = QHBoxLayout()
        self._code_edit = QLineEdit()
        self._code_edit.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self._code_edit.setFixedHeight(34)
        self._code_edit.returnPressed.connect(self._activate)
        code_row.addWidget(self._code_edit, 1)
        activate_btn = QPushButton("Aktivieren")
        activate_btn.setObjectName("PrimaryBtn")
        activate_btn.setFixedHeight(34)
        activate_btn.clicked.connect(self._activate)
        code_row.addWidget(activate_btn)
        lay.addLayout(code_row)

        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet("color:#E05050;font-size:11px;")
        lay.addWidget(self._error_lbl)

        cancel_btn = QPushButton("Abbrechen — im Free-Plan bleiben")
        cancel_btn.setStyleSheet(f"color:{_tc('#9CA3AF','#6B7280')};border:none;background:transparent;")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedHeight(30)
        lay.addWidget(cancel_btn, alignment=Qt.AlignCenter)

    def _open_buy(self, plan_key: str):
        from semetra.infra.license import (
            STRIPE_MONTHLY_URL, STRIPE_HALFYEAR_URL, STRIPE_YEARLY_URL,
            STRIPE_DESKTOP_PRO_URL
        )
        urls = {
            "monthly":      STRIPE_MONTHLY_URL,
            "halfyear":     STRIPE_HALFYEAR_URL,
            "yearly":       STRIPE_YEARLY_URL,
            "desktop_pro":  STRIPE_DESKTOP_PRO_URL,
        }
        _open_url(urls.get(plan_key, STRIPE_MONTHLY_URL))

    def _activate(self):
        from semetra.infra.license import LicenseManager
        code = self._code_edit.text().strip()
        if not code:
            self._error_lbl.setText("Bitte einen Lizenzcode eingeben.")
            return
        lm = LicenseManager(self.repo)
        ok, msg = lm.activate(code)
        if ok:
            QMessageBox.information(
                self, "✅ Aktiviert!",
                "Semetra Pro wurde erfolgreich aktiviert.\n"
                "Danke für deine Unterstützung! 🎉"
            )
            self.accept()
        else:
            self._error_lbl.setText(f"❌ {msg}")
