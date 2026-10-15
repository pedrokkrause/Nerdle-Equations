from fractions import Fraction

# Pre-pairing characters with their integer values avoids calling int() in the loop
DIGITS = tuple((str(i), i) for i in range(10))
NON_ZERO_DIGITS = tuple((str(i), i) for i in range(1, 10))
OPERATORS = ('+', '-', '*', '/')


def apply_op(a, op, b):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        # Keep as native int when evenly divisible; otherwise use Fraction
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            return a // b
        return Fraction(a, b)


def generate_classic_equations(total_length=8):
    max_lhs = total_length - 2  # At least 2 chars needed for '=' and RHS
    equations = []
    count = 0

    def record_if_valid(equation, val):
        nonlocal count
        if val < 0:
            return
        if isinstance(val, Fraction):
            if val.denominator != 1:
                return
            val = val.numerator

        rhs_str = str(val)
        if len(equation) + 1 + len(rhs_str) == total_length:
            full_eq = f"{equation}={rhs_str}"
            equations.append(full_eq)
            count += 1
            if count % 2000 == 0:
                print(count, full_eq)

    def dfs(equation, ls, acc_expr, op_expr, acc_term, op_term, curr_val):
        lhs_len = len(equation)
        rem = max_lhs - lhs_len

        # 1. Every state ending in a digit is a complete, valid expression
        if ls is not None and ls not in OPERATORS:
            term_val = apply_op(acc_term, op_term, curr_val)
            total_val = apply_op(acc_expr, op_expr, term_val)
            record_if_valid(equation, total_val)

        if rem == 0:
            return

        # 2. Branch on next valid symbols
        # --- CASE A: Start of expression or right after an operator (1-9 only) ---
        if ls is None or ls in OPERATORS:
            for d_char, d_val in NON_ZERO_DIGITS:
                dfs(equation + d_char, d_char, acc_expr, op_expr, acc_term, op_term, d_val)

        # --- CASE B: Right after a digit (0-9 or an operator) ---
        else:
            # Option 1: Continue building the current multi-digit number (Layer 3)
            for d_char, d_val in DIGITS:
                dfs(equation + d_char, d_char, acc_expr, op_expr, acc_term, op_term, curr_val * 10 + d_val)

            # Option 2: Place an operator (needs at least 2 chars left: operator + digit)
            if rem >= 2:
                # Fold Layer 3 (curr_val) into Layer 2 (acc_term)
                new_term = apply_op(acc_term, op_term, curr_val)

                # Multiplicative operators (*, /) stay in Layer 2
                for op in ('*', '/'):
                    dfs(equation + op, op, acc_expr, op_expr, new_term, op, 0)

                # Additive operators (+, -) fold Layer 2 into Layer 1 (acc_expr)
                new_expr = apply_op(acc_expr, op_expr, new_term)
                for op in ('+', '-'):
                    dfs(equation + op, op, new_expr, op, 1, '*', 0)

    dfs('', None, 0, '+', 1, '*', 0)
    return equations


if __name__ == '__main__':
    print("Started generating Classic Nerdle equations...")
    equations = generate_classic_equations(total_length=8)
    print(f"Total found: {len(equations)}. Saving equations to file...")
    with open('nerdle_equations.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(equations) + '\n')