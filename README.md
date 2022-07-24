# Nerdle-Equations
All the possible equations for the Nerdle game and a solver.

- The 'Raw' files contains all the equations that Python evaluates as True, which spans almost all possible equations that can be inserted in the Nerdle game, with the exception of numbers that contain leading zeroes.
- The '4Op' files are a filtered version of their respective raws such that the operation symbols are not used in sequence, as in '4**4=16' or '4+-3=1'. Sequences of zeroes and beginning the equation with + or - is also invalid.
- The 'Restricted' files are a filtered version of their respective 4Op's accounting for the fact that nerdle's answers only contain numbers after the = symbol. These are probably the most important, as they reflect the most probable answers to the puzzles.

- wordle.py is the solver based on information theory. You enter what you inserted in the Nerdle website ("1+4*3=13" for example) and the mask returned by the game. A mask is a sequence of 0s, 1s or 2s that represent the colors of the equation you inserted. 0s are black, 1s are purple and 2s are green. Next, the algorithm will return the next optimal choice. Also, note that it assumes all equations are equally likely. Don't forget to add the path to the text file. 

Here are the best first choices considering each file:

| File              | Best choice   |
| ----------------- | ------------- |
| MiniRaw           | To be checked |
| Mini4Op           | To be checked |
| MiniRestricted    | To be checked |
| ClassicRaw        | To be checked |
| Classic4Op        | To be checked |
| ClassicRestricted | To be checked |
