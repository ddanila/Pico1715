# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess
import tempfile
import unittest


class ShutdownTests(unittest.TestCase):
    def test_production_service_shutdown_faults(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            binary = str(Path(directory) / 'shutdown-test')
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined', '-fno-sanitize-recover=all',
                            '-DP1715_HOST_SIM', '-Itools/firmware_host',
                            'tests/shutdown_test.c', 'firmware/service.c', 'firmware/store.c',
                            'model/controller.c', 'tools/firmware_host/host_hal.c',
                            '-o', binary], cwd=root, check=True)
            subprocess.run([binary], check=True, timeout=30)
