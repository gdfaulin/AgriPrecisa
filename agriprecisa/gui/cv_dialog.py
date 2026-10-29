# -*- coding: utf-8 -*-
"""
AgriPrecisa: result of the IDW cross-validation (RMSE table by power P and radius).
"""

import math

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QHeaderView, QAbstractItemView,
)

from ..i18n import tr, fmt

from ..core.idw_math import CV_POWERS, CV_MULTIPLES  # noqa: E402  (shared with the core)
BEST_COLOR = QColor(166, 217, 106)      # light green of the RdYlGn ramp


def significant_decimals(values, digits=3):
    """Decimals that show ``digits`` significant digits for the smallest finite value."""
    finite = [abs(float(v)) for v in values.ravel() if v == v and v != 0]
    if not finite:
        return 2
    return max(2, digits - 1 - int(math.floor(math.log10(min(finite)))))


class CrossValidationDialog(QDialog):
    linkActivated = pyqtSignal(str)

    def __init__(self, parent, attribute, rmse, coverage, spacing, best, best_power,
                 n_val, exclusion, mean, map_coverage=None):
        super().__init__(parent)
        self.setWindowTitle(tr("cv_title"))
        self.resize(720, 620)
        i, j = best
        best_rmse = float(rmse[i, j])
        pct = abs(best_rmse / mean * 100) if mean else float("nan")
        mult = CV_MULTIPLES[j]

        header = QLabel(tr("cv_header", attribute=attribute, n=fmt(n_val),
                           exclusion=fmt(exclusion, 1), spacing=fmt(spacing)))
        header.setWordWrap(True)

        table = QTableWidget(len(CV_POWERS), len(CV_MULTIPLES))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setHorizontalHeaderLabels(
            [tr("cv_col", mult=fmt(m, 1), radius=fmt(m * spacing)) for m in CV_MULTIPLES])
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        decimals = significant_decimals(rmse)
        table.setVerticalHeaderLabels([tr("p3_power_value", p=fmt(p, 1)) for p in CV_POWERS])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r in range(len(CV_POWERS)):
            for c in range(len(CV_MULTIPLES)):
                v = rmse[r, c]
                cov = coverage[r, c]
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    item = QTableWidgetItem(tr("cv_na"))
                    item.setToolTip(tr("cv_na_tip"))
                else:
                    item = QTableWidgetItem(fmt(float(v), decimals))
                    item.setToolTip(tr("cv_cell_tip", cov=fmt(cov * 100)))
                    if cov < 0.95:
                        item.setForeground(QColor(150, 150, 150))
                    if map_coverage is not None and map_coverage[c] < 0.99:
                        item.setForeground(QColor(150, 150, 150))
                        item.setToolTip(tr("cv_gap_tip", gap=fmt((1 - map_coverage[c]) * 100, 1)))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if (r, c) == (i, j):
                    font = QFont(item.font())
                    font.setBold(True)
                    item.setFont(font)
                    item.setBackground(BEST_COLOR)
                table.setItem(r, c, item)
        table.resizeRowsToContents()
        table.horizontalHeader().setMinimumHeight(2 * table.fontMetrics().height() + 8)
        rows_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
        table.setMinimumHeight(table.horizontalHeader().minimumHeight() + rows_h + 6)

        best_label = QLabel(tr("cv_best", p=fmt(best_power, 1), mult=fmt(mult, 1),
                               radius=fmt(mult * spacing), rmse=fmt(best_rmse, decimals),
                               pct=fmt(pct, 1)))
        best_label.setWordWrap(True)
        explain = QLabel(tr("cv_explain") + f'  <a href="cv_more">{tr("learn_more")}</a>')
        explain.setWordWrap(True)
        explain.linkActivated.connect(self.linkActivated.emit)

        buttons = QDialogButtonBox()
        buttons.addButton(tr("cv_apply"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr("cv_close"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        axes = QLabel(tr("cv_axes"))
        axes.setEnabled(False)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(axes)
        layout.addWidget(table, 1)
        layout.addWidget(best_label)
        layout.addWidget(explain)
        layout.addWidget(buttons)

        self.table = table
        self.result_summary = {"power": best_power, "multiple": mult, "rmse": best_rmse}
