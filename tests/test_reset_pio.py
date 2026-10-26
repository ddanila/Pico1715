# SPDX-License-Identifier: MIT
"""Execute the actual reset PIO source's instruction subset, without CPU service."""
from collections import deque
from pathlib import Path
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]


class PulsePIO:
    def __init__(self):
        self.code, self.labels = [], {}
        self.pc = self.x = self.osr = self.pin = self.ticks = 0
        self.fifo = deque()
        for raw in (ROOT / 'firmware/reset_pulse.pio').read_text().splitlines():
            line = raw.split(';')[0].strip()
            if not line or line.startswith('.'):
                continue
            if line.endswith(':'):
                self.labels[line[:-1]] = len(self.code)
            else:
                self.code.append(line)

    def step(self):
        instruction = self.code[self.pc]
        nxt = (self.pc + 1) % len(self.code)
        if instruction == 'pull block':
            if self.fifo:
                self.osr = self.fifo.popleft()
            else:
                nxt = self.pc
        elif instruction == 'mov x, osr':
            self.x = self.osr
        elif instruction.startswith('set pins, '):
            self.pin = int(instruction.rsplit(' ', 1)[1])
        elif instruction.startswith('jmp x-- '):
            if self.x:
                nxt = self.labels[instruction.split()[-1]]
            self.x = (self.x - 1) & 0xffffffff
        else:
            raise AssertionError(f'Unsupported PIO instruction: {instruction}')
        self.pc = nxt
        self.ticks += 1


class ResetPIOTests(unittest.TestCase):
    def test_idle_single_pulse_and_no_retrigger_without_cpu(self):
        pio = PulsePIO()
        for _ in range(100):
            pio.step()
        self.assertEqual(pio.pin, 0)
        source = (ROOT / 'firmware/analyzer_main.c').read_text()
        count = int(re.search(r'pio_sm_put\(pio0,reset_sm,(\d+)u\)', source).group(1))
        pio.fifo.append(count)
        edges = []
        # CPU does nothing throughout this interval; only PIO instructions execute.
        for _ in range(300000):
            old = pio.pin
            pio.step()
            if pio.pin != old:
                edges.append((pio.ticks, pio.pin))
        self.assertEqual([value for _, value in edges], [1, 0])
        self.assertEqual(edges[1][0] - edges[0][0], 100000)
        self.assertEqual(pio.pin, 0)
        self.assertFalse(pio.fifo)


if __name__ == '__main__':
    unittest.main()
