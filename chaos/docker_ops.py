import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PROJECT = "chaos-target"
FAULTS = ("kill", "pause", "latency")
GATEWAY = "http://127.0.0.1:18080/"


def _docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=check
    ).stdout.strip()


def container(service):
    ids = _docker(
        "ps",
        "-aq",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
        "--filter",
        f"label=com.docker.compose.service={service}",
    ).split()
    if len(ids) != 1:
        raise RuntimeError(
            f"esperava 1 container de {PROJECT}/{service}, achei {len(ids)}"
        )
    return ids[0]


def apply(service, fault):
    c = container(service)
    if fault == "kill":
        _docker("stop", "-t", "0", c)
    elif fault == "pause":
        _docker("pause", c)
    elif fault == "latency":
        _docker(
            "exec",
            c,
            "tc",
            "qdisc",
            "add",
            "dev",
            "eth0",
            "root",
            "netem",
            "delay",
            "300ms",
        )
    else:
        raise ValueError(fault)


def restore(services):
    for s in services:
        c = container(s)
        status = _docker("inspect", "-f", "{{.State.Status}}", c)
        if status == "paused":
            _docker("unpause", c)
        elif status != "running":
            _docker("start", c)
        _docker("exec", c, "tc", "qdisc", "del", "dev", "eth0", "root", check=False)
    wait_ready()


def _one(timeout):
    t = time.monotonic()
    try:
        with urllib.request.urlopen(GATEWAY, timeout=timeout) as r:
            ok = r.status == 200
    except Exception:
        ok = False
    return ok, (time.monotonic() - t if ok else timeout)


def probe(n=10, timeout=2.0):
    with ThreadPoolExecutor(n) as ex:
        results = list(ex.map(lambda _: _one(timeout), range(n)))
    lat = sorted(l for _, l in results)
    return sum(not ok for ok, _ in results) / n, lat[min(n - 1, int(0.95 * n))]


def wait_ready(seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _one(2.0)[0]:
            return
        time.sleep(0.5)
    raise RuntimeError(f"gateway {GATEWAY} não respondeu em {seconds}s")
