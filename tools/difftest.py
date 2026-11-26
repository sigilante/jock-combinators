#!/usr/bin/env python3
"""Differential test: combinator.jock against the Aviary kernel's reducer.

Generates random terms over the aviary birds plus free variables x, y, z,
reduces each under normal order with Aviary ($AVIARY), writes a Jock program
that reduces the same terms with combinator.jock, runs it, and
compares the normal form, the step count and the halting status case by case.

Usage:  python3 tools/difftest.py [N] [SEED] [FUEL]
Env:    AVIARY  (default ~/Code/urbit/aviary)   JOCK (default ~/Code/jock)

Theta and A are absent from Aviary's table, so the generator never
produces them (Aviary's Θ is the alias `U U`, which takes an extra step
per unfolding); tests/vectors.jock covers both.  Terms that grow past
MAXSIZE leaves in Aviary are dropped and counted.  Aviary reports FUEL once
the step count reaches the budget, so a Jock result counts as normal only
if it is done AND finished inside the budget.
"""
import os, random, re, subprocess, sys, tempfile

AVIARY = os.path.expanduser(os.environ.get("AVIARY", "~/Code/urbit/aviary"))
JOCK = os.path.expanduser(os.environ.get("JOCK", "~/Code/jock"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AVIARY)

from aviary_kernel.birds import BIRDS            # noqa: E402
from aviary_kernel.environment import Environment  # noqa: E402
from aviary_kernel.reduce import reduce, Status    # noqa: E402
from aviary_kernel.terms import Atom, App, pretty  # noqa: E402

# aviary canonical name -> our ASCII name
ASCII = {"Φ": "Phi", "Ψ": "Psi", "Ê": "E^"}
def ours(name): return ASCII.get(name, name)

MAXSIZE = 400   # atoms; larger terms are dropped, and counted
NAMES = [b.name for b in BIRDS]
VARS = ["x", "y", "z"]

def gen(rng, size):
    if size <= 1:
        if rng.random() < 0.3:
            return Atom(rng.choice(VARS))
        # bias toward the small classic birds so terms do interesting things
        pool = NAMES + ["S", "K", "I", "B", "C", "W", "M"] * 4
        return Atom(rng.choice(pool))
    left = rng.randint(1, size - 1)
    return App(gen(rng, left), gen(rng, size - left))

def show(t):
    return pretty(t, display=ours)

def decode_cord(n):
    b = n.to_bytes((n.bit_length() + 7) // 8, "little") if n else b""
    return b.decode("utf-8")

def parse_noun(s):
    """Parse jockc's printed noun: atoms and right-nested (a, b) cells."""
    toks = re.findall(r"\(|\)|,|\d+", s)
    pos = 0
    def noun():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            items = [noun()]
            while toks[pos] == ",":
                pos += 1; items.append(noun())
            assert toks[pos] == ")"; pos += 1
            # (a, b, c) is a right-nested cell
            out = items[-1]
            for it in reversed(items[:-1]):
                out = (it, out)
            return out
        return int(t)
    return noun()

def to_list(n):
    out = []
    while n != 0:
        out.append(n[0]); n = n[1]
    return out

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    fuel = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    rng = random.Random(seed)
    env = Environment()
    cases = []
    dropped = 0
    while len(cases) < n:
        t = gen(rng, rng.randint(2, 9))
        r = reduce(t, env, max_steps=fuel, max_size=MAXSIZE)
        if r.status == Status.SIZE:
            dropped += 1   # explosive growth: neither side should be asked to print it
            continue
        cases.append((show(t), show(r.term), r.steps, r.status == Status.NORMAL))

    lines = ["import combinator;", "let t = combinator.aviary();",
             "func run(t: List<combinator.Bird>, s: String) -> (String, @, Bool) {",
             "  match combinator.parse(t, s) {",
             f"    .ok(e) => {{ let r = combinator.nf(t, e, {fuel}); (combinator.show(r.expr), r.steps, r.done) }},",
             "    .bad(p) => (\"PARSE-ERROR\", p, false),",
             "  }",
             "};"]
    body = ", ".join(f'run(t, "{c[0]}")' for c in cases)
    lines.append(f"[{body}]")
    with tempfile.NamedTemporaryFile("w", suffix=".jock", delete=False, dir=os.environ.get("TMPDIR")) as f:
        f.write("\n".join(lines) + "\n")
        prog = f.name
    out = subprocess.run(["zsh", f"{JOCK}/tools/jockc.sh", "--data-dir", ROOT, "run", prog],
                         capture_output=True, text=True, cwd=JOCK)
    text = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if out.returncode != 0 or not text.startswith("("):
        print("jock run failed:\n", out.stdout[-2000:], out.stderr[-2000:]); sys.exit(2)
    # Jock Bool: %.y is 0.  Aviary reports FUEL once steps reach the budget,
    # even on a normal term, so a Jock result is NORMAL only if done AND
    # it finished inside the budget.
    got = [(decode_cord(a), b, c == 0 and b < fuel) for (a, (b, c)) in to_list(parse_noun(text))]
    bad = 0
    for (src, want, wsteps, wdone), (gt, gsteps, gdone) in zip(cases, got):
        if (want, wsteps, wdone) != (gt, gsteps, gdone):
            bad += 1
            if bad <= 15:
                print(f"MISMATCH {src}\n  aviary: {want} [{wsteps} {'nf' if wdone else 'fuel'}]\n  jock:   {gt} [{gsteps} {'nf' if gdone else 'fuel'}]")
    nf = sum(1 for c in cases if c[3])
    print(f"{len(cases)} cases (seed {seed}, fuel {fuel}; {nf} reach normal form; {dropped} dropped for size > {MAXSIZE}): {len(cases)-bad} agree, {bad} differ")
    os.unlink(prog)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
