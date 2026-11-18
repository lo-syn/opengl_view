import socket
import struct
import sys

import mido
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
MIDI_INPUT_INDEX = 16
MIDI_CC_TO_OSC = {
    0: "/u_x0",
    1: "/u_x1",
    2: "/u_x2",
}
SHADERS = {
    "Blob": "blob",
    "Gradient": "shader",
}

TOGGLE_STATES = {True: "on", False: ""}


def osc_string(value):
    encoded = value.encode("utf-8") + b"\0"
    return encoded + b"\0" * (-len(encoded) % 4)


def osc_float(address, value):
    return osc_string(address) + osc_string(",f") + struct.pack(">f", value)


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
        midi_ports = mido.get_input_names()
        if MIDI_INPUT_INDEX >= len(midi_ports):
            port_list = "\n".join(
                f"{index}: {name}" for index, name in enumerate(midi_ports)
            ) or "(no MIDI input ports found)"
            raise RuntimeError(
                f"MIDI input index {MIDI_INPUT_INDEX} is unavailable. "
                f"Available inputs:\n{port_list}"
            )

        self.midi_input = mido.open_input(midi_ports[MIDI_INPUT_INDEX])
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active_shader = None

        self.setWindowTitle("Shader menu")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(460, 142)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title = QLabel("SHADER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #a0aec0; font-size: 9pt;")
        layout.addWidget(title)

        self.shader_list = ShaderListWidget()
        self.shader_list.setSpacing(2)
        #self.shader_list.setStyleSheet(
        #    "QListWidget { background: transparent; border: 0; }"
        #    "QListWidget::item { padding: 3px 6px; }"
        #)

        self.status_labels: dict[str, QLabel] = {}
        for label, name in SHADERS.items():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)
            row = self._create_row(label, name, False)
            self.shader_list.addItem(item)
            item.setSizeHint(row.sizeHint())
            self.shader_list.setItemWidget(item, row)

        self.shader_list.itemActivated.connect(self.activate_item)
        layout.addWidget(self.shader_list)
        self.shader_list.setCurrentRow(0)

        self.midi_timer = QTimer(self)
        self.midi_timer.timeout.connect(self.read_midi)
        self.midi_timer.start(5)

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

    def read_midi(self):
        for message in self.midi_input.iter_pending():
            if message.type != "control_change":
                continue
            address = MIDI_CC_TO_OSC.get(message.control)
            if address is None:
                continue
            value = message.value / 127.0
            packet = osc_float(address, value)
            self.udp_socket.sendto(packet, (OSC_HOST, OSC_PORT))

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
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
