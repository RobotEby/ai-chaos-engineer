import argparse
import atexit
import json
import subprocess

from stable_baselines3 import PPO

from chaos import docker_ops
from chaos.env import ChaosEnv, summarize


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--steps",
        type=int,
        default=2000,
        help="passos de treino (cada um ~1-3s em Docker real)",
    )
    p.add_argument(
        "--episodes",
        type=int,
        default=5,
        help="episódios de avaliação do agente treinado",
    )
    p.add_argument("--out", default="findings.json")
    args = p.parse_args()

    subprocess.run(
        ["docker", "compose", "-f", "target/docker-compose.yml", "up", "-d", "--build"],
        check=True,
    )
    docker_ops.wait_ready()
    env = ChaosEnv()
    atexit.register(docker_ops.restore, env.services)

    model = PPO("MlpPolicy", env, n_steps=64, batch_size=32, verbose=1)
    model.learn(args.steps)

    attacks = []
    for _ in range(args.episodes):
        obs, _ = env.reset()
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, term, trunc, _ = env.step(action)
            done = term or trunc
        attacks.append(env.history[-1] if env.history else None)

    ranking = summarize(env.history, env.slo)
    with open(args.out, "w") as f:
        json.dump({"learned_attack": attacks[-1], "ranking": ranking}, f, indent=2)

    print(f"\nAtaque aprendido pelo agente: {attacks[-1]}")
    print(f"\n{'falhas':45} {'erro':>6} {'p95(s)':>7}  frágil")
    for r in ranking[:15]:
        print(
            f"{' + '.join(r['faults']):45} {r['error_rate']:6.0%} {r['p95']:7.2f}  {'SIM' if r['fragile'] else ''}"
        )
    print(f"\nRelatório completo em {args.out}")


if __name__ == "__main__":
    main()
