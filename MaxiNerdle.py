numbers = list('1234567890')
numbers2 = list('123456789')
operators = list('-+*/')
exponents = list('²³')


# Possible symbols that can come next, based on the current state of the equation and last symbol used
def possiblesymbols(eq, opened_parenthesis, length, start):
    # The set of symbols the equation can begin with
    if eq == '':
        return (start)
    # The maximum length of the LHS is the max. length of the equation -2, because at least 2 spaces are used for = and RHS
    elif len(eq) >= length - 2:
        return [None]
    # None is to indicate that the LHS can be ended
    else:
        pos = [None]

    # Returns what can come next based on the last symbol and how many open parenthesis there are
    last = eq[-1]
    if last in numbers:
        pos += numbers + operators + exponents
        if opened_parenthesis > 0:
            pos += [')']
    elif last in operators:
        pos += numbers2 + ['(']
    elif last in exponents:
        pos += operators
        if opened_parenthesis > 0:
            pos += [')']
    elif last == ')':
        pos += operators + exponents
        if opened_parenthesis > 0:
            pos += [')']
    elif last == '(':
        pos = numbers2 + ['(']
    return pos


# Counts the numbers of equations saved so far to print them periodically just to ensure the code isn't stuck
count = 0
equations = []

'''
Function that generates all possible equations. This function needs to be run
2 times: one with start=numbers2 and opened_parenthesis=0 and another with
start=['('] and opened_parenthesis=1
'''


def allequations(eq='', length=10, opened_parenthesis=0, start=numbers2):
    global count
    for sym in possiblesymbols(eq, opened_parenthesis, length, start):
        if sym == None:
            try:
                val = eval(eq.replace('²', '**2').replace('³', '**3'))
                if val == int(val) and val >= 0:
                    equation = eq + f'={int(val)}'
                    if len(equation) == length:
                        equations.append(equation)
                        count += 1
                        if count % 2048 == 0:
                            print(count, equations[-1])
            except:
                continue
        else:
            allequations(eq + sym,
                         opened_parenthesis=opened_parenthesis + (1 if sym == '(' else (-1 if sym == ')' else 0)))


allequations(opened_parenthesis=0, start=numbers2)
allequations(opened_parenthesis=1, start=['('])

with open('NerdleMaxi.txt', 'a', encoding='utf-8') as f:
    for eq in equations:
        f.write(eq + '\n')
