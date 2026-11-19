import socket
import sys

from midi_send import *
from lib_osc import osc_string

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem
)


OSC_HOST = "127.0.0.1"
OSC_PORT = 8001

SHADERS = {
    "Blob": "blob",
    "Gradient": "shader",
}

TOGGLE_STATES = {True: "on", False: ""}

ENABLE_MIDI = False


class ShaderListWidget(QListWidget):
    activateCurrentItem = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            self.activateCurrentItem.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ShaderMenu(QWidget):
    def __init__(self):
        super().__init__()

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active_shader = None

        self.setWindowTitle("Shader menu")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(680, 420)
        self.setStyleSheet(
            "QWidget { background-color: #000; color: #fff; }"
            "QListWidget { border: 0; }"
            "QListWidget::item { padding: 0 6px; }"
            "QListWidget::item:selected { background-color: #555; color: #fff; }"
            "QListWidget QWidget { background-color: transparent; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title = QLabel("SHADER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #fff; font-size: 9pt;")
        layout.addWidget(title)

        self.shader_list = ShaderListWidget()
        self.shader_list.setSpacing(3)

        self.status_labels: dict[str, QLabel] = {}
        for label, name in SHADERS.items():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)
            row = self._create_row(label, name, False)
            self.shader_list.addItem(item)
            item.setSizeHint(row.sizeHint())
            self.shader_list.setItemWidget(item, row)

        self.shader_list.itemActivated.connect(self.activate_item)
        self.shader_list.currentRowChanged.connect(self.update_selected_row)
        layout.addWidget(self.shader_list)
        self.shader_list.setCurrentRow(0)

        if ENABLE_MIDI:
            midi_handler = MidiHandler(MIDI_INPUT_INDEX)
            midi_handler.open_midi_input()

            self.midi_timer = QTimer(self)
            self.midi_timer.timeout.connect(self.read_midi)
            self.midi_timer.start(5)

    def update_selected_row(self, selected_row: int):
        for row_index in range(self.shader_list.count()):
            row = self.shader_list.itemWidget(self.shader_list.item(row_index))
            background = "#555" if row_index == selected_row else "transparent"
            row.setStyleSheet(f"background-color: {background};")

    def _create_row(self, label, name, state: bool):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(label))
        row_layout.addStretch()
        status = QLabel(TOGGLE_STATES[state])
        status.setObjectName("activeStatus")
        self.status_labels[name] = status
        row_layout.addWidget(status)
        return row

    def activate_item(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        if self.active_shader == name:
            self.status_labels[name].setText("")
            self.active_shader = None
            self.send_shader("reset")
            return

        if self.active_shader is not None:
            self.status_labels[self.active_shader].setText("")

        self.active_shader = name
        self.status_labels[name].setText(TOGGLE_STATES[True])
        self.send_shader(name)

    def send_shader(self, name):
        packet = osc_string("/shader") + osc_string(",s") + osc_string(name)
        self.udp_socket.sendto(packet, (OSC_HOST, OSC_PORT))


    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if ENABLE_MIDI:
            self.midi_timer.stop()
            self.midi_input.close()
        self.udp_socket.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    menu = ShaderMenu()

    screen_geometry = app.primaryScreen().availableGeometry()
    x_position = (screen_geometry.width() - menu.width()) // 2
    y_position = screen_geometry.height() - menu.height() - 18
    menu.move(screen_geometry.x() + x_position, screen_geometry.y() + y_position)
    menu.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
