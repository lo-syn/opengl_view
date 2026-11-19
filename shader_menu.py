import socket
import sys

from midi_send import MidiHandler, MIDI_INPUT_INDEX
from lib_osc import osc_string, OSC_HOST, OSC_PORT
from schema import DefaultMenuItem, ShaderMenuItem, SettingsMenuItem

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QListWidget,
    QListWidgetItem,
)


TOGGLE_STATES = {True: "on", False: ""}

# Default trigger states
ENABLE_MIDI = False


class DefaultListWidget(QListWidget):
    # Create navigateable list widget
    activateCurrentItem = pyqtSignal()
    navigateRight = pyqtSignal()
    navigateLeft = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
         # Handle key events for activating items and navigating
        if event.key() == Qt.Key.Key_Space:
            item = self.currentItem()
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                super().keyPressEvent(event)
            else:
                self.activateCurrentItem.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.navigateRight.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Left:
            self.navigateLeft.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class DefaultMenu(QWidget):
    def __init__(self):
        super().__init__()

        self.shaders = {"Blob": ShaderMenuItem(on_state_msg="on"),
           "Gradient": ShaderMenuItem(on_state_msg="on")}

        self.settings = {"enable_midi": SettingsMenuItem(on_state_msg="enabled", off_state_msg="disabled", linked_function=self.set_midi_enabled)}

        # Setup UDP socket to send OSC messages to openFrameworks application
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active_shader = None

        self.setWindowTitle("Default menu")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # Change window size to match desired dimensions (e.g. 680x420)
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

        # Setup label for the title of the current menu
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #fff; font-size: 9pt;")
        layout.addWidget(self.title)

        self.list_widget = DefaultListWidget()
        self.list_widget.setSpacing(3)

        # Connect actions to functions
        self.status_labels: dict[str, QLabel] = {}
        #self.list_widget.activateCurrentItem.connect(self.activate_current_item)
        self.list_widget.itemActivated.connect(self.activate_item)
        self.list_widget.currentRowChanged.connect(self.update_selected_row)

        self.list_widget.navigateRight.connect(self.show_settings)
        self.list_widget.navigateLeft.connect(self.show_shaders)

        layout.addWidget(self.list_widget)

        self.message_bar = QLabel()
        self.message_bar.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.message_bar.setWordWrap(True)
        self.message_bar.setMinimumHeight(28)
        self.message_bar.setStyleSheet(
            "QLabel { background-color: #222; color: #fff; padding: 4px 6px; }"
        )
        layout.addWidget(self.message_bar)

        self.current_page = "shaders"
        self.midi_handler = None
        self.midi_timer = None

        # Show shader menu by default
        self.show_shaders()

        #if ENABLE_MIDI:
        #    self.set_midi_enabled(True)

    def update_selected_row(self, selected_row: int):
        self.clear_message()
        for row_index in range(self.list_widget.count()):
            row = self.list_widget.itemWidget(self.list_widget.item(row_index))
            if row is not None:
                background = "#555" if row_index == selected_row else "transparent"
                row.setStyleSheet(f"background-color: {background};")

    def _populate_menu(self, menu_items: dict[str, DefaultMenuItem]):
        # Populates selected list widget with menu items
        for name, menu_item in menu_items.items():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, name)
            row = self._create_row(name, menu_item)
            self.list_widget.addItem(item)
            item.setSizeHint(row.sizeHint())
            self.list_widget.setItemWidget(item, row)

    def show_shaders(self):
        self.clear_message()
        # Show shader menu
        self.current_page = "shaders"
        self.title.setText("SHADER")
        self.list_widget.clear()
        self._populate_menu(self.shaders)
        self.list_widget.setCurrentRow(0)

    def show_settings(self):
        self.clear_message()
        # Show settings menu
        self.current_page = "settings"
        self.title.setText("SETTINGS")
        self.list_widget.clear()
        self._populate_menu(self.settings)
        self.list_widget.setCurrentRow(0)

    def clear_message(self):
        self.message_bar.clear()

    '''
    def activate_current_item(self):
        item = self.list_widget.currentItem()
        if item is not None:
            self.activate_item(item)
    '''
    def set_midi_enabled(self, enabled: bool) -> bool:
        if enabled:
            if self.midi_handler is not None:
                self.status_labels["enable_midi"].setText("enabled")
            try:
                midi_handler = MidiHandler(MIDI_INPUT_INDEX)
                midi_handler.open_midi_input()
            except Exception as error:
                self.status_labels["enable_midi"].setText("disabled")
                self.message_bar.setText(f"Could not enable MIDI: {error}")
                return False

            self.midi_handler = midi_handler
            self.midi_timer = QTimer(self)
            self.midi_timer.timeout.connect(self.midi_handler.read_midi)
            self.midi_timer.start(5)

            return True

        if self.midi_timer is not None:
            self.midi_timer.stop()
            self.midi_timer = None
        if self.midi_handler is not None:
            self.midi_handler.close_midi_input()
            self.midi_handler = None
        return False

    def _create_row(self, name: str, menu_item: DefaultMenuItem):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(name))
        row_layout.addStretch()
        if menu_item.state:
            status = QLabel(menu_item.on_state_msg)
        else:
            status = QLabel(menu_item.off_state_msg)
        status.setObjectName("activeStatus")
        self.status_labels[name] = status
        row_layout.addWidget(status)
        return row

    def _run_settings_option(self, name: str):
        if name not in self.settings.keys():
            raise ValueError("Attempting to run missing setting")
        current_setting: SettingsMenuItem = self.settings[name]
        current_state = current_setting.state
        state = current_setting.linked_function(not current_state)
        current_setting.state = state
        if state:
            self.status_labels[name].setText(current_setting.on_state_msg)
        else:
            self.status_labels[name].setText(current_setting.off_state_msg)

    def _run_shader_option(self, name: str):
        if name not in self.shaders.keys():
            raise ValueError("Attempting to run missing shader")
        current_shader: ShaderMenuItem = self.shaders[name]
        current_state = current_shader.state
        
        return

    def activate_item(self, item):
        self.clear_message()
        name = item.data(Qt.ItemDataRole.UserRole)
        if self.current_page == "settings":
            self._run_settings_option(name)
            return
        if self.current_page == "shaders":
            self._run_shader_option(name)
            return
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
        self.set_midi_enabled(False)
        self.udp_socket.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    menu = DefaultMenu()

    screen_geometry = app.primaryScreen().availableGeometry()
    x_position = (screen_geometry.width() - menu.width()) // 2
    y_position = screen_geometry.height() - menu.height() - 18
    menu.move(screen_geometry.x() + x_position, screen_geometry.y() + y_position)
    menu.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
