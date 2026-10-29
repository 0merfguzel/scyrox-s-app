"""Windows stilinin üzerine iki küçük değişiklik (tüm uygulamaya uygulanır):

* Sayı kutularında azaltma düğmesi solda, artırma düğmesi sağda (Windows 11
  stili tersini yapıyor). Hem tıklama alanları hem oklar yer değiştirir.
* Açılır listelerin işareti ok değil üç yatay çizgi: sayı kutusunun "azalt"
  okuyla karışmasın.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QAbstractSpinBox, QApplication, QProxyStyle, QStyle, QStyleFactory,
                             QStyleOptionComboBox, QStyleOptionSpinBox)

CC = QStyle.ComplexControl
SC = QStyle.SubControl
UP, DOWN = SC.SC_SpinBoxUp, SC.SC_SpinBoxDown
STEP = QAbstractSpinBox.StepEnabledFlag


class HelperStyle(QProxyStyle):
    def subControlRect(self, cc, opt, sc, widget=None):  # noqa: N802 - Qt adı
        if cc == CC.CC_SpinBox and sc in (UP, DOWN):
            return super().subControlRect(cc, opt, DOWN if sc == UP else UP, widget)
        return super().subControlRect(cc, opt, sc, widget)

    def drawComplexControl(self, cc, opt, p, widget=None):  # noqa: N802 - Qt adı
        if cc == CC.CC_SpinBox and isinstance(opt, QStyleOptionSpinBox):
            o = QStyleOptionSpinBox(opt)
            o.subControls &= ~(UP | DOWN)
            super().drawComplexControl(cc, o, p, widget)
            self._spin_buttons(opt, p, widget)
            return
        if cc == CC.CC_ComboBox and isinstance(opt, QStyleOptionComboBox):
            o = QStyleOptionComboBox(opt)
            o.subControls &= ~SC.SC_ComboBoxArrow
            super().drawComplexControl(cc, o, p, widget)
            self._menu_lines(opt, p, widget)
            return
        super().drawComplexControl(cc, opt, p, widget)

    def _ink(self, opt, enabled: bool) -> QColor:
        role = opt.palette.ColorRole.Text if enabled else opt.palette.ColorRole.PlaceholderText
        return opt.palette.color(role)

    def _spin_buttons(self, opt: QStyleOptionSpinBox, p: QPainter, widget) -> None:
        steps = opt.stepEnabled
        flags = QStyle.StateFlag
        if opt.buttonSymbols == QAbstractSpinBox.ButtonSymbols.NoButtons:
            return                                  # düğmesiz kutu (DPI kartındaki değer)
        for sc, up in ((UP, True), (DOWN, False)):
            r = QRectF(self.subControlRect(CC.CC_SpinBox, opt, sc, widget))
            enabled = bool(opt.state & flags.State_Enabled) and bool(
                steps & (STEP.StepUpEnabled if up else STEP.StepDownEnabled))
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if enabled and opt.activeSubControls & sc and opt.state & (flags.State_MouseOver | flags.State_Sunken):
                hover = QColor(self._ink(opt, True))
                hover.setAlpha(60 if opt.state & flags.State_Sunken else 30)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hover)
                p.drawRoundedRect(r.adjusted(2, 3, -2, -3), 3, 3)
            pen = QPen(self._ink(opt, enabled), 1.3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            c, half, rise = r.center(), 4.0, 2.2
            path = QPainterPath()
            sign = -1 if up else 1                 # yukarı ok: tepe üstte
            path.moveTo(c.x() - half, c.y() - sign * rise)
            path.lineTo(c.x(), c.y() + sign * rise)
            path.lineTo(c.x() + half, c.y() - sign * rise)
            p.drawPath(path)
            p.restore()

    def _menu_lines(self, opt: QStyleOptionComboBox, p: QPainter, widget) -> None:
        r = QRectF(self.subControlRect(CC.CC_ComboBox, opt, SC.SC_ComboBoxArrow, widget))
        enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._ink(opt, enabled), 1.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        c = r.center()
        for dy in (-3.5, 0.0, 3.5):
            p.drawLine(QPointF(c.x() - 5, c.y() + dy), QPointF(c.x() + 5, c.y() + dy))
        p.restore()


def install() -> None:
    """Uygulamanın stilini HelperStyle ile sar (bir kez)."""
    app = QApplication.instance()
    if app is None or isinstance(app.style(), HelperStyle):
        return
    base = QStyleFactory.create(app.style().name())
    app.setStyle(HelperStyle(base))
