from math import factorial
from fractions import Fraction

class Parser:

    def __init__(self):
        # Infix cumulative
        self.infix_cm = {'+': lambda x, y: x + y,
                         '-': lambda x, y: x - y}

        self.r_assoc_ops = {'^': lambda x, y: x ** y}

        # Infix immediate
        self.infix_im = {'*': lambda x, y: x * y,
                         '/': lambda x, y: Fraction(x,y)}

        self.unary_right = {'²': lambda x: x * x,
                            '³': lambda x: x * x * x,
                            '!': lambda x: factorial(x)}

    def parse_expression(self, expression):
        self.index = 0
        self.expression_to_parse = expression
        return self.expression()

    def peek(self):
        if self.index < len(self.expression_to_parse):
            return self.expression_to_parse[self.index]

    def get(self):
        if self.index < len(self.expression_to_parse):
            char = self.expression_to_parse[self.index]
            self.index += 1
            return char

    def number(self):
        result = int(self.get())
        while self.peek() and self.peek().isdecimal():
            result = 10 * result + int(self.get())
        return result

    def factor(self):
        if self.peek() and self.peek().isdecimal():
            return self.number()
        elif self.peek() == '(':
            self.get()
            result = self.expression(check_end=False)
            if self.get() != ')':
                raise SyntaxError("Unmatched parenthesis")
            return result
        elif self.peek() == '-':
            self.get()
            return -self.factor()
        raise SyntaxError("Unexpected character")

    def expon(self):
        result = self.factor()
        while self.peek() in self.unary_right:
            result = self.unary_right[self.get()](result)
        return result

    def term(self):
        result = self.expon()
        while self.peek() in self.r_assoc_ops:
            operator = self.get()
            result = self.r_assoc_ops[operator](result, self.r_assoc(self.expon(),operator,self.r_assoc_ops[operator]))
        while self.peek() in self.infix_im:
            result = self.infix_im[self.get()](result, self.expon())
        return result

    def expression(self, check_end=True):
        result = self.term()
        while self.peek() in self.infix_cm:
            result = self.infix_cm[self.get()](result, self.term())
        if check_end and self.peek() is not None:
            raise SyntaxError("Expression could not be parsed fully")
        return result

    # Handle right associativity
    def r_assoc(self, exp, symbol, operator):
        if self.peek() == symbol:
            self.get()
            return self.r_assoc(operator(exp,self.factor()), symbol, operator)
        else:
            return exp

parser = Parser()

def parenthesis_helper(s):
    if s == '(':
        return 1
    elif s == ')':
        return -1
    else:
        return 0

numbers1 = list('0123456789')
numbers2 = list('123456789')
operators = list('+-*/')
exponents = list('²³')

def possible_symbols(equation,opened_parenthesis,total_length):
    if len(equation) == 0:
        return numbers2+['(']
    elif len(equation) == total_length-2:
        return [None]

    pos = [None]
    ls = equation[-1]

    if ls in numbers1:
        pos += numbers1+operators+exponents
    elif ls in operators:
        pos += numbers2+['(']
    elif ls in exponents:
        pos += operators+['(']
    elif ls == '(':
        pos += numbers2+['-','(']
    elif ls == ')':
        pos += operators+exponents

    if opened_parenthesis != 0 and ls != '(':
        pos.append(')')

    return pos

count = 0
equations = []

def handle_equation(equation,value,total_length=10):
    global count
    full_equation = equation + f'={round(value)}'
    if len(full_equation) == total_length:
        equations.append(full_equation)
        count += 1
        if count % 2000 == 0:
            print(count, full_equation)

def gen_equations(equation='',opened_parenthesis=0,total_length=10):
    for symbol in possible_symbols(equation,opened_parenthesis,total_length):
        if symbol is None:
            try:
                val = parser.parse_expression(equation)
                if val >= 0:
                    if isinstance(val,Fraction):
                        if val.denominator==1:
                            handle_equation(equation, val, total_length)
                    else:
                        handle_equation(equation, val, total_length)
            except:
                continue
        else:
            gen_equations(equation+symbol, opened_parenthesis+parenthesis_helper(symbol), total_length)

print("Started generating")
gen_equations()

print("Saving equations to file")
with open('NerdleMaxi2.txt', 'a', encoding='utf-8') as f:
    for eq in equations:
        f.write(eq + '\n')