import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.webview_settings import apply_kernel_preferences


class FakeFunc:
    def __class_getitem__(cls, item):
        return lambda callback: callback


class FakeNative:
    def __init__(self, core):
        self.core = core
        self.in_ui_thread = False
        self.core_read_contexts = []
        self.invoke_count = 0
        self.webview = self

    @property
    def CoreWebView2(self):
        self.core_read_contexts.append(self.in_ui_thread)
        return self.core

    def Invoke(self, callback):
        self.invoke_count += 1
        self.in_ui_thread = True
        try:
            callback()
        finally:
            self.in_ui_thread = False


class KernelPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            AreDefaultContextMenusEnabled=False,
            AreBrowserAcceleratorKeysEnabled=False,
        )
        self.core = SimpleNamespace(Settings=self.settings)
        self.native = FakeNative(self.core)
        self.window = SimpleNamespace(native=self.native)
        self.enterContext(patch.dict(sys.modules, {
            'System': SimpleNamespace(Func=FakeFunc, Type=type),
        }))
        self.light_scheme = self.enterContext(patch('app.webview_settings._apply_light_color_scheme'))
        self.menu_filter = self.enterContext(patch('app.webview_settings._subscribe_menu_filter'))

    def test_core_is_only_read_on_ui_thread(self):
        self.assertTrue(apply_kernel_preferences(self.window))
        self.assertEqual(self.native.core_read_contexts, [True])
        self.assertEqual(self.native.invoke_count, 1)
        self.assertTrue(self.settings.AreDefaultContextMenusEnabled)
        self.assertTrue(self.settings.AreBrowserAcceleratorKeysEnabled)
        self.light_scheme.assert_called_once_with(self.core)
        self.menu_filter.assert_called_once_with(self.core)

    def test_initializing_core_is_checked_on_ui_thread_and_can_be_retried(self):
        self.native.core = None
        self.assertFalse(apply_kernel_preferences(self.window))
        self.assertEqual(self.native.core_read_contexts, [True])
        self.light_scheme.assert_not_called()
        self.menu_filter.assert_not_called()
        self.native.core = self.core
        self.assertTrue(apply_kernel_preferences(self.window))
        self.assertEqual(self.native.core_read_contexts, [True, True])

    def test_optional_accelerator_keys_remain_disabled(self):
        self.assertTrue(apply_kernel_preferences(self.window, accelerator_keys=False))
        self.assertTrue(self.settings.AreDefaultContextMenusEnabled)
        self.assertFalse(self.settings.AreBrowserAcceleratorKeysEnabled)

    def test_window_not_created_yet(self):
        self.assertFalse(apply_kernel_preferences(SimpleNamespace(native=None)))
        self.assertFalse(apply_kernel_preferences(SimpleNamespace()))

    def test_unsupported_backend(self):
        self.assertFalse(apply_kernel_preferences(SimpleNamespace(native=object())))
        self.native.webview = None
        self.assertFalse(apply_kernel_preferences(self.window))
        self.menu_filter.assert_not_called()

    def test_missing_settings(self):
        self.native.core = SimpleNamespace(Settings=None)
        self.assertFalse(apply_kernel_preferences(self.window))
        self.menu_filter.assert_not_called()

    def test_disposed_window_returns_false(self):
        self.native.Invoke = Mock(side_effect=RuntimeError('window disposed'))
        with self.assertLogs(level='ERROR'):
            self.assertFalse(apply_kernel_preferences(self.window))
        self.menu_filter.assert_not_called()


if __name__ == '__main__':
    unittest.main()
