import time
from collections import defaultdict
from fractions import Fraction
import numpy as np

# ==============================================================================
# CONFIGURATION (Edit these variables directly in PyCharm)
# ==============================================================================

# 1. Path to your secret equations file (used to measure Average Information)
SECRETS_FILE = "maxi_equations.txt"

# 2. Output file to save all valid pairs (set to None if you only want console output)
OUTPUT_FILE = "maxi_pairs.txt"

# 3. Maxi Pair Candidate Rules (used automatically when word_len == 10)
MAXI_ALLOW_LONE_ZERO = False          # Allows e.g. 3²+(0/7)=9 or 8-2*4=0 (forbids 07)
MAXI_ALLOW_UNARY_PLUS_MINUS = False   # Allows unary + / - at start of LHS or after '('
MAXI_ALLOW_OP_PLUS_MINUS = False     # Set True to also allow *+, *-, /+, /-, +-, -+

# 4. Two-Stage Evaluation Settings (keeps RAM under ~90 MB for Maxi)
#    - Stage 1 screens all pairs using SCREEN_SAMPLE_SIZE secrets (50,000).
#      (For Classic Nerdle, 17,723 < 50,000, so Stage 1 is already 100% exact!)
#    - Stage 2 computes the EXACT information across ALL 2.2M secrets for the top finalists.
SCREEN_SAMPLE_SIZE = 50000
TOP_FINALISTS_EXACT = 100
TOP_K_TO_DISPLAY = 20

# ==============================================================================
# CORE ENGINE
# ==============================================================================

CLASSIC_NON_EQ = "0123456789+-*/"
MAXI_NON_EQ = "0123456789+-*/()QC"  # Q = ², C = ³


def normalize(eq: str) -> str:
    return eq.strip().replace("²", "Q").replace("³", "C")


def denormalize(eq: str) -> str:
    return eq.replace("Q", "²").replace("C", "³")


