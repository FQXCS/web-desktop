import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.controller import AppController
from app.service import WebServiceError


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.controller = AppController({'web_url': 'http://127.0.0.1:3080'})
        self.loaded = threading.Event()
        self.window = Mock(events=SimpleNamespace(loaded=self.loaded))
        self.controller._window = self.window
        self.service_class = self.enterContext(patch('app.controller.WebServiceManager'))
        self.service = self.service_class.return_value
        self.wait_loop = self.enterContext(patch.object(self.controller, '_wait_loop'))

    def test_service_waits_for_initial_page_before_starting(self):
        attempted_wait = threading.Event()
        original_wait = self.loaded.wait

        def wait(timeout=None):
            attempted_wait.set()
            return original_wait(timeout)

        self.loaded.wait = wait
        worker = threading.Thread(target=self.controller.start)
        worker.start()
        try:
            self.assertTrue(attempted_wait.wait(1))
            self.service.start.assert_not_called()
            self.window.load_html.assert_not_called()
            self.loaded.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.service.start.assert_called_once()
            self.window.load_html.assert_called_once()
        finally:
            self.controller.stop_event.set()
            self.loaded.set()
            worker.join(1)

    def test_close_while_waiting_does_not_start_service(self):
        def close_during_wait(timeout):
            self.controller.stop_event.set()
            return False

        self.loaded.wait = Mock(side_effect=close_during_wait)
        self.controller.start()
        self.loaded.wait.assert_called()
        self.service_class.assert_not_called()
        self.window.load_html.assert_not_called()

    def test_config_mode_does_not_wait_or_start_service(self):
        self.controller._config_mode = True
        self.loaded.wait = Mock()
        self.controller.start()
        self.loaded.wait.assert_not_called()
        self.service_class.assert_not_called()

    def test_immediate_failure_is_shown_after_initial_page(self):
        self.loaded.set()
        self.service.start.side_effect = WebServiceError('missing executable')
        self.controller.start()
        html = self.window.load_html.call_args.args[0]
        self.assertIn('服务启动失败', html)
        self.assertIn('missing executable', html)
        self.wait_loop.assert_not_called()

    def test_retry_stops_previous_service_and_restarts(self):
        self.loaded.set()
        previous_service = Mock()
        self.controller._service = previous_service
        self.controller.retry()
        previous_service.stop.assert_called_once()
        self.service.start.assert_called_once()
        self.assertIs(self.controller._service, self.service)


if __name__ == '__main__':
    unittest.main()
