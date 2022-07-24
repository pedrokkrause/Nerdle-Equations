from math import log2
from tqdm import tqdm
from collections import defaultdict
from time import sleep

def genmaskW(expression,correct):
    mask = ''
    count = defaultdict(lambda: 0)
    for i,x in enumerate(expression):
        if x == correct[i]:
            mask += '2'
            count[x] += 1
        elif x not in correct:
            mask += '0'
        else:
            if count[x] < correct.count(x):
                mask += '1'
                count[x] += 1
            else:
                mask += '0'
    return(mask)

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
    best = None
    expected = 0
    length = len(possible)
    for expression in tqdm(dictionary):
        localexp = 0
        allmaskss = allmasksW(expression,possible)
        for mask in allmaskss:
            prob = allmaskss[mask]/length
            localexp += -prob*log2(prob)
        if localexp > expected:
            best = expression
            expected = localexp
            if len(possible) > 10000:
                print([best,expected,best in possible])
    return([best,expected,best in possible])

if __name__ == "__main__":
    palavras = []
    with open("PathToEquationOrWordList.txt") as file:
        for line in file:
            palavras.append(line.rstrip())
    print(searchW(palavras))
    print(len(palavras))
    while True:
        ans1 = input("What you inserted: ")
        ans2 = input("Mask: ")
        palavrasPossiveis = filtermaskW(ans2,ans1,palavras)
        print(len(palavras))
        print(searchW(palavras,palavrasPossiveis))
        if len(palavras) < 7:
            print(palavras)
        print("============")