def generate_maxi_pair_candidates() -> list[str]:
    """
    Generates all 10-unique-character Maxi equations directly in memory.
    Allows lone zeroes and flexible unary + / - as configured above.
    """
    print(
        f"Generating 10-unique-char Maxi candidates "
        f"(lone_zero={MAXI_ALLOW_LONE_ZERO}, unary_pm={MAXI_ALLOW_UNARY_PLUS_MINUS}, "
        f"op_pm={MAXI_ALLOW_OP_PLUS_MINUS})...",
        flush=True,
    )
    t0 = time.perf_counter()

    digits = [(str(d), d, 1 << d) for d in range(10)]
    non_zero_digits = digits[1:]
    ops = [(op, 1 << (10 + i)) for i, op in enumerate("+-*/")]
    exps = [("Q", 2, 1 << 16), ("C", 3, 1 << 17)]
    BIT_LPAREN = 1 << 14
    BIT_RPAREN = 1 << 15

    candidates = []

    def apply_op(a, op, b):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                return None
            if isinstance(a, int) and isinstance(b, int) and a % b == 0:
                return a // b
            return Fraction(a, b)

    def check_and_record(lhs: str, val, used_mask: int):
        if val is None or val < 0:
            return
        if isinstance(val, Fraction):
            if val.denominator != 1:
                return
            val = val.numerator
        if val == 0 and not MAXI_ALLOW_LONE_ZERO:
            return

        # '(' and ')' must either both be used or neither be used
        if bool(used_mask & BIT_LPAREN) != bool(used_mask & BIT_RPAREN):
            return

        rhs = str(val)
        if len(lhs) + 1 + len(rhs) != 10:
            return

        m = used_mask
        for ch in rhs:
            bit = 1 << (ord(ch) - 48)
            if m & bit:
                return  # Duplicate digit on RHS
            m |= bit

        candidates.append(f"{lhs}={rhs}")

    # curr_sign (+1 or -1) is kept separate from curr_val so that -2² evaluates as -(2²) = -4
    def dfs(lhs, ls, used_mask, acc_expr, op_expr, acc_term, op_term, curr_sign, curr_val, is_unary, stack):
        lhs_len = len(lhs)
        rem = 8 - lhs_len
        open_parens = len(stack)

        # 1. Check if valid complete LHS
        if lhs_len > 0 and open_parens == 0 and ls in "0123456789QC)":
            term_val = apply_op(acc_term, op_term, curr_sign * curr_val)
            if term_val is not None:
                total_val = apply_op(acc_expr, op_expr, term_val)
                check_and_record(lhs, total_val, used_mask)

        if rem == 0:
            return

        # 2. Append a Digit
        if ls is None or ls in "+-*/(":
            if rem - 1 >= open_parens:
                allowed_digits = digits if MAXI_ALLOW_LONE_ZERO else non_zero_digits
                for d_ch, d_val, d_bit in allowed_digits:
                    if not (used_mask & d_bit):
                        dfs(lhs + d_ch, d_ch, used_mask | d_bit,
                            acc_expr, op_expr, acc_term, op_term, curr_sign, d_val, False, stack)
        elif ls in "123456789" or (ls == "0" and curr_val != 0):
            # Multi-digit continuation (never after a leading '0')
            if rem - 1 >= open_parens:
                for d_ch, d_val, d_bit in digits:
                    if not (used_mask & d_bit):
                        dfs(lhs + d_ch, d_ch, used_mask | d_bit,
                            acc_expr, op_expr, acc_term, op_term, curr_sign, curr_val * 10 + d_val, False, stack)

        # 3. Append an Exponent ('Q' = ², 'C' = ³)
        if ls is not None and ls in "0123456789)":
            if rem - 1 >= open_parens:
                for e_ch, power, e_bit in exps:
                    if not (used_mask & e_bit):
                        new_val = curr_val * curr_val if power == 2 else curr_val * curr_val * curr_val
                        dfs(lhs + e_ch, e_ch, used_mask | e_bit,
                            acc_expr, op_expr, acc_term, op_term, curr_sign, new_val, False, stack)

        # 4. Append a Binary Operator (+, -, *, /)
        if ls is not None and ls in "0123456789QC)":
            if rem - 1 >= open_parens + 1:
                new_term = apply_op(acc_term, op_term, curr_sign * curr_val)
                if new_term is None:
                    return
                new_expr = apply_op(acc_expr, op_expr, new_term)
                for op_ch, op_bit in ops:
                    if not (used_mask & op_bit):
                        if op_ch in "*/":
                            dfs(lhs + op_ch, op_ch, used_mask | op_bit,
                                acc_expr, op_expr, new_term, op_ch, 1, 0, False, stack)
                        else:
                            dfs(lhs + op_ch, op_ch, used_mask | op_bit,
                                new_expr, op_ch, 1, "*", 1, 0, False, stack)

        # 5. Append a Unary '+' or '-'
        can_unary_start = (ls is None or ls == "(") and MAXI_ALLOW_UNARY_PLUS_MINUS
        can_unary_after_dir = (ls == "(") and not MAXI_ALLOW_UNARY_PLUS_MINUS  # Strict mode allows '(-'
        can_unary_after_op = (ls is not None and ls in "+-*/" and not is_unary) and MAXI_ALLOW_OP_PLUS_MINUS

        if can_unary_start or can_unary_after_op:
            if rem - 1 >= open_parens + 1:
                for op_ch, op_bit in ops[:2]:  # '+' or '-'
                    if not (used_mask & op_bit):
                        sign = -curr_sign if op_ch == "-" else curr_sign
                        dfs(lhs + op_ch, op_ch, used_mask | op_bit,
                            acc_expr, op_expr, acc_term, op_term, sign, 0, True, stack)
        elif can_unary_after_dir:
            op_ch, op_bit = ops[1]  # '-' only
            if not (used_mask & op_bit) and (rem - 1 >= open_parens + 1):
                dfs(lhs + op_ch, op_ch, used_mask | op_bit,
                    acc_expr, op_expr, acc_term, op_term, -curr_sign, 0, True, stack)

        # 6. Open Parenthesis '('
        if not (used_mask & BIT_LPAREN) and (ls is None or ls in "+-*/("):
            if rem - 1 >= (open_parens + 1) + 1:
                new_stack = stack + ((acc_expr, op_expr, acc_term, op_term, curr_sign),)
                dfs(lhs + "(", "(", used_mask | BIT_LPAREN,
                    0, "+", 1, "*", 1, 0, False, new_stack)

        # 7. Close Parenthesis ')'
        if open_parens > 0 and not (used_mask & BIT_RPAREN) and ls in "0123456789QC":
            if rem - 1 >= open_parens - 1:
                inner_term = apply_op(acc_term, op_term, curr_sign * curr_val)
                if inner_term is None:
                    return
                inner_val = apply_op(acc_expr, op_expr, inner_term)
                p_acc_expr, p_op_expr, p_acc_term, p_op_term, p_sign = stack[-1]
                dfs(lhs + ")", ")", used_mask | BIT_RPAREN,
                    p_acc_expr, p_op_expr, p_acc_term, p_op_term, p_sign, inner_val, False, stack[:-1])

    dfs("", None, 0, 0, "+", 1, "*", 1, 0, False, ())
    print(f"Generated {len(candidates):,} 10-unique-char Maxi candidates in {time.perf_counter() - t0:.2f}s.", flush=True)
    return candidates


