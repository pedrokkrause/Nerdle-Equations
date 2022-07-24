from math import log2
from tqdm import tqdm
from collections import defaultdict
from time import sleep
from copy import deepcopy

def genmaskW(expression,correct):
    mask = ['N']*len(expression)
    count = defaultdict(lambda: 0)
    for i, x in enumerate(expression):
        if x == correct[i]:
            mask[i] = '2'
            count[x] += 1
    for i,x in enumerate(expression):
        if x not in correct:
            mask[i] = '0'
        elif x != correct[i]:
            if count[x] < correct.count(x):
                mask[i] = '1'
                count[x] += 1
            else:
                mask[i] = '0'
    return(''.join(mask))

def checkmaskW(mask,expression,correct):
    if mask == genmaskW(expression,correct):
        return(True)
    else:
        return(False)

def allmasksW(expression,dictionary):
    masks = defaultdict(lambda: 0)
    for expression2 in dictionary:
        mask = genmaskW(expression,expression2)
        masks[mask] += 1
    return(masks)

def filtermaskW(mask,expression,dictionary):
    local = [x for x in dictionary if checkmaskW(mask,expression,x)]
    return(local)

def searchW(dictionary,possible=None):
    if possible==None:
        possible = dictionary
    if len(possible) == 1 or len(dictionary) == 1:
        return([possible[0],0,possible[0] in dictionary])
    best = None
    expected = 0
    length = len(possible)
    for expression in tqdm(dictionary):
        localexp = 0
        allmaskss = allmasksW(expression,possible)
        for mask in allmaskss:
            prob = allmaskss[mask]/length
            localexp += -prob*log2(prob)
        if localexp > expected or (localexp >= expected and expression in possible):
            best = expression
            expected = localexp
            if len(possible) > 10000:
                print([best,expected,best in possible])
    return([best,expected,best in possible])

if __name__ == "__main__":
    words = []
    with open("PathToTextFile") as file:
        for line in file:
            words.append(line.rstrip())
    possiblewords = deepcopy(words)
    print("Number of possible words:",len(possiblewords))
    print(searchW(words,possiblewords))
    best = ['48-32=16']
    while True:
        ans1 = input("What you inserted (enter 'b' if it was the best choice): ")
        ans2 = input("Mask: ")
        if ans1 == 'b':
            ans1 = best[0]
        possiblewords = filtermaskW(ans2,ans1,possiblewords)
        print("Number of possible words:",len(possiblewords))
        best = searchW(words,possiblewords)
        print("Best choice:",best[0])
        print("Average information:",best[1])
        if len(possiblewords) < 7:
            print("Possible words:",possiblewords)
        print("============")
