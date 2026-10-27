# SPDX-License-Identifier: MIT
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ScheduleTests(unittest.TestCase):
 def test_delivery_and_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);binary=d/'check';good=d/'good';bad=d/'bad'
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(ROOT/'tests/keyboard_schedule_test.c'),'-o',str(binary)],check=True)
   good.write_text('0 0\n10 1\n20 2\n')
   for invalid in ('2 0\n1 1\n','0 256\n','-1 2\n','1 2 junk\n','2000000000 1\n','1 2','x 1\n'):
    bad.write_text(invalid);subprocess.run([str(binary),str(good),str(bad)],check=True,capture_output=True)