def filter_and_group_by_mask(equations: list[str], non_eq_symbols: str, word_len: int):
    bit_map = {ch: (1 << i) for i, ch in enumerate(non_eq_symbols)}
    all_mask = (1 << len(non_eq_symbols)) - 1

    by_mask = defaultdict(list)
    for eq in set(equations):
        if len(eq) != word_len or "=" not in eq:
            continue
        mask = 0
        valid = True
        seen_eq = False
        for ch in eq:
            if ch == "=":
                if seen_eq:
                    valid = False
                    break
                seen_eq = True
            else:
                b = bit_map.get(ch, 0)
                if b == 0 or (mask & b):
                    valid = False
                    break
                mask |= b
        if valid and seen_eq:
            by_mask[mask].append(eq)

    valid_mask_pairs = []
    surviving_eqs = []
    for mask in sorted(by_mask.keys()):
        comp = all_mask ^ mask
        if mask < comp and comp in by_mask:
            valid_mask_pairs.append((mask, comp))
            surviving_eqs.extend(by_mask[mask])
            surviving_eqs.extend(by_mask[comp])

    return by_mask, valid_mask_pairs, surviving_eqs


def stream_secrets_to_compact_arrays(filepath: str, batch_size: int = 100000):
    """
    Streams SECRETS_FILE in chunks directly into compact uint8 arrays:
      - s_ids: shape (word_len, N) uint8  (~22 MB for 2.2M Maxi equations)
      - s_has: shape (n_syms, N) uint8    (~42 MB for 2.2M Maxi equations)
    Also collects unique-character candidates while streaming if word_len == 8.
    """
    t0 = time.perf_counter()
    n_secrets = 0
    word_len = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                if word_len is None:
                    word_len = len(normalize(s))
                n_secrets += 1

    is_maxi = (word_len == 10)
    non_eq_symbols = MAXI_NON_EQ if is_maxi else CLASSIC_NON_EQ
    all_symbols = non_eq_symbols + "="
    n_syms = len(all_symbols)
    char_to_id = {ch: i for i, ch in enumerate(all_symbols)}

    lut = np.zeros(256, dtype=np.uint8)
    for ch, idx in char_to_id.items():
        lut[ord(ch)] = idx

    s_ids = np.empty((word_len, n_secrets), dtype=np.uint8)
    classic_unique_cands = []

    idx = 0
    chunk = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            s = normalize(line)
            if not s:
                continue
            chunk.append(s)
            if not is_maxi and len(set(s)) == word_len:
                classic_unique_cands.append(s)

            if len(chunk) == batch_size:
                n_c = len(chunk)
                raw = np.frombuffer("".join(chunk).encode("ascii"), dtype=np.uint8).reshape(n_c, word_len)
                s_ids[:, idx:idx + n_c] = lut[raw].T
                idx += n_c
                chunk.clear()

        if chunk:
            n_c = len(chunk)
            raw = np.frombuffer("".join(chunk).encode("ascii"), dtype=np.uint8).reshape(n_c, word_len)
            s_ids[:, idx:idx + n_c] = lut[raw].T
            idx += n_c
            chunk.clear()

    s_has = np.zeros((n_syms, n_secrets), dtype=np.uint8)
    secret_range = np.arange(n_secrets)
    for pos in range(word_len):
        s_has[s_ids[pos], secret_range] = 1

    ram_mb = (s_ids.nbytes + s_has.nbytes) / (1024 * 1024)
    print(
        f"Streamed {n_secrets:,} secrets (L={word_len}) into {ram_mb:.1f} MB RAM "
        f"in {time.perf_counter() - t0:.2f}s.",
        flush=True,
    )
    return s_ids, s_has, word_len, non_eq_symbols, all_symbols, char_to_id, classic_unique_cands


def compute_pattern_inplace(eq: str, char_to_id: dict, s_ids: np.ndarray, s_has: np.ndarray,
                            out_pat: np.ndarray, scratch: np.ndarray):
    """Computes the feedback pattern of a unique-char equation `eq` with zero allocations."""
    out_pat.fill(0)
    for pos, ch in enumerate(eq):
        c = char_to_id[ch]
        if pos > 0:
            out_pat *= 3
        out_pat += s_has[c]
        np.equal(s_ids[pos], c, out=scratch)
        out_pat += scratch


