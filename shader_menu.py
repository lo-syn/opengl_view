import sys
import logging

from browser import BrowserHandler
from midi_handler import MidiHandler
from osc_handler import OscHandler, OSC_HOST, OSC_PORT, osc_string
from audio_handler import AudioHandler
from bluetooth_audio import BluetoothAudioManager
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

logger = logging.getLogger(__name__)


class DefaultListWidget(QListWidget):
    # Create navigateable list widget
    activateCurrentItem = pyqtSignal(QListWidgetItem)
    navigateRight = pyqtSignal()
    navigateLeft = pyqtSignal()
    closeRequested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
         # Handle key events for activating items and navigating
        if event.key() == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.currentItem()
            if item is not None:
                self.activateCurrentItem.emit(item)
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

        self.shaders = {"blob": ShaderMenuItem(on_state_msg="on"),
           "shader": ShaderMenuItem(on_state_msg="on")}

        self.settings = {
            "enable_midi": SettingsMenuItem(
                on_state_msg="enabled",
                off_state_msg="disabled",
                linked_function=self.set_midi_enabled,
            ),
            "enable_audio": SettingsMenuItem(
                on_state_msg="bluetooth",
                off_state_msg="disabled",
                linked_function=self.set_audio_enabled,
            ),
        }

        # Add handlers
        self.browser_handler = BrowserHandler()
        self.osc_handler = OscHandler()
        self.audio_handler = None
        self.active_shader = None

        # Audio mode state: 0=disabled, 1=bluetooth, 2=audio_file
        self.audio_mode = 0
        self.bluetooth_audio_handler = None
        self.file_audio_handler = None

        # Prevent automatic Bluetooth audio passthrough on startup
        self._prevent_bluetooth_passthrough()

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

        self.status_bar = QLabel()
        self.status_bar.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.status_bar.setMinimumHeight(28)
        self.status_bar.setStyleSheet(
            "QLabel { background-color: #222; color: #fff; padding: 4px 6px; }"
        )
        layout.addWidget(self.status_bar)
        self.update_active_shader_status()

        self.list_widget = DefaultListWidget()
        self.list_widget.setSpacing(3)

        # Connect actions to functions
        self.status_labels: dict[str, QLabel] = {}
        self.list_widget.activateCurrentItem.connect(self.activate_item)
        self.list_widget.currentRowChanged.connect(self.update_selected_row)

        self.list_widget.navigateRight.connect(self.navigate_right)
        self.list_widget.navigateLeft.connect(self.navigate_left)
        self.list_widget.closeRequested.connect(self.close)

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

    def show_browser(self):
        self.clear_message()
        # Show browser menu
        self.current_page = "browser"
        self.title.setText("BROWSER")
        try:
            self.browser_handler.populate(self.list_widget)
        except OSError as error:
            self._update_message(f"Could not read browser directory: {error}")
            return
        self.list_widget.setCurrentRow(0)

    def navigate_right(self):
        if self.current_page == "shaders":
            self.show_settings()
        elif self.current_page == "settings":
            self.show_browser()

    def navigate_left(self):
        if self.current_page == "browser":
            self.show_settings()
        elif self.current_page == "settings":
            self.show_shaders()

    def clear_message(self):
        self.message_bar.clear()

    def update_active_shader_status(self):
        # Add active shader to status bar
        shader_name = self.active_shader if self.active_shader is not None else ""
        self.status_bar.setText(f"Active Shader: {shader_name}")

    def _prevent_bluetooth_passthrough(self) -> None:
        """Prevent automatic Bluetooth audio passthrough on application startup.
        
        This ensures:
        1. Bluetooth input is NOT captured at startup
        2. Audio doesn't automatically route to Bluetooth when devices connect
        3. Bluetooth mode can only be enabled by explicit user action
        """
        try:
            manager = BluetoothAudioManager()
            manager.prevent_automatic_passthrough()
            manager.disable_all_bluetooth_audio()
            logger.info("Bluetooth audio disabled on startup - Bluetooth mode must be explicitly enabled")
        except OSError:
            # Bluetooth not available on this system
            logger.debug("Bluetooth audio not available, passthrough prevention skipped")
        except Exception as e:
            # Log but don't fail - passthrough prevention is non-critical
            logger.warning(f"Could not initialize Bluetooth passthrough prevention: {e}")

    def set_midi_enabled(self, enabled: bool) -> bool:
        if enabled:
            if self.midi_handler is not None:
                self.status_labels["enable_midi"].setText("enabled")
            try:
                midi_handler = MidiHandler(self.osc_handler)
                midi_handler.open_midi_input()
            except Exception as error:
                self.status_labels["enable_midi"].setText("disabled")
                self._update_message(f"Could not enable MIDI: {error}")
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

    def set_audio_enabled(self, enabled: bool) -> bool:
        """
        Cycle through audio modes:
        - Disabled (0) → Bluetooth (1) → Audio File (2) → Disabled (0)
        
        When enabled=True, advance to next mode.
        When enabled=False, go to disabled mode.
        
        When switching away from Bluetooth mode, all Bluetooth audio passthrough is disabled.
        When switching to Bluetooth mode, Bluetooth audio passthrough is enabled.
        """
        try:
            # Track previous mode to disable Bluetooth if leaving Bluetooth mode
            previous_mode = self.audio_mode
            
            if not enabled:
                # Disable all audio modes
                self._stop_all_audio()
                # If we were in Bluetooth mode, disable all Bluetooth audio passthrough
                if previous_mode == 1:
                    self._disable_bluetooth_passthrough()
                self.audio_mode = 0
                return False
            
            # Cycle to next audio mode: 0 → 1 → 2 → 0
            self.audio_mode = (self.audio_mode + 1) % 3
            
            if self.audio_mode == 1:
                # Switch to Bluetooth mode
                self._stop_all_audio()
                if self.bluetooth_audio_handler is None:
                    self.bluetooth_audio_handler = AudioHandler(
                        self.osc_handler,
                        enable_bluetooth=True
                    )
                
                # Scan for available devices without blocking
                self._update_message("Scanning for Bluetooth devices...")
                devices = self.bluetooth_audio_handler.scan_bluetooth_devices()
                
                if not devices:
                    self._update_message("No Bluetooth devices found")
                    # Reset to disabled mode if no devices found
                    self.audio_mode = 0
                    return False
                
                # Try to reconnect to saved device first
                if self.bluetooth_audio_handler.load_bluetooth_config():
                    self._update_message("Reconnected to saved device")
                    self.bluetooth_audio_handler.play()
                    return True
                
                # No saved device, show user available devices in UI
                # Don't auto-connect - let user select which device to use
                device_names = [f"{dev.name} ({dev.mac_address})" for dev in devices]
                self._update_message(f"Found devices: {', '.join(device_names[:2])}")
                logger.info(f"Found {len(devices)} Bluetooth devices: {device_names}")
                
                # For now, just show the available devices without connecting
                # User can pair their device first if needed
                return True
            
            elif self.audio_mode == 2:
                # Switch to File audio mode (disable Bluetooth if coming from Bluetooth mode)
                self._stop_all_audio()
                if previous_mode == 1:
                    self._disable_bluetooth_passthrough()
                if self.file_audio_handler is None:
                    self.file_audio_handler = AudioHandler(self.osc_handler)
                self.file_audio_handler.play()
                return True
            
            else:  # audio_mode == 0
                # Disabled (disable Bluetooth if coming from Bluetooth mode)
                self._stop_all_audio()
                if previous_mode == 1:
                    self._disable_bluetooth_passthrough()
                return False
                
        except (ImportError, FileNotFoundError) as error:
            # Only catch setup errors, not connection errors
            self._stop_all_audio()
            self.audio_mode = 0
            self._update_message(f"Could not enable audio: {error}")
            return False
    
    def _stop_all_audio(self):
        """Stop all audio handlers."""
        if self.bluetooth_audio_handler is not None:
            try:
                self.bluetooth_audio_handler.stop()
            except Exception:
                pass
        if self.file_audio_handler is not None:
            try:
                self.file_audio_handler.stop()
            except Exception:
                pass

    def _disable_bluetooth_passthrough(self) -> None:
        """Disable all Bluetooth audio passthrough.
        
        This prevents any Bluetooth device from receiving audio until explicitly re-enabled.
        Called when switching away from Bluetooth audio mode to ensure clean state.
        """
        try:
            manager = BluetoothAudioManager()
            manager.disable_all_bluetooth_audio()
            logger.info("All Bluetooth audio passthrough disabled")
        except OSError:
            # Bluetooth not available on this system - this is fine
            logger.debug("Bluetooth audio not available, passthrough disable skipped")
        except Exception as e:
            # Log but don't fail - disabling passthrough is non-critical
            logger.warning(f"Could not disable Bluetooth passthrough: {e}")

    def _update_message(self, text: str) -> None:
        """Update message bar text and immediately refresh the GUI """
        self.message_bar.setText(text)
        QApplication.processEvents()

    def _create_row(self, name: str, menu_item: DefaultMenuItem):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(name))
        row_layout.addStretch()
        
        # Special handling for audio mode display
        if name == "enable_audio":
            audio_mode_names = ["disabled", "bluetooth", "audio_file"]
            status = QLabel(audio_mode_names[self.audio_mode])
        elif menu_item.state:
            status = QLabel(menu_item.on_state_msg)
        else:
            status = QLabel(menu_item.off_state_msg)
        
        status.setObjectName("activeStatus")
        self.status_labels[name] = status
        row_layout.addWidget(status)
        return row

    def _run_settings_option(self, name: str):
        if name not in self.settings.keys():
            self._update_message("Attempting to run missing setting")
            return
        current_setting: SettingsMenuItem = self.settings[name]
        current_state = current_setting.state
        
        # Special handling for audio mode cycling - always advance mode
        if name == "enable_audio":
            # For audio, we always pass True to cycle through modes
            # We never toggle off/on, we just cycle through 3 modes
            state = current_setting.linked_function(True)
            
            # Always keep button state as True (we're in audio mode selection)
            # This ensures next press advances to next mode, not toggles back
            current_setting.state = True
            
            # Update label with current mode name
            audio_mode_names = ["disabled", "bluetooth", "audio_file"]
            mode_name = audio_mode_names[self.audio_mode]
            self.status_labels[name].setText(mode_name)
        else:
            # Normal toggle for other settings
            state = current_setting.linked_function(not current_state)
            current_setting.state = state
            
            if state:
                self.status_labels[name].setText(current_setting.on_state_msg)
            else:
                self.status_labels[name].setText(current_setting.off_state_msg)

    def _run_shader_option(self, name: str):
        if name not in self.shaders.keys():
            self._update_message("Attempting to run missing shader")
            return
        current_shader: ShaderMenuItem = self.shaders[name]
        # Reset if already active
        if self.active_shader == name:
            current_shader.state = False
            self.status_labels[name].setText(current_shader.off_state_msg)
            self.active_shader = None
            self.update_active_shader_status()
            self.send_shader("reset")
            return
        # Set off message for previous shader
        if self.active_shader is not None:
            previous_shader = self.shaders[self.active_shader]
            previous_shader.state = False
            self.status_labels[self.active_shader].setText(previous_shader.off_state_msg)

        # Set active shader
        self.active_shader = name
        self.update_active_shader_status()
        current_shader.state = True
        self.status_labels[name].setText(current_shader.on_state_msg)
        self.send_shader(name)

    def activate_item(self, item):
        self.clear_message()
        name = item.data(Qt.ItemDataRole.UserRole)
        if self.current_page == "settings":
            self._run_settings_option(name)
            return
        if self.current_page == "shaders":
            self._run_shader_option(name)
            return
        if self.current_page == "browser":
            try:
                self.browser_handler.toggle_directory(self.list_widget, item)
            except OSError as error:
                self._update_message(f"Could not read directory: {error}")
            return

    def send_shader(self, name):
        packet = osc_string("/shader") + osc_string(",s") + osc_string(name)
        self.osc_handler.udp_socket.sendto(packet, (OSC_HOST, OSC_PORT))

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Clean up all resources on application exit.
        
        CRITICAL: Disable Bluetooth audio input before exiting.
        This ensures Bluetooth input is not passed through after app closes.
        """
        logger.info("Application closing - cleaning up resources...")
        
        # Stop all audio playback
        self.set_midi_enabled(False)
        self._stop_all_audio()
        
        # Disable Bluetooth audio input on exit - prevent passthrough after app closes
        self._disable_bluetooth_passthrough()
        logger.info("Bluetooth audio disabled on exit")
        
        # Close OSC socket
        self.osc_handler.udp_socket.close()
        
        super().closeEvent(event)


def main():
    # Configure logging to show all debug messages
    # Set level to INFO for production, DEBUG for troubleshooting
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
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
