# jock-combinators

Combinatory logic for [Jock](https://jock.is): terms, Smullyan's birds, and
reduction. The library is one module, `combinator.jock`, with no dependencies
beyond Jock's prelude.

```jock
import combinator;

let t = combinator.aviary();
match combinator.parse(t, "S K K x") {
  .ok(e) => combinator.show(combinator.nf(t, e, 1000).expr),   // "x"
  .bad(p) => "parse error",
}
```

## Install

Jock has no package system yet, so install by copying. Put `combinator.jock`
in a directory and pass that directory to the compiler as a data dir:

```
zsh ~/Code/jock/tools/jockc.sh --data-dir path/to/dir run program.jock
zsh ~/Code/jock/tools/kern.sh  --data-dir path/to/dir kernel.jock out.jam
```

Then `import combinator;`. The module name is the file name.

## What it provides

### Terms

```jock
enum Expr { sym(String), free(String), app(Expr, Expr) };
```

A term is a named combinator (`sym`), a free variable (`free`), or an
application. Application is binary and left-nested, so `S x y z` is
`app(app(app(S, x), y), z)`. Two terms are equal exactly when `===` says so.
There are no binders, so there is no alpha-renaming to worry about.

| function | does |
|---|---|
| `ap(f, a)`, `sym(n)`, `free(n)` | build terms |
| `apply(h, args)` | `h a1 a2 ...`, left-nested |
| `spine(e)` | the head and its arguments: `Spine { head, args }` |
| `size(e)` | atoms in the term (names and variables) |
| `occurs(x, e)` | whether variable `x` occurs in `e` |

### Birds

```jock
enum Tpl { arg(@), bird(String), ap(Tpl, Tpl) };
struct Bird { name: String, title: String, arity: @, rhs: Tpl };
```

A bird is a rule `X a1 ... an = rhs`. Its right-hand side is a template
over argument slots, and it may name birds, including the bird itself,
which is how a recursive bird such as `Y` is written. A table is a plain
`List<Bird>`.

| function | does |
|---|---|
| `aviary()` | the whole table (below) |
| `ski()`, `bckw()` | the classic bases |
| `select(tbl, names)` | the rows of `tbl` named in `names` |
| `find(tbl, n)` | `Lookup.hit(bird)` or `Lookup.miss` |
| `rule(name, title, arity, rhs)` | a bird from text: `rule("B", "Bluebird", 3, "a (b c)")`. Arguments are `a`, `b`, `c`, … in order. A malformed rule crashes, because rules are written by programmers. |
| `describe(b)` | the rule as text: `"S a b c = a c (b c)"` |

**`aviary()`** holds 52 birds. Fifty come from the Aviary kernel's table,
which uses Smullyan's and Rathman's names. They are B, B1, B2, B3, C, C\*, C\*\*, D, D1,
D2, E, E^, F, F\*, F\*\*, G, H, I, I\*, I\*\*, J, K, Ki, KM, KM', L, M, M2, O,
Phi, Psi, Q, Q1–Q4, R, R\*, R\*\*, S, T, U, V, V\*, V\*\*, W, W\*, W\*\*, W', Y.
Two more are added:

- **`Theta`**, Turing's fixed point, as a primitive: `Theta a = a (Theta a)`.
  Y has the same rule. The two differ only in what they abbreviate, which
  matters to `expand`.
- **`A = S S S`**, an *abbreviation*. Its arity is 0, so it unfolds in
  place as soon as reduction reaches it, and nowhere else.

**Names are ASCII.** Unicode string literals are not yet reliable through
every Jock toolchain lane, so Θ is `Theta`, Φ is `Phi`, Ψ is `Psi` and Ê is
`E^`. A front end can map names to glyphs.

### Reduction

| function | does |
|---|---|
| `headStep(tbl, e)` | one contraction of the head redex: `Step.next(e')` or `Step.stuck` |
| `step(tbl, e)` | one contraction of the leftmost-outermost redex (normal order) |
| `whnf(tbl, e, fuel)` | reduce to weak head normal form, in at most `fuel` steps |
| `nf(tbl, e, fuel)` | reduce to normal form under normal order, in at most `fuel` steps |
| `trace(tbl, e, fuel)` | every term from `e` onward under normal order, starting with `e` |
| `fire(b, args)` | contract `b` applied to exactly `b.arity` arguments |

A redex is a bird applied to at least its arity of arguments. Extra
arguments stay applied: `K a b c` contracts to `a c`. Normal order finds a
normal form whenever one exists, so `K x (M M)` halts.

`whnf` and `nf` return `Run { expr, steps, done }`. `done` is true when the
term is in (weak head) normal form, and false when fuel ran out first. The
Aviary kernel instead reports FUEL whenever the step count reaches the
budget, even if the term is normal by then. To compare with it, treat a
result as normal iff `done` and `steps < fuel`.

### Text

| function | does |
|---|---|
| `show(e)` | minimal parentheses, space-separated: `S K (K I)`. It parses back. |
| `tight(e)` | no spaces: `SK(KI)`. This is unambiguous only for one-letter names. |
| `parse(tbl, s)` | `Parsed.ok(e)`, or `Parsed.bad(n)` with the byte offset of the first error |

The parser matches bird names longest first against the table, so `KM'` is
one bird and `K M'` is two tokens. A lowercase letter, optionally followed
by digits or primes, is a free variable: `x`, `x1`, `f'`. An unknown name
becomes an inert `sym` that no rule fires on.

### Bracket abstraction

| function | does |
|---|---|
| `abstract(x, e)` | `[x] e` into S/K/I, with the K and eta optimisations |
| `expand(tbl, e)` | rewrite every bird into S/K/I: `Expansion.ok(e')` or `Expansion.cyclic(name)` |

`Y` expands to Curry's `S (K (S I I)) (S (S (K S) K) (K (S I I)))`, and
`Theta` to Turing's `U U`. Any other bird whose rule names itself is
`cyclic`. A rule that names *other* birds, like `A = S S S`, expands them
in turn. A table whose rules name each other in a cycle would make
`expand` run forever.

### Spine-preserving contraction

`fireSpine(b, args)` contracts a redex but keeps each argument as one item,
where ordinary contraction would re-associate it into the result. With
`x = K I`, `S x y z` gives the items `[(K I), z, (y z)]`, not
`[K, I, z, (y z)]`. `unfold(tpl, args, atom, group)` does the same over
*any* item type. A client whose items are not `Expr`s, such as a game that
keeps holes and bracket groups, can apply the table's rules without
converting its items. Ordinary reduction never needs either function.

## Testing

```
zsh tests/run.sh                     # 26 vectors: reduction, rules, expansion, parsing
python3 tools/difftest.py 200 1 100  # random terms against the Aviary kernel
```

`tools/difftest.py` generates random terms over the Aviary birds and free
variables. It reduces each one with the Aviary kernel (`$AVIARY`, default
`~/Code/urbit/aviary`) and with this module, then compares the normal form,
the step count and the status. `Theta` and `A` are left out, because Aviary
defines `Θ` as the alias `U U`, which takes an extra step per unfolding.
The vectors cover both instead.

Results so far (2026-11-26):
- **Random terms:** 410 of 410 agree, over four seeds at fuel ≤ 100.
- **Benchmark sample:** 222 rows of a stratified sample of the
  `combinator-benchmarks` manifests agree on status, step count and normal
  form. The sample covers the SKI, SK, BCKW and native-bird families, in
  both `nf` and `whnf` modes. Rows needing more than 600 steps, or with
  terms over 400 characters, were not run.

## Limits

- **Speed.** Reduction is plain term rewriting with no sharing. Under
  interpreted Nock it suits terms of hundreds of atoms and thousands of
  steps, not millions.
- **No size guard.** `nf` bounds steps but not term size. A term that grows
  exponentially can exhaust memory before it exhausts fuel.
- **Lookups are linear.** Each step finds its bird by scanning the table.
  The full aviary has 52 rows.

## Provenance

This module was written for Combinatrix, a falling-block game in which
combinators reduce. The game is inspired by Dirk van Deun's
[Combinatris](https://dirk.rave.org/combinatris/).
