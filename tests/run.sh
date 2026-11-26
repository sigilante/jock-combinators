#!/bin/zsh
#  tests/run.sh: compile and run tests/vectors.jock with the Jock toolchain,
#  decode the list of Strings it returns, and diff it against
#  tests/vectors.expected.  Exit 0 iff they match.
#  Env:  JOCK (default ~/Code/jock), and HONK/KICK as Jock's tools/vex.sh.
set -e
HERE="${0:A:h}"; ROOT="${HERE:h}"
JOCK="${JOCK:-$HOME/Code/jock}"
OUT=$(cd "$JOCK" && zsh tools/jockc.sh --data-dir "$ROOT" run "$HERE/vectors.jock" 2>&1 | tail -1)
GOT=$(print -r -- "$OUT" | python3 -c '
import re, sys
toks = re.findall(r"\(|\)|,|\d+", sys.stdin.read())
pos = 0
def noun():
    global pos
    t = toks[pos]; pos += 1
    if t == "(":
        items = [noun()]
        while toks[pos] == ",":
            pos += 1; items.append(noun())
        pos += 1
        out = items[-1]
        for it in reversed(items[:-1]): out = (it, out)
        return out
    return int(t)
n = noun()
while n != 0:
    a, n = n
    print(a.to_bytes((a.bit_length() + 7) // 8, "little").decode("utf-8"))
')
if diff <(print -r -- "$GOT") "$HERE/vectors.expected"; then
  echo "vectors: $(wc -l < "$HERE/vectors.expected" | tr -d ' ') pass"
else
  echo "vectors: MISMATCH (above: < got, > expected)"; exit 1
fi
