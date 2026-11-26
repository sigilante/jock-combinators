# jock-combinators

Combinatory logic for [Jock](https://jock.is), a language that compiles to
Nock. The module covers terms, Smullyan's birds, normal-order reduction,
parsing, and bracket abstraction. It is a single file, `combinator.jock`,
with no dependencies beyond Jock's prelude.

```jock
import combinator;

let t = combinator.aviary();
match combinator.parse(t, "S K K x") {
  .ok(e) => combinator.show(combinator.nf(t, e, 1000).expr),   // "x"; fuel: at most 1000 steps
  .bad(p) => "parse error",
}
```

## Install

Jock has no package system yet, so install by copying. Put
`combinator.jock` in a directory and pass that directory to the Jock
compiler as a data dir. From your Jock checkout:

```
zsh tools/jockc.sh --data-dir path/to/dir run program.jock     # compile and run a program
zsh tools/kern.sh  --data-dir path/to/dir kernel.jock out.jam  # build a NockApp kernel
```

Then write `import combinator;`. The module name is the file name.

## Terms

```jock
enum Expr { sym(String), free(String), app(Expr, Expr) };
```

A term is one of three things: a named combinator (`sym`), a free variable
(`free`), or an application. Application is binary and left-nested, so
`S x y z` is `app(app(app(S, x), y), z)`. Equality is structural: `===`
compares terms. Terms have no binders, so they need no alpha-renaming.

| function | returns |
|---|---|
| `ap(f, a)`, `sym(n)`, `free(n)` | a term (constructors) |
| `apply(h, args)` | `h a1 a2 ...`, left-nested |
| `spine(e)` | the head and its arguments, as `Spine { head, args }` |
| `size(e)` | the number of leaves (names and variables) in `e` |
| `occurs(x, e)` | whether variable `x` occurs in `e` |

## Birds

```jock
enum Tpl { arg(@), bird(String), ap(Tpl, Tpl) };
struct Bird { name: String, title: String, arity: @, rhs: Tpl };
```

A bird is a rule `X a1 ... an = rhs`, and `title` holds its common name.
The right-hand side is a template (`Tpl`) over argument slots. It may name
other birds, or the bird itself, which is how a recursive bird such as `Y`
is written. A table is a plain `List<Bird>`.

| function | returns |
|---|---|
| `aviary()` | the full table (below) |
| `ski()`, `bckw()` | the classic bases |
| `select(tbl, names)` | the rows of `tbl` whose names are listed, in table order; unknown names are skipped |
| `find(tbl, n)` | the first row named `n`: `Lookup.hit(bird)` or `Lookup.miss` |
| `rule(name, title, arity, rhs)` | a bird from text, e.g. `rule("B", "Bluebird", 3, "a (b c)")` |
| `ruleIn(tbl, name, title, arity, rhs)` | the same, but the right-hand side may name the birds of `tbl` |
| `describe(b)` | the rule as text: `"S a b c = a c (b c)"` |

In a rule, the arguments are the letters `a`, `b`, `c`, … in order, each
below the arity. `rule` reads its right-hand side against no table, so a
multi-letter bird name splits into letters. Use `ruleIn` to name birds
such as `KM`. A rule is source code, not user input, so `rule` crashes on a
malformed rule (bad syntax, an argument out of range, a multi-letter
variable) instead of returning an error. Because `find` returns the first
match, a bird prepended to a table overrides one of the same name, and an
appended one does not.

**`aviary()`** holds 52 birds. Fifty come from the table of the
[Aviary](https://github.com/sigilante/aviary) Jupyter kernel for
combinatory logic, which uses Smullyan's and Rathman's names. They are B,
B1, B2, B3, C, C\*, C\*\*, D, D1, D2, E, E^, F, F\*, F\*\*, G, H, I, I\*,
I\*\*, J, K, Ki, KM, KM', L, M, M2, O, Phi, Psi, Q, Q1–Q4, R, R\*, R\*\*, S,
T, U, V, V\*, V\*\*, W, W\*, W\*\*, W' and Y. Two more are added:

- **`Theta`**, Turing's fixed point, as a primitive: `Theta a = a (Theta a)`.
  It has the same rule as `Y`. The two differ only in their S/K/I
  expansions (see [Bracket abstraction](#bracket-abstraction)).
- **`A = S S S`**, an *abbreviation*. Its arity is 0, so it unfolds to
  `S S S` wherever reduction reaches it.

Names are ASCII. Unicode string literals are not yet reliable through
every Jock toolchain, so Θ is `Theta`, Φ is `Phi`, Ψ is `Psi` and Ê is
`E^`. A front end can map names to glyphs.

## Reduction

A *redex* is a bird applied to at least as many arguments as its arity.
Contraction substitutes the first arguments into the rule and leaves the
rest applied: `K a b c` contracts to `a c`.

| function | returns |
|---|---|
| `headStep(tbl, e)` | one contraction of the head redex: `Step.next(e')` or `Step.stuck` |
| `step(tbl, e)` | one contraction of the leftmost-outermost redex (normal order) |
| `whnf(tbl, e, fuel)` | the weak head normal form, within `fuel` steps |
| `nf(tbl, e, fuel)` | the normal form under normal order, within `fuel` steps |
| `trace(tbl, e, fuel)` | the terms of the normal-order reduction of `e`, starting with `e`, at most `fuel` steps |
| `fire(b, args)` | the contractum of `b` on its first `b.arity` arguments |
| `inst(tpl, args)` | a template with its slots filled |

Normal order finds a normal form whenever one exists, so `K x (M M)` halts.
`fire` crashes on fewer than `b.arity` arguments and ignores any extra.

`whnf` and `nf` return `Run { expr, steps, done }`. `done` is true when
the term is in (weak head) normal form, and false when fuel ran out first.
Aviary instead reports FUEL whenever the step count reaches the budget,
even if the term is normal by then. To compare with Aviary, treat a result
as normal exactly when `done` and `steps < fuel`.

## Text

| function | returns |
|---|---|
| `show(e)` | the term with minimal parentheses, space-separated: `S K (K I)` |
| `tight(e)` | the same without spaces: `SK(KI)`; unambiguous only for one-letter names |
| `render(e, sep)` | the same with any separator |
| `parse(tbl, s)` | `Parsed.ok(e)`, or `Parsed.bad(n)` with the byte offset of the first error |

The parser reads left to right. At each position:
- it takes the longest bird name in the table, so `KM'` is one bird and
  `K M` is two;
- failing that, a lowercase letter, optionally followed by digits or
  primes, is a variable: `x`, `x1`, `f'`;
- any other character becomes a one-character name that no rule fires on.

An unknown multi-letter name therefore splits: with `aviary()`, `Foo`
parses as Finch applied to `o` and `o`. A name the table lacks splits the
same way: `Ki x` is Kite applied to `x` with `aviary()`, but `K i x` with
`ski()`. Only unbalanced parentheses and empty input are errors. `show`
output parses back to the same term with the same table, provided the
term's names came from that parser.

## Bracket abstraction

| function | returns |
|---|---|
| `abstract(x, e)` | `[x] e` compiled to S/K/I, with the K and eta optimisations |
| `expand(tbl, e)` | `e` with its birds rewritten into S/K/I: `Expansion.ok(e')` or `Expansion.cyclic(name)` |

`expand` leaves `S`, `K` and `I` as they are, and passes through names that
are not in the table. It rewrites any bird *named* `Y` to Curry's
`S (K (S I I)) (S (S (K S) K) (K (S I I)))`, and any bird named `Theta` to
Turing's `U U`, whatever their rules say. For any other bird whose rule
names itself, it returns `cyclic`. It expands the birds a rule names in
turn. It detects only self-reference: if two rules name each other,
`expand` never terminates.

## Spine-preserving contraction

Ordinary contraction builds the result as one term, which re-associates
the arguments into it. `fireSpine(b, args)` instead returns the
contractum's spine as a list of *items*: the head, then each argument, with
every argument and every parenthesised part of the rule kept whole. With
`x = K I`, `S x y z` gives `[(K I), z, (y z)]`, not `[K, I, z, (y z)]`.

`unfold(tpl, args, atom, group)` does the same over items of *any* type
`T`. The caller supplies two builders: `atom(name)` makes an item for a bird
the rule names, and `group(items)` makes one item from a parenthesised part.
A client whose items are not `Expr`s can then apply the table's rules
without converting its items; the Combinatrix game, for example, keeps holes
and bracket groups. Ordinary reduction needs neither function.

## Internal names

Jock lets functions call each other mutually only when they are adjacent
and public, so a few helpers are exported although they are not part of
the API: `argStep`, `parseAtom`, `parseMore`, `parseSeq`, `Got`, `PR`,
`unfoldOne`, `unfoldAcc`, `birdSki` and `mentions`. Do not rely on them.

## Testing

```
zsh tests/run.sh                     # 36 vectors: reduction, rules, expansion, parsing
python3 tools/difftest.py 200 1 100  # 200 random terms, seed 1, fuel 100
```

`tests/run.sh` compiles and runs `tests/vectors.jock` and compares its
output with `tests/vectors.expected`. Set `JOCK` to your Jock checkout
(default `~/Code/jock`).

`tools/difftest.py` generates random terms over the Aviary birds and free
variables. It reduces each term with Aviary (set `AVIARY` to an Aviary
checkout) and with this module, then compares the normal form, the step
count and the status. Terms that grow past 400 leaves in Aviary are dropped
and counted. `Theta` and `A` are not in Aviary's table, so the vectors
cover them instead.

Results on 2026-11-26:
- **Random terms:** 570 of 570 agreed, over six seeds at fuel 5 and fuel ≤ 100.
- **Benchmark sample:** a stratified sample of the
  [combinator-benchmarks](https://github.com/sigilante/combinator-benchmarks)
  manifests was run, covering the SKI, SK, BCKW and native-bird families in
  `nf` and `whnf` modes. All 222 rows with an inline term agreed on status,
  step count and normal form. Rows needing more than 600 steps, or with
  terms over 400 characters, were not run.

## Limits

- **Speed.** Reduction is plain term rewriting, with no sharing. Under
  interpreted Nock it suits terms of hundreds of leaves and thousands of
  steps, not millions.
- **Memory.** `nf` bounds steps but not term size, so a term that grows
  exponentially can exhaust memory before it exhausts fuel.
- **Lookup.** Each step scans the table for its bird; `aviary()` has 52
  rows.

## License

MIT; see [LICENSE](LICENSE). Copyright (c) 2026 N. E. Davis / Sigilante.

## Provenance

This module was written for Combinatrix, a falling-block game in which
combinators reduce. The game is inspired by Dirk van Deun's
[Combinatris](https://dirk.rave.org/combinatris/).
