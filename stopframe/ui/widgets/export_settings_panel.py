"""Compact export preferences beside the review tab's logo switch."""
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from stopframe.config import Settings, save_settings


class ExportSettingsPanel(QFrame):
    changed = Signal()

    def __init__(self, settings: Settings, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.settings = settings
        self.setObjectName('exportSettingsPopup')
        self.setWindowTitle('Параметры экспорта')
        self.setFixedWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QLabel('Параметры экспорта')
        title.setProperty('class', 'section-label')
        layout.addWidget(title)
        form = QFormLayout()
        form.setSpacing(10)
        self.prefix_edit = QLineEdit(settings.export_prefix)
        self.prefix_edit.setPlaceholderText('Без префикса')
        self.prefix_edit.setToolTip('Для фотографий при пустом префиксе используется logo')
        form.addRow('Префикс', self.prefix_edit)
        self.prefix_position_combo = QComboBox()
        self.prefix_position_combo.addItems(['Перед именем', 'После имени'])
        self.prefix_position_combo.setCurrentIndex(0 if settings.prefix_before_name else 1)
        form.addRow('Положение', self.prefix_position_combo)
        self.format_combo = QComboBox()
        self.format_combo.addItems(['PNG', 'JPEG'])
        self.format_combo.setCurrentText(settings.export_format)
        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(settings.jpeg_quality)
        self.jpeg_quality_spin.setSuffix('%')
        self.jpeg_quality_spin.setAccessibleName('Качество JPEG')
        self.jpeg_quality_spin.setEnabled(settings.export_format == 'JPEG')
        format_row = QHBoxLayout()
        format_row.addWidget(self.format_combo)
        format_row.addWidget(QLabel('Качество'))
        format_row.addWidget(self.jpeg_quality_spin)
        form.addRow('Формат', format_row)
        layout.addLayout(form)
        done = QPushButton('Готово')
        done.clicked.connect(self.hide)
        layout.addWidget(done, alignment=Qt.AlignmentFlag.AlignRight)
        self.prefix_edit.textChanged.connect(self._on_prefix_changed)
        self.prefix_position_combo.currentIndexChanged.connect(self._on_position_changed)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        self.jpeg_quality_spin.valueChanged.connect(self._on_quality_changed)

    def button_text(self) -> str:
        quality = f' · {self.settings.jpeg_quality}%' if self.settings.export_format == 'JPEG' else ''
        return f'Параметры · {self.settings.export_format}{quality}'

    def show_for(self, button: QPushButton) -> None:
        self.adjustSize()
        position = button.mapToGlobal(QPoint(button.width() - self.width(), button.height() + 6))
        available = button.screen().availableGeometry()
        position.setX(max(available.left(), min(position.x(), available.right() - self.width() + 1)))
        position.setY(max(available.top(), min(position.y(), available.bottom() - self.height() + 1)))
        self.move(position)
        self.show()
        self.prefix_edit.setFocus()

    def _save(self) -> None:
        save_settings(self.settings)
        self.changed.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _on_prefix_changed(self, value: str) -> None:
        self.settings.export_prefix = value
        self._save()

    def _on_position_changed(self, index: int) -> None:
        self.settings.prefix_before_name = index == 0
        self._save()

    def _on_format_changed(self, value: str) -> None:
        self.settings.export_format = value
        self.jpeg_quality_spin.setEnabled(value == 'JPEG')
        self._save()

    def _on_quality_changed(self, value: int) -> None:
        self.settings.jpeg_quality = value
        self._save()
