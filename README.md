# AI Chaos Engineer

Agente de Reinforcement Learning (PPO, stable-baselines3) que injeta falhas em containers Docker reais,
mede o impacto no sistema e aprende quais falhas - e combinações - o derrubam.

## Como funciona
- `target/` - sistema-alvo de exemplo (gateway → auth, catalog → cache) com fragilidades plantadas.
- `chaos/docker_ops.py` - falhas `kill`, `pause`, `latency` (tc netem 300ms) e `probe` (10 GETs paralelos no gateway).
  Só toca containers do projeto compose `chaos-target`.
- `chaos/env.py` - `ChaosEnv` (Gymnasium). Ação = (serviço, falha) ou parar. Recompensa = aumento de
  `erro + p95/SLO` menos custo por falha; o episódio termina quando o sistema cai, então o agente aprende a
  **menor** combinação que quebra o sistema.
- `train.py` - sobe o alvo, treina, avalia e grava o ranking de pontos frágeis em `findings.json`.

## Uso
```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                       # testes sem Docker
.venv/bin/python train.py --steps 2000    # ~2.5s por passo em Docker real
```
O alvo é restaurado ao fim (e no Ctrl+C). Gateway em `127.0.0.1:18080`.

Para atacar outro sistema compose: mude `PROJECT`/`GATEWAY` em `chaos/docker_ops.py` e `services` em `ChaosEnv`
(as imagens precisam de `iproute2` e `cap_add: NET_ADMIN` para a falha de latência).
