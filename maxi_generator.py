from fractions import Fraction

DIGITS = tuple('0123456789')
NON_ZERO_DIGITS = tuple('123456789')
OPERATORS = tuple('+-*/')
EXPONENTS = ('²', '³')


def apply_op(a, op, b):
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        if b == 0:
            return None  # Signals division by zero
        # Use pure int when evenly divisible for speed; fall back to Fraction
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            return a // b
        return Fraction(a, b)


def generate_maxi_equations(total_length=10):
    max_lhs = total_length - 2
    equations = []
    count = 0

    def record_if_valid(equation, val):
        nonlocal count
        if val is None or val < 0:
            return
        if isinstance(val, Fraction):
            if val.denominator != 1:
                return
            val = val.numerator

        # Quick length check before string formatting
        rhs_str = str(val)
        if len(equation) + 1 + len(rhs_str) == total_length:
            full_eq = f"{equation}={rhs_str}"
            equations.append(full_eq)
            count += 1
            if count % 2000 == 0:
                print(count, full_eq)

    def dfs(equation, ls, acc_expr, op_expr, acc_term, op_term, curr_val, stack):
        lhs_len = len(equation)
        rem = max_lhs - lhs_len
        open_parens = len(stack)

        # 1. If we are at a valid end state with no open parentheses, fold & check
        if lhs_len > 0 and open_parens == 0 and ls not in '+-*/(':
            term_val = apply_op(acc_term, op_term, curr_val)
            if term_val is not None:
                total_val = apply_op(acc_expr, op_expr, term_val)
                record_if_valid(equation, total_val)

        if rem == 0:
            return

        # 2. Branch on next valid symbols based on last symbol (ls)
        # --- CASE A: Append a Digit ---
        if ls is None or ls in OPERATORS or ls == '(':
            # Need at least `open_parens` chars left after this digit to close parens
            if rem - 1 >= open_parens:
                for d in NON_ZERO_DIGITS:
                    dfs(equation + d, d, acc_expr, op_expr, acc_term, op_term, int(d), stack)
        elif ls in DIGITS:
            if rem - 1 >= open_parens:
                for d in DIGITS:
                    dfs(equation + d, d, acc_expr, op_expr, acc_term, op_term, curr_val * 10 + int(d), stack)

        # --- CASE B: Append an Exponent (² or ³) ---
        if ls in DIGITS or ls == ')':
            # After an exponent, we MUST place an operator (+-*/) and a digit,
            # EXCEPT if we are at the end of the expression (open_parens == 0)
            if rem - 1 >= open_parens:
                dfs(equation + '²', '²', acc_expr, op_expr, acc_term, op_term, curr_val * curr_val, stack)
                dfs(equation + '³', '³', acc_expr, op_expr, acc_term, op_term, curr_val * curr_val * curr_val, stack)

        # --- CASE C: Append an Operator (+, -, *, /) ---
        if ls in DIGITS or ls in EXPONENTS or ls == ')':
            # After an operator, we need at least 1 digit + `open_parens` closing parens
            if rem - 1 >= open_parens + 1:
                new_term = apply_op(acc_term, op_term, curr_val)
                if new_term is None:
                    return  # Prune division by zero immediately!

                # Multiplicative operators (*, /) keep building `acc_term`
                for op in ('*', '/'):
                    dfs(equation + op, op, acc_expr, op_expr, new_term, op, 0, stack)

                # Additive operators (+, -) fold `new_term` into `acc_expr`
                new_expr = apply_op(acc_expr, op_expr, new_term)
                for op in ('+', '-'):
                    dfs(equation + op, op, new_expr, op, 1, '*', 0, stack)

        # --- CASE D: Unary Minus right after '(' ---
        if ls == '(':
            # Needs at least 1 digit + open_parens closing parens
            if rem - 1 >= open_parens + 1:
                dfs(equation + '-', '-', 0, '-', 1, '*', 0, stack)

        # --- CASE E: Open Parenthesis '(' ---
        if ls is None or ls in OPERATORS or ls == '(':
            # Opening a new paren increases open_parens by 1, and inside it we need
            # at least 1 digit + 1 operator + 1 digit (or unary minus + digit) + closing ')'
            if rem - 1 >= (open_parens + 1) + 1:
                new_stack = stack + ((acc_expr, op_expr, acc_term, op_term),)
                dfs(equation + '(', '(', 0, '+', 1, '*', 0, new_stack)

        # --- CASE F: Close Parenthesis ')' ---
        if open_parens > 0 and ls not in '+-*/(':
            if rem - 1 >= open_parens - 1:
                inner_term = apply_op(acc_term, op_term, curr_val)
                if inner_term is None:
                    return  # Prune division by zero inside parens!
                inner_val = apply_op(acc_expr, op_expr, inner_term)
                prev_acc_expr, prev_op_expr, prev_acc_term, prev_op_term = stack[-1]
                dfs(equation + ')', ')', prev_acc_expr, prev_op_expr, prev_acc_term, prev_op_term, inner_val, stack[:-1])

    dfs('', None, 0, '+', 1, '*', 0, ())
    return equations


if __name__ == '__main__':
    print("Started generating")
    equations = generate_maxi_equations(total_length=10)
    print(f"Total found: {len(equations)}. Saving equations to file...")
    with open('maxi_equations.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(equations) + '\n')