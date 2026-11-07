"""Bounded Rich dashboard showing measured process and execution telemetry."""
from __future__ import annotations
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
import psutil
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def sparkline(values):
    bars = '▁▂▃▄▅▆▇█'
    if not values:
        return ''
    lower, upper = min(values), max(values)
    return ''.join(bars[int((v - lower) / (upper - lower or 1) * 7)] for v in values)


@dataclass
class DashboardState:
    lark: str = 'starting'
    mode: str = 'idle'
    sandbox: str = 'unconfigured'
    events: deque = field(default_factory=lambda: deque(maxlen=256))
    memory: deque = field(default_factory=lambda: deque(maxlen=60))
    velocity: deque = field(default_factory=lambda: deque(maxlen=60))
    completed: int = 0
    rss_mb: float = 0

    def event(self, message):
        self.events.append((time.strftime('%H:%M:%S'), str(message)[:400]))


class VisualCLI:
    def __init__(self, state, optimizer, limit_mb=512):
        self.state, self.optimizer, self.limit_mb = state, optimizer, limit_mb
        self.process = psutil.Process()

    def sample(self):
        processes = [self.process] + self.process.children(recursive=True)
        memory = 0
        for process in processes:
            try:
                memory += process.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.state.rss_mb = memory / (1024 ** 2)
        self.state.memory.append(self.state.rss_mb)
        self.state.velocity.append(self.state.completed)
        return self.state.rss_mb

    def render(self):
        state, usage = self.state, self.optimizer.usage
        header = Panel(Text(f'Lark: {state.lark}   Mode: {state.mode}   E2B: {state.sandbox}'), title='SuperCraftOS')
        table = Table(expand=True)
        table.add_column('Input tokens'); table.add_column('Output tokens'); table.add_column('Estimated USD'); table.add_column('RSS / cap MB')
        table.add_row(str(usage['input_tokens']), str(usage['output_tokens']), f"${usage['cost_usd']:.6f}" + (" + unpriced" if usage.get("unpriced_requests") else ""), f'{state.rss_mb:.1f} / {self.limit_mb}')
        vector = Panel(Text(f'Planner → Builder → Approval → Delivery\nMemory   {sparkline(state.memory)}\nDelivered {sparkline(state.velocity)}'), title='Execution graph / measured history')
        stream = Text('\n'.join(f'{stamp}  {event}' for stamp, event in list(state.events)[-12:]) or 'Waiting for work')
        return Group(header, table, vector, Panel(stream, title='Tools and transitions'))

    async def run(self, enabled=True):
        if enabled:
            with Live(self.render(), refresh_per_second=2) as live:
                while True:
                    self.sample(); live.update(self.render()); await asyncio.sleep(0.5)
        else:
            while True:
                self.sample(); await asyncio.sleep(1)
