import itertools
from time import perf_counter
symbols = '1234567890+-/*=' #Symbols used in classic nerdle
length = 8 #number of symbols in the equation
alleqs = [] #The list of all equations

# Checks whether the equation is true or not
def checkworks(expression):
    if expression.count("=") != 1:
        return(False)
    expression = expression.replace("=","==")
    try:
        if eval(expression):
            return(True)
        else:
            return(False)
    except:
        return(False)

start = perf_counter()
# Function to generate all possible combinations of the symbols
def foo(l):
    yield from itertools.product(*([l] * length))

# counter counts how many equations have been checked so far and max is the total number of equations there are to check
counter = 0
max = len(symbols)**length

# Checks every possible combination and uses the counter and max to estimate the time remaining
for x in foo(symbols):
    if checkworks(''.join(x)):
        alleqs.append(''.join(x))
    counter += 1
    if counter%10000000 == 0:
        elapsed = perf_counter()-start
        print(counter/max*100,"Time spent/remaining:",elapsed,elapsed*(max-counter)/counter)
print(perf_counter()-start)

# prints the number of equations validated and writes them to a file
print(len(alleqs))
with open('nerdle'+str(length)+'.txt', 'w') as f:
    for x in alleqs:
        f.write(x+"\n")