import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from schema import ShaderItem, ShaderPackItem
from shader_menu import DefaultListWidget, DefaultMenu


class ShaderPackMenuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.menu = DefaultMenu.__new__(DefaultMenu)
        QWidget.__init__(self.menu)
        self.menu.shader_packs = {
            "pack1": ShaderPackItem(shaders={"shared": ShaderItem(on_state_msg="on")}),
            "pack2": ShaderPackItem(shaders={"shared": ShaderItem(on_state_msg="on")}),
        }
        self.menu.active_shader_pack = None
        self.menu.active_shader = None
        self.menu.active_shader_owner = None
        self.menu.status_labels = {}
        self.menu.shader_status_labels = {}
        self.menu.list_widget = DefaultListWidget()
        self.menu.title = QLabel()
        self.menu.status_bar = QLabel()
        self.menu.message_bar = QLabel()
        self.menu.settings = {}
        self.menu.send_shader = Mock()
        self.menu.send_shader_pack = Mock()
        self.menu.show_shaders()

    def tearDown(self):
        self.menu.list_widget.clear()
        self.menu.deleteLater()

    def activate(self, row):
        self.menu.activate_item(self.menu.list_widget.item(row))

    def names(self):
        return [
            self.menu.list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.menu.list_widget.count())
        ]

    def test_packs_remain_open_and_shaders_select_their_own_pack(self):
        self.activate(0)
        self.activate(2)
        self.assertEqual(self.names(), ["pack1", "shared", "pack2", "shared"])

        self.activate(1)
        self.menu.send_shader_pack.assert_called_with("pack1")
        self.menu.send_shader.assert_called_with("shared")
        self.activate(3)
        self.menu.send_shader_pack.assert_called_with("pack2")
        self.menu.send_shader.assert_called_with("shared")
        self.assertFalse(self.menu.shader_packs["pack1"].shaders["shared"].state)
        self.assertTrue(self.menu.shader_packs["pack2"].shaders["shared"].state)
        self.assertEqual(self.menu.shader_status_labels[("pack1", "shared")].text(), "")
        self.assertEqual(self.menu.shader_status_labels[("pack2", "shared")].text(), "on")

        self.activate(0)
        self.assertEqual(self.names(), ["pack1", "pack2", "shared"])
        self.assertTrue(self.menu.shader_packs["pack2"].state)
        self.activate(2)
        self.menu.send_shader.assert_called_with("reset")

    def test_collapsed_active_shader_can_be_reopened_or_replaced(self):
        self.activate(0)
        self.activate(1)
        self.activate(0)
        self.activate(1)
        self.activate(2)
        self.assertFalse(self.menu.shader_packs["pack1"].shaders["shared"].state)
        self.activate(0)
        self.assertEqual(self.menu.shader_status_labels[("pack1", "shared")].text(), "")
        self.assertEqual(self.menu.shader_status_labels[("pack2", "shared")].text(), "on")

    def test_shader_named_like_a_pack_is_not_a_pack_header(self):
        self.menu.shader_packs["pack1"].shaders["pack2"] = ShaderItem(on_state_msg="on")
        self.activate(0)
        self.activate(2)
        self.menu.send_shader.assert_called_with("pack2")
        self.assertFalse(self.menu.shader_packs["pack2"].state)


if __name__ == "__main__":
    unittest.main()
