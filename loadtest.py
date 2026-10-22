#!/usr/bin/env python3
"""Load test for dfilt: mixes allowed and blacklisted queries and reports results.

Usage: ./loadtest.py --clients 100 --requests 5000
"""
import argparse, os, random, selectors, socket, struct, time

GOOD = ["example.com", "google.com", "github.com", "wikipedia.org", "debian.org",
        "cloudflare.com", "kernel.org", "mozilla.org", "python.org", "rust-lang.org"]


def query(qid, name):
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    return header + qname + struct.pack(">HH", 1, 1)


def load_bad(path, n=100):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(line)
            if len(out) == n:
                break
    return out


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=10, help="concurrent clients (one query in flight each)")
    ap.add_argument("--requests", type=int, default=100, help="total queries to send")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--timeout", type=float, default=4.0, help="seconds before a query counts as timed out")
    ap.add_argument("--bad-ratio", type=float, default=0.75, help="share of blacklisted queries")
    ap.add_argument("--blacklist", default=os.path.join(root, "data", "blacklist.txt"))
    args = ap.parse_args()

    bad = load_bad(args.blacklist)
    sel = selectors.DefaultSelector()
    clients = []
    for i in range(args.clients):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(False)
        s.connect((args.host, args.port))
        sel.register(s, selectors.EVENT_READ, i)
        clients.append(s)

    stats = {k: {"ok": 0, "wrong": 0, "timeout": 0, "lat": []} for k in ("good", "bad")}
    inflight = {}  # client index -> (kind, qid, msg, sent_at)
    idle = list(range(args.clients))
    sent = 0
    start = time.perf_counter()

    while sent < args.requests or inflight:
        while idle and sent < args.requests:
            i = idle.pop()
            kind = "bad" if random.random() < args.bad_ratio else "good"
            qid = random.randint(0, 0xFFFF)
            msg = query(qid, random.choice(bad if kind == "bad" else GOOD))
            try:
                clients[i].send(msg)
            except (BlockingIOError, ConnectionRefusedError):
                idle.append(i)
                break
            inflight[i] = (kind, qid, msg, time.perf_counter())
            sent += 1

        for key, _ in sel.select(0.01):
            i = key.data
            while True:
                try:
                    data = key.fileobj.recv(1500)
                except (BlockingIOError, ConnectionRefusedError):
                    break
                if i not in inflight:
                    continue
                kind, qid, msg, t = inflight.pop(i)
                st = stats[kind]
                if struct.unpack(">H", data[:2])[0] == qid and msg[12:-4] in data:
                    st["ok"] += 1
                    st["lat"].append((time.perf_counter() - t) * 1000)
                else:
                    st["wrong"] += 1
                idle.append(i)

        now = time.perf_counter()
        for i in [i for i, v in inflight.items() if now - v[3] > args.timeout]:
            stats[inflight.pop(i)[0]]["timeout"] += 1
            idle.append(i)

    elapsed = time.perf_counter() - start
    print(f"requests={args.requests} clients={args.clients} elapsed={elapsed:.1f}s")
    for kind, st in stats.items():
        lat = sorted(st["lat"])
        n = st["ok"] + st["wrong"] + st["timeout"]
        pct = lambda f: f"{lat[min(int(len(lat) * f), len(lat) - 1)]:.0f}" if lat else "-"
        print(f"{kind:4} n={n} ok={st['ok']} wrong={st['wrong']} timeout={st['timeout']} "
              f"latency ms p50={pct(.5)} p99={pct(.99)} max={pct(1)}")


if __name__ == "__main__":
    main()
