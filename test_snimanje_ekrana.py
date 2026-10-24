import subprocess
import unittest
from unittest.mock import call, patch

import snimanje_ekrana


class RecordScreenTests(unittest.TestCase):
    @patch("snimanje_ekrana.subprocess.run")
    @patch("snimanje_ekrana.shutil.which", return_value="/usr/bin/adb")
    def test_records_pulls_and_cleans_up_using_selected_device(self, _which, run):
        with patch.object(snimanje_ekrana.Path, "exists", return_value=False), patch.object(
            snimanje_ekrana.Path, "mkdir"
        ):
            snimanje_ekrana.record_screen("capture.mp4", duration=30, serial="device-1")

        commands = [item.args[0] for item in run.call_args_list]
        self.assertEqual(commands[0][:3], ["/usr/bin/adb", "-s", "device-1"])
        self.assertEqual(commands[0][3:7], ["shell", "screenrecord", "--time-limit", "30"])
        self.assertEqual(commands[1][:4], ["/usr/bin/adb", "-s", "device-1", "pull"])
        self.assertEqual(commands[1][-1], "capture.mp4")
        self.assertEqual(commands[2][:5], ["/usr/bin/adb", "-s", "device-1", "shell", "rm"])
        self.assertFalse(run.call_args_list[-1].kwargs["check"])

    def test_rejects_duration_outside_adb_limit(self):
        with self.assertRaises(ValueError):
            snimanje_ekrana.record_screen("capture.mp4", duration=181)

    @patch("snimanje_ekrana.shutil.which", return_value=None)
    def test_requires_adb(self, _which):
        with self.assertRaisesRegex(RuntimeError, "adb was not found"):
            snimanje_ekrana.record_screen("capture.mp4")


if __name__ == "__main__":
    unittest.main()
