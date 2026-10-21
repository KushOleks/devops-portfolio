import importlib.util
import tempfile
import unittest
from pathlib import Path

ANALYZER_PATH = Path(__file__).resolve().parents[1] / "log_analyzer.py"

spec = importlib.util.spec_from_file_location("log_analyzer", ANALYZER_PATH)
log_analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log_analyzer)


class TestLogAnalyzer(unittest.TestCase):
    def setUp(self):
        self.valid_line = (
            '192.168.1.10 - - [21/Oct/2026:09:15:30 +0300] '
            '"GET /index.html HTTP/1.1" 200 1024 "-" "Mozilla/5.0"'
        )

    def test_valid_log_line(self):
        result = log_analyzer.parse_log_line(self.valid_line)

        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.10")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["status_class"], "2xx")
        self.assertEqual(result["hour"], "2026-10-21 09:00 +0300")

    def test_invalid_log_line(self):
        result = log_analyzer.parse_log_line("INVALID LOG LINE")

        self.assertIsNone(result)

    def test_invalid_timestamp(self):
        invalid_line = self.valid_line.replace(
            "21/Oct/2026:09:15:30",
            "incorrect-date",
        )

        result = log_analyzer.parse_log_line(invalid_line)

        self.assertIsNone(result)

    def test_invalid_http_status(self):
        invalid_line = self.valid_line.replace(
            '" 200 1024',
            '" 999 1024',
        )

        result = log_analyzer.parse_log_line(invalid_line)

        self.assertIsNone(result)

    def test_analyze_log_with_invalid_lines(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "access.log"

            log_path.write_text(
                self.valid_line + "\n"
                + self.valid_line + "\n"
                + "INVALID LOG LINE\n",
                encoding="utf-8",
            )

            report = log_analyzer.analyze_log(log_path, top_n=3)

            self.assertEqual(report["total_lines"], 3)
            self.assertEqual(report["valid_lines"], 2)
            self.assertEqual(report["invalid_lines"], 1)
            self.assertEqual(report["top_ips"][0]["requests"], 2)
            self.assertEqual(report["status_classes"]["2xx"], 2)
            self.assertEqual(report["peak_hours"][0]["requests"], 2)

    def test_text_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "access.log"
            log_path.write_text(self.valid_line + "\n", encoding="utf-8")

            report = log_analyzer.analyze_log(log_path, top_n=5)
            text_report = log_analyzer.format_text_report(report)

            self.assertIn("ЗВІТ ПРО АНАЛІЗ", text_report)
            self.assertIn("192.168.1.10", text_report)
            self.assertIn("Пошкоджених рядків: 0", text_report)


if __name__ == "__main__":
    unittest.main()
