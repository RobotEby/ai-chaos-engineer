from collections import defaultdict

import gymnasium as gym
import numpy as np

from chaos import docker_ops


class ChaosEnv(gym.Env):
    def __init__(
        self,
        ops=docker_ops,
        services=("auth", "catalog", "cache"),
        faults=docker_ops.FAULTS,
        max_steps=3,
        fault_cost=0.1,
        slo=1.0,
    ):
        self.ops, self.services, self.faults = ops, list(services), list(faults)
        self.max_steps, self.fault_cost, self.slo = max_steps, fault_cost, slo
        self.n = len(self.services) * len(self.faults)
        self.action_space = gym.spaces.Discrete(self.n + 1)
        self.observation_space = gym.spaces.Box(0.0, 1.0, (self.n + 2,), np.float32)
        self.history = []
        self.active = {}

    def _impact(self):
        return self.err + min(self.p95 / self.slo, 1.0)

    def _obs(self):
        flags = [
            float(self.active.get(s) == f) for s in self.services for f in self.faults
        ]
        return np.array(flags + [self.err, min(self.p95 / self.slo, 1.0)], np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.ops.restore(self.services)
        self.active, self.steps = {}, 0
        self.err, self.p95 = self.ops.probe()
        return self._obs(), {}

    def step(self, action):
        action = int(action)
        self.steps += 1
        if action == self.n:
            return self._obs(), 0.0, True, False, {}
        service, fault = (
            self.services[action // len(self.faults)],
            self.faults[action % len(self.faults)],
        )
        if service in self.active:
            return (
                self._obs(),
                -self.fault_cost,
                False,
                self.steps >= self.max_steps,
                {},
            )
        before = self._impact()
        self.ops.apply(service, fault)
        self.active[service] = fault
        self.err, self.p95 = self.ops.probe()
        self.history.append(
            {
                "faults": sorted(f"{s}:{f}" for s, f in self.active.items()),
                "error_rate": self.err,
                "p95": self.p95,
            }
        )
        reward = self._impact() - before - self.fault_cost
        broken = self.err >= 0.5
        return self._obs(), reward, broken, self.steps >= self.max_steps, {}

    def close(self):
        self.ops.restore(self.services)


def summarize(history, slo=1.0):
    groups = defaultdict(list)
    for h in history:
        groups[tuple(h["faults"])].append(h)
    rows = [
        {
            "faults": list(k),
            "error_rate": round(sum(h["error_rate"] for h in v) / len(v), 3),
            "p95": round(sum(h["p95"] for h in v) / len(v), 3),
            "samples": len(v),
        }
        for k, v in groups.items()
    ]
    for r in rows:
        r["fragile"] = r["error_rate"] >= 0.5 or r["p95"] >= slo
    return sorted(rows, key=lambda r: (-r["error_rate"], len(r["faults"]), -r["p95"]))