def compute_joint_entropy(pat1: np.ndarray, pat2: np.ndarray, max_patterns: int,
                          n_sec: int, log2_n: float, n_log2_n: np.ndarray,
                          joint_buf: np.ndarray) -> float:
    """Computes exact joint Shannon entropy of (pat1, pat2) using a pre-allocated uint32 buffer."""
    np.multiply(pat1, max_patterns, out=joint_buf, casting="unsafe")
    joint_buf += pat2
    joint_buf.sort()

    # Count run lengths of identical joint patterns
    diff_indices = np.flatnonzero(joint_buf[1:] != joint_buf[:-1]) + 1
    boundaries = np.empty(len(diff_indices) + 2, dtype=np.int64)
    boundaries[0] = 0
    boundaries[1:-1] = diff_indices
    boundaries[-1] = n_sec

    counts = np.diff(boundaries)
    return log2_n - float(np.sum(n_log2_n[counts])) / n_sec


def main():
    print(f"Loading secrets from '{SECRETS_FILE}'...", flush=True)
    (
        s_ids,
        s_has,
        word_len,
        non_eq_symbols,
        all_symbols,
        char_to_id,
        classic_cands,
    ) = stream_secrets_to_compact_arrays(SECRETS_FILE)

    n_secrets = s_ids.shape[1]
    is_maxi = (word_len == 10)
    max_patterns = 3 ** word_len

    # 1. Build candidate pool
    if is_maxi:
        raw_candidates = generate_maxi_pair_candidates()
    else:
        raw_candidates = classic_cands

    by_mask, valid_mask_pairs, surviving_eqs = filter_and_group_by_mask(
        raw_candidates, non_eq_symbols, word_len
    )

    total_pairs = sum(len(by_mask[m1]) * len(by_mask[m2]) for m1, m2 in valid_mask_pairs)
    print(
        f"Surviving unique-char candidates: {len(surviving_eqs):,} across "
        f"{len(valid_mask_pairs):,} complementary mask pairs ({total_pairs:,} total equation pairs).",
        flush=True,
    )

    if total_pairs == 0:
        print("No valid pairs found.")
        return

    # 2. Stage 1: Screen all pairs per mask-bucket (uses only a few MB of RAM)
    use_screening = (SCREEN_SAMPLE_SIZE > 0 and SCREEN_SAMPLE_SIZE < n_secrets)
    if use_screening:
        rng = np.random.default_rng(1337)
        sample_idx = np.sort(rng.choice(n_secrets, size=SCREEN_SAMPLE_SIZE, replace=False))
        s_ids_stage1 = np.ascontiguousarray(s_ids[:, sample_idx])
        s_has_stage1 = np.ascontiguousarray(s_has[:, sample_idx])
        n_stage1 = SCREEN_SAMPLE_SIZE
        print(f"\n[Stage 1] Screening all {total_pairs:,} pairs over {n_stage1:,} sampled secrets...", flush=True)
    else:
        s_ids_stage1 = s_ids
        s_has_stage1 = s_has
        n_stage1 = n_secrets
        print(f"\n[Stage 1] Evaluating all {total_pairs:,} pairs over all {n_stage1:,} secrets...", flush=True)

    t0 = time.perf_counter()
    log2_n1 = float(np.log2(n_stage1))
    n_log2_n1 = np.zeros(n_stage1 + 1, dtype=np.float64)
    arr1 = np.arange(1, n_stage1 + 1, dtype=np.float64)
    n_log2_n1[1:] = arr1 * np.log2(arr1)

    scratch1 = np.empty(n_stage1, dtype=np.uint8)
    joint_buf1 = np.empty(n_stage1, dtype=np.uint32)

    all_pairs_stage1 = []

    # Process one complementary mask pair (m1, m2) at a time so pattern arrays are immediately freed
    for m1, m2 in valid_mask_pairs:
        list1 = by_mask[m1]
        list2 = by_mask[m2]

        pats1 = []
        ents1 = []
        for eq1 in list1:
            p = np.empty(n_stage1, dtype=np.uint16)
            compute_pattern_inplace(eq1, char_to_id, s_ids_stage1, s_has_stage1, p, scratch1)
            counts = np.bincount(p)
            e1 = log2_n1 - float(np.sum(n_log2_n1[counts[counts > 0]])) / n_stage1
            pats1.append(p)
            ents1.append(e1)

        pats2 = []
        ents2 = []
        for eq2 in list2:
            p = np.empty(n_stage1, dtype=np.uint16)
            compute_pattern_inplace(eq2, char_to_id, s_ids_stage1, s_has_stage1, p, scratch1)
            counts = np.bincount(p)
            e2 = log2_n1 - float(np.sum(n_log2_n1[counts[counts > 0]])) / n_stage1
            pats2.append(p)
            ents2.append(e2)

        for i, eq1 in enumerate(list1):
            p1 = pats1[i]
            e1 = ents1[i]
            for j, eq2 in enumerate(list2):
                joint_ent = compute_joint_entropy(
                    p1, pats2[j], max_patterns, n_stage1, log2_n1, n_log2_n1, joint_buf1
                )
                all_pairs_stage1.append((joint_ent, e1, ents2[j], eq1, eq2))

    all_pairs_stage1.sort(key=lambda x: x[0], reverse=True)
    print(f"[Stage 1] Completed in {time.perf_counter() - t0:.2f}s.", flush=True)

    # 3. Stage 2: Exact evaluation over 100% of secrets for top finalists (if Stage 1 was sampled)
    if use_screening:
        n_finalists = min(TOP_FINALISTS_EXACT, len(all_pairs_stage1))
        print(
            f"\n[Stage 2] Computing EXACT information across all {n_secrets:,} secrets "
            f"for top {n_finalists} finalists...",
            flush=True,
        )
        t0 = time.perf_counter()
        log2_full = float(np.log2(n_secrets))
        n_log2_full = np.zeros(n_secrets + 1, dtype=np.float64)
        arr_full = np.arange(1, n_secrets + 1, dtype=np.float64)
        n_log2_full[1:] = arr_full * np.log2(arr_full)

        # Reuse just two 4.5 MB pattern buffers + one 9 MB uint32 buffer!
        pat1_full = np.empty(n_secrets, dtype=np.uint16)
        pat2_full = np.empty(n_secrets, dtype=np.uint16)
        scratch_full = np.empty(n_secrets, dtype=np.uint8)
        joint_buf_full = np.empty(n_secrets, dtype=np.uint32)

        exact_results = []
        for idx_f in range(n_finalists):
            _, _, _, eq1, eq2 = all_pairs_stage1[idx_f]
            compute_pattern_inplace(eq1, char_to_id, s_ids, s_has, pat1_full, scratch_full)
            compute_pattern_inplace(eq2, char_to_id, s_ids, s_has, pat2_full, scratch_full)

            c1 = np.bincount(pat1_full)
            e1_exact = log2_full - float(np.sum(n_log2_full[c1[c1 > 0]])) / n_secrets

            c2 = np.bincount(pat2_full)
            e2_exact = log2_full - float(np.sum(n_log2_full[c2[c2 > 0]])) / n_secrets

            joint_exact = compute_joint_entropy(
                pat1_full, pat2_full, max_patterns, n_secrets, log2_full, n_log2_full, joint_buf_full
            )
            exact_results.append((joint_exact, e1_exact, e2_exact, denormalize(eq1), denormalize(eq2)))

        exact_results.sort(key=lambda x: x[0], reverse=True)
        print(f"[Stage 2] Completed in {time.perf_counter() - t0:.2f}s.\n", flush=True)
    else:
        exact_results = [
            (j_ent, e1, e2, denormalize(eq1), denormalize(eq2))
            for j_ent, e1, e2, eq1, eq2 in all_pairs_stage1
        ]

    # 4. Save all pairs to OUTPUT_FILE if configured
    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # Write exact top finalists first, followed by remaining pairs
            for j_ent, e1, e2, eq1, eq2 in exact_results:
                f.write(f"{eq1} {eq2} {j_ent:.4f}\n")
            if use_screening and len(all_pairs_stage1) > len(exact_results):
                for j_ent, _, _, eq1, eq2 in all_pairs_stage1[len(exact_results):]:
                    f.write(f"{denormalize(eq1)} {denormalize(eq2)}\n")
        print(f"Saved all {len(all_pairs_stage1):,} pairs to '{OUTPUT_FILE}'.\n", flush=True)

    # 5. Print Leaderboard
    print("=" * 82)
    print(f"{'Rank':<6}{'Equation 1':<16}{'Equation 2':<16}{'H(Eq1)':<12}{'H(Eq2)':<12}{'Joint Info (bits)'}")
    print("-" * 82)
    for rank, (joint_ent, e1, e2, eq1, eq2) in enumerate(exact_results[:TOP_K_TO_DISPLAY], start=1):
        print(f"{rank:<6}{eq1:<16}{eq2:<16}{e1:<12.4f}{e2:<12.4f}{joint_ent:.4f}")
    print("=" * 82)
    if exact_results:
        best = exact_results[0]
        print(f"🏆 BEST PAIR: {best[3]} and {best[4]} -> {best[0]:.4f} bits of information")
    print("=" * 82)


if __name__ == "__main__":
    main()