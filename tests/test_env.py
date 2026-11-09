from gymnasium.utils.env_checker import check_env

from chaos.env import ChaosEnv, summarize


class FakeOps:

    def __init__(self):
        self.active = {}

    def restore(self, services):
        self.active = {}

    def apply(self, service, fault):
        self.active[service] = fault

    def probe(self):
        broken = "auth" in self.active or self.active.get("cache") == "pause"
        return (1.0, 2.0) if broken else (0.0, 0.1)


def make():
    return ChaosEnv(ops=FakeOps())


def test_gymnasium_api():
    check_env(make(), skip_render_check=True)


def act(env, service, fault):
    return env.services.index(service) * len(env.faults) + env.faults.index(fault)


def test_breaking_fault_is_rewarded_and_ends_episode():
    env = make()
    env.reset()
    _, r_harmless, term, _, _ = env.step(act(env, "catalog", "latency"))
    assert r_harmless < 0 and not term
    _, r_break, term, _, _ = env.step(act(env, "auth", "pause"))
    assert r_break > 1 and term
    _, r_repeat, _, _, _ = env.step(act(env, "auth", "kill"))
    assert r_repeat < 0
    obs, _ = env.reset()
    assert env.ops.active == {} and obs[: env.n].sum() == 0


def test_summarize_ranks_minimal_breaking_combo_first():
    history = [
        {"faults": ["catalog:kill", "auth:kill"], "error_rate": 1.0, "p95": 2.0},
        {"faults": ["auth:pause"], "error_rate": 1.0, "p95": 2.0},
        {"faults": ["cache:kill"], "error_rate": 0.0, "p95": 1.2},
        {"faults": ["catalog:latency"], "error_rate": 0.0, "p95": 0.4},
    ]
    ranking = summarize(history)
    assert ranking[0]["faults"] == ["auth:pause"]
    assert [r["fragile"] for r in ranking] == [True, True, True, False]


def test_ppo_runs_on_fake():
    from stable_baselines3 import PPO

    PPO("MlpPolicy", make(), n_steps=64, batch_size=32).learn(128)
