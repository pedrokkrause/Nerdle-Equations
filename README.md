# Nerdle Equations and Analysis Repository

A complete dataset of valid equations, fast on-the-fly generators, and information-theoretic / decision-tree analysis for **Classic Nerdle** (8 tiles) and **Maxi Nerdle** (10 tiles).

---

## Repository Structure

* **`classic_equations.txt` & `maxi_equations.txt`**[cite: 1, 2] — All valid target equations for Classic and Maxi Nerdle. These datasets strictly follow Nerdle's official answer rules:
  * Only a single non-negative integer appears on the right-hand side (RHS) of the `=` symbol.
  * No leading zeroes (e.g., `07`) or lone zeroes (`0`).
  * No consecutive binary operators (such as `+-` or `*+`).
* **`classic_generator.py` & `maxi_generator.py`**[cite: 1, 2] — Fast Depth-First Search (DFS) generators that build valid left-hand side (LHS) expressions step by step while evaluating arithmetic on the fly.
* **`classic_opener.cpp` & `maxi_opener.cpp`**[cite: 2] — Multi-threaded C++20 / OpenMP solvers that find the optimal first guesses by combining Shannon entropy screening with full Branch-and-Bound decision-tree evaluation.
* **`classic_pairs.txt` & `maxi_pairs.txt`**[cite: 1, 2] — All valid pairs of equations that collectively test every possible symbol in their respective game modes (with `=` used once in each equation), ranked by their exact joint Shannon information.
* **`pair_finder.py`**[cite: 1, 2] — Vectorized Python script that pairs complementary all-unique-character equations via bitmasks and computes their joint information across the equation datasets.
* **`old_version/`**[cite: 1, 2] — Archive of legacy scripts, unfiltered raw datasets, and earlier solver versions.

---

## Best Openers and Pairs

The single-opener benchmarks below were computed by `classic_opener.cpp` and `maxi_opener.cpp`[cite: 2] by evaluating full Branch-and-Bound decision trees to minimize **Expected Average Turns** (assuming all target equations are equally likely), alongside their Turn-1 **Average Information** (Shannon entropy in bits).

| Game Mode | Best Opener | Average Information (bits) | Average Turns | Best Pair | Pair Information (bits) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Classic** | `54-36=18` | 9.7253 | 3.0194 | `5*9+1=46` and `30/2-7=8` | 13.0380 |
| **Maxi** | `56-1+23=78`\* | 12.4120 | 3.4484\* | `90+3-6²=57` and `1*(4/2)³=8` | 16.1508 |

*\*Evaluated under Hard Mode (subsequent guesses restricted to the remaining candidate pool).*

---

## How the Equations Are Generated (`*_generator.py`)

Generating equations by brute-forcing all possible character combinations is feasible for smaller modes, but impossible for Maxi Nerdle, where the raw symbol space exceeds 6 trillion strings. Instead, `classic_generator.py` and `maxi_generator.py`[cite: 1, 2] construct equations using a finite-state machine combined with **on-the-fly evaluation**:

1. **LHS-Only Construction:** Only the left-hand side (LHS) of the equation is generated (up to $L - 2$ characters, leaving at least 2 characters for `=` and the RHS).
2. **State-Machine Transitions:** The next allowed symbol depends strictly on the last symbol ($LS$) added and the remaining character budget.

### Symbol Sets
* **Digits ($D$):** $[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]$ and **Non-Zero Digits ($D^*$):** $[1, 2, 3, 4, 5, 6, 7, 8, 9]$
* **Operators ($O$):** $[-, +, *, /]$
* **Exponents ($E$, Maxi only):** $[², ³]$

### Transition Rules ($LS \rightarrow \text{Next Allowed Symbols}$)
* **Start of expression ($LS = \text{None}$):** $\rightarrow D^* \cup [(]$
* **$LS \in D$:** $\rightarrow D \cup O \cup E$
* **$LS \in O$:** $\rightarrow D^* \cup [(]$
* **$LS \in E$:** $\rightarrow O$
* **$LS = ($:** $\rightarrow D^* \cup [(, -]$
* **$LS = )$:** $\rightarrow O \cup E$

*(Note: Classic Nerdle omits parentheses and exponents $E$. In Maxi Nerdle, `)` is also allowed whenever there is an unclosed `(` and $LS \notin O \cup [(]$.)*

### On-the-Fly 3-Layer Evaluation & Pruning[cite: 3]
Rather than parsing completed strings from scratch at the leaves of the search tree, the generators maintain the running value of the expression across three precedence layers during the DFS[cite: 3]:

$$\text{Value} = \mathtt{acc}_{\mathtt{expr}} \pm (\mathtt{acc}_{\mathtt{term}} \times/\div \mathtt{curr}_{\mathtt{val}})$$

* **Layer 1 (`acc_expr`, `op_expr`):** Holds the sum/difference of all completed additive terms.
* **Layer 2 (`acc_term`, `op_term`):** Holds the product/quotient of all completed factors in the active term.
* **Layer 3 (`curr_val`):** Accumulates the current multi-digit number or exponent (`²`, `³`).
* **Parentheses (`stack`):** Opening a parenthesis `(` pushes the active outer state onto a stack and starts a fresh inner state; closing `)` folds the inner state and pops the outer state back.

This architecture eliminates string parsing overhead, prunes division-by-zero branches (`1/(2-2)`) the instant a zero divisor closes, and prunes branches whose unclosed parentheses or trailing operators cannot fit within the remaining character budget.

---

## Finding the Optimal Openers (`*_opener.cpp`)

Maximizing Turn-1 Shannon entropy does not always guarantee the lowest average number of turns to solve a puzzle. To find the true optimal openers, `classic_opener.cpp` and `maxi_opener.cpp`[cite: 2] build full decision trees:

* **`classic_opener.cpp`**[cite: 2] precomputes the full $17,723 \times 17,723$ feedback matrix in RAM (~628 MB), ranks candidate openers by initial Shannon entropy, and solves the exact minimum-turn decision tree across the full dictionary using Branch-and-Bound, Zobrist hash memoization, and theoretical lower-bound pruning across OpenMP threads.
* **`maxi_opener.cpp`**[cite: 2] filters the ~2.25M Maxi equations down to candidates with 10 unique characters, screens the top finalists via sampled Shannon entropy, and evaluates full parallel Hard Mode decision trees across all 2.25M target equations.

### Compilation (GCC / Clang with OpenMP)
```bash
g++ -O3 -std=c++20 -fopenmp classic_opener.cpp -o classic_opener
g++ -O3 -std=c++20 -fopenmp maxi_opener.cpp -o maxi_opener
```

---

## All-Symbol Pairs (`pair_finder.py`)

For human play, a popular strategy is to open with two pre-planned equations that test **every possible symbol** without overlapping characters (except `=`, which must appear in both):
* **Classic Nerdle:** 15 total symbols (`0-9`, `+-*/`, `=`) across $2 \times 8 = 16$ tiles.
* **Maxi Nerdle:** 19 total symbols (`0-9`, `+-*/()²³`, `=`) across $2 \times 10 = 20$ tiles.

`pair_finder.py`[cite: 1, 2] filters the equations down to those with all unique characters, groups them by their non-`=` character bitmask, pairs each mask with its exact bitwise complement in $O(1)$ time, and computes the exact joint Shannon entropy for every valid pair.
