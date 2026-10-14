# Part 2: Data Scientist

## The role in one page

A data scientist uses statistics and modelling to find out what is true, what is likely to happen next, and how sure anyone can be. Where an analyst (Part 1) reports what the numbers say, a scientist asks whether the pattern is real, how big it is, why it might be there, and what would change the conclusion. The product is a defensible claim: "this change raised conversion by about two points, give or take two", or "these ten units fall into three kinds, and here is what to do with each".

**Who you work with.** Product and operations people who want to know whether something worked. Analysts who supply cleaned tables and context. Data engineers who keep the data flowing (Part 4). Machine learning engineers who put models into use (Part 3). Executives who want one sentence and a number.

**A typical day.** Morning: read a question and turn it into something testable, which usually means choosing the outcome, the comparison and the unit you count. Then explore the data: distributions, missing values, odd days. Midday: run a test or fit a model, always against a simple baseline. Afternoon: write down what you did, what you found, what you did not find and what would make you wrong, then explain it aloud to someone who dislikes statistics.

**What good looks like.**

- Every estimate comes with its uncertainty, in plain words.
- Every model is compared with a naive baseline and tested on data it never saw, split by time when time matters.
- The question and the analysis plan are written down before the data is examined for results.
- You separate "predicts" from "causes" and never sell one as the other.
- Someone can rerun your work from raw data and get the same answer.

**What it is not.** It is not applying the fanciest algorithm. It is not hunting for a p-value below 0.05. It is not the same as analytics (Part 1), which leans on SQL, definitions and reporting; nor as machine learning engineering (Part 3), which leans on evaluation, tracking and deployment; nor as data engineering (Part 4).

**The honest hard parts.**

- *Uncertainty is uncomfortable.* People want "yes" or "no", and the honest answer is often "probably a little, but we cannot rule out nothing".
- *Small and messy data.* Many business questions have a few dozen data points, not millions.
- *Causation is hard.* Most data is observational, and observational data cannot settle cause on its own.
- *Temptation.* Run enough comparisons and something will look significant. Resisting that is a core professional skill.
- *Communication.* A correct result that is misread does harm, so you must say clearly what it does not show.

This part is a self-study route from "I know averages" to "I can design a test, fit and judge a model, and review someone else's claims".

## How to use this part

There are four levels. Each has outcomes, core ideas with worked examples you can check by hand, labs to run on your own, exercises with answers or hints, and a checkpoint. Do not move on until you can answer the checkpoint aloud.

| Level | Aim | Time at about 5 hours a week |
|---|---|---|
| 1 Foundations | Describe data, understand sampling, correlation, confounding and what a p-value is | about 25 hours, 5 weeks |
| 2 Practitioner | Estimate differences, intervals, effect size, power, experiments, multiple tests | about 40 hours, 8 weeks |
| 3 Advanced | Regression, honest model evaluation, classification metrics, clustering, forecast backtests | about 45 hours, 9 weeks |
| 4 Expert | Causal thinking, reproducibility, ethics, review, team practice | about 35 hours, 7 weeks, then ongoing |

That is roughly eight months at a steady pace.

**What you need.** A spreadsheet is enough for Level 1 and most of Level 2. From Level 2 onward you will want a scripting language with a statistics and table library. Python with pandas, numpy, scipy and scikit-learn is a common choice; R is an equally good one. Everything is free. The worked examples use tiny datasets you can check with a calculator, so you can verify the method before you trust software.

**A good rhythm.** Read a core idea, redo its arithmetic by hand, then reproduce it in software and make the two agree. Write your prediction before you run anything. Keep a notebook of what you tried, including dead ends. Labs that use random numbers will give slightly different values each time; set a random seed if you want repeatable results.

Two attitudes to keep throughout. A result is a lead, not a verdict. And the sample you have is not the world.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can summarise a variable with a centre and a spread, and choose between the mean and the median.
- You can explain what a standard error is and why quadrupling the sample halves it.
- You can compute and interpret a correlation, and say what it does not tell you.
- You can recognise a confounder and a Simpson's paradox when you see group tables.
- You can state in plain words what a p-value is and what it is not.
- You can turn a vague question into a testable one: outcome, comparison, unit.

### Core ideas

#### 1. Centre and spread: mean, median and standard deviation

The **mean** is the sum divided by the count. The **median** is the middle value after sorting. They answer different questions, and they split apart when the data has outliers. Take five delivery times in minutes: 2, 3, 3, 4, 18. The mean is 30 / 5 = 6. The median is 3. One slow delivery drags the mean to twice the median.

**Spread** says how far values typically sit from the centre. The sample standard deviation squares each distance from the mean, adds them, divides by n - 1 (not n, because the mean was estimated from the same data), and takes the square root. Distances from 6: -4, -3, -3, -2, 12. Squares: 16, 9, 9, 4, 144, summing to 182. Divide by 4 to get 45.5, and the square root is 6.75. Remove the 18 and the four values 2, 3, 3, 4 have mean 3 and a standard deviation of 0.82. One value changed the spread from 0.82 to 6.75.

Practical rule: look at the whole distribution (a histogram or a sorted list) before choosing a summary. For skewed things such as incomes, delays and order sizes, report the median, or both. The mean is still the right tool when you care about totals: total cost is the mean times the count, which a median cannot give you.

#### 2. Sampling and the standard error

You almost never see the whole population; you see a sample and use it to estimate something. A different sample would give a different answer, and the **standard error** (SE) says by how much, typically. For a mean, SE = standard deviation / sqrt(n).

Suppose a sample of 100 customers has a mean spend of 50 and a standard deviation of 20. SE = 20 / sqrt(100) = 2. An approximate 95% interval is the mean plus or minus 1.96 SE, so 50 +/- 3.92, or 46.1 to 53.9. Now collect 400 customers with the same spread: SE = 20 / sqrt(400) = 1, and the interval is 48.0 to 52.0. Four times the data bought half the uncertainty. That square-root law explains why precision gets expensive.

Two warnings. First, the formula assumes your sample is representative. A survey of people who answered an email tells you about people who answer emails, however many reply: more data does not fix a biased sample. Second, an interval describes uncertainty about the estimate, not the range of individual values. Most individual customers will not fall between 46.1 and 53.9.

#### 3. Correlation: how much two variables move together

Correlation (Pearson's r) runs from -1 to +1 and measures how closely points follow a straight line. Take x = 1, 2, 3, 4, 5 and y = 2, 4, 5, 4, 5. The means are 3 and 4. Deviations of x: -2, -1, 0, 1, 2. Deviations of y: -2, 0, 1, 0, 1. Multiply pairwise and add: 4 + 0 + 0 + 0 + 2 = 6. Sum of squared x deviations: 10. Sum of squared y deviations: 6. Then r = 6 / sqrt(10 x 6) = 6 / 7.746 = 0.775.

How to read it: 0.775 is a fairly strong straight-line relationship, and r squared is 0.60, the share of the variation in y a straight line through x accounts for. What r does not say: that x causes y, that the relationship is a straight line (a perfect curve can have r near 0), or that it will hold for values outside those you saw. One extreme point can create or destroy a correlation, so always plot the data first. With only five points, r = 0.775 is also very uncertain: the same data would be compatible with a wide range of true correlations.

#### 4. Confounding and Simpson's paradox

A **confounder** is something that influences both the thing you think is the cause and the outcome. Ice cream sales and drownings rise together because both rise in summer. The famous version in group data is **Simpson's paradox**: a comparison reverses when you split by a hidden group. A classic textbook example compares two treatments for kidney stones, split by stone size.

| | Small stones | Large stones | Overall |
|---|---|---|---|
| Treatment A | 81 / 87 = 93% | 192 / 263 = 73% | 273 / 350 = 78% |
| Treatment B | 234 / 270 = 87% | 55 / 80 = 69% | 289 / 350 = 83% |

A wins in both groups, yet B wins overall. The reason: A was given mostly to the harder, large-stone cases and B mostly to the easy, small-stone ones. Group size acts as a confounder, because it influenced both which treatment was used and the chance of success.

The lesson is not "always split by everything" (that leads to other mistakes). It is: before believing a comparison, ask how the two groups came to be different, and whether something else explains the gap. Randomly assigning treatment, covered at Level 2, is the one clean cure, because it cuts the link between group and everything else.

#### 5. What a p-value is, and is not

Suppose you flip a coin 100 times and get 60 heads. Is it biased? A p-value answers one narrow question: if the coin really were fair, how often would you see a result at least this extreme? For a fair coin, 100 flips give 50 heads on average with a standard deviation of sqrt(100 x 0.5 x 0.5) = 5. Sixty heads is 2 standard deviations out. The exact two-sided probability of 60 or more heads, or 40 or fewer, is about 0.057. So a fair coin produces a result this lopsided about 6 times in 100 sets of flips.

What the p-value is not: it is not the probability that the coin is fair, not the probability that your result is a fluke, and not a measure of how important the effect is. It also does not tell you how biased the coin is. The more useful report is an estimate with an interval: 60% heads, with a 95% interval of roughly 50% to 70%.

The convention of calling p below 0.05 "significant" is a habit, not a law of nature. A result at 0.049 and one at 0.051 carry almost the same evidence. Report the number, the size of the effect and the interval, and let the reader judge.

The same discipline applies before you start: turn a vague question into a testable one by naming the **outcome** (the number that would show it worked), the **comparison** (against what) and the **unit** (what counts as one independent observation), and write the decision rule down before you look at results.

### Practice on your own

1. Make a column of 30 delivery times (mostly 20 to 40 minutes, with two or three at 120). Compute the mean, median and standard deviation, then remove the outliers and recompute. Write one sentence on what changed.
2. Simulate sampling: generate 10,000 values from a skewed distribution, draw 1,000 random samples of size 25 and 1,000 of size 100, and compare the spread of the sample means. Confirm the ratio is near 2.
3. Enter x = 1 to 5, y = 2, 4, 5, 4, 5 in a spreadsheet, compute r with a correlation function and match 0.775. Then change the last y to 20 and watch r move.
4. Build the kidney stone table in a spreadsheet and compute each rate and the overall rates. Explain the reversal in two sentences.
5. Flip a coin (or simulate it) 100 times, 1,000 times over. Count how often you get 60 or more heads or 40 or fewer, and compare with 0.057.
6. Write one real question from your own life or work as outcome, comparison, unit and decision rule.

### Exercises

1. Compute the mean and median of 4, 8, 8, 10, 40. Which would you report for "typical", and why?
2. Compute the sample standard deviation of 2, 4, 6.
3. A sample of 64 has mean 30 and standard deviation 12. Give the standard error and an approximate 95% interval.
4. How large a sample do you need to halve that standard error?
5. Compute r for x = 1, 2, 3 and y = 3, 2, 1, without calculating: what must it be, and why?
6. In a survey, 70 of 100 people who opened your email say they like the product. Give two reasons you cannot conclude 70% of customers like it.
7. A study reports p = 0.03. A colleague says "so there is a 97% chance the effect is real". What is wrong?

### Answers and hints

1. Mean 70 / 5 = 14; median 8. The median describes the typical value; the 40 pulls the mean up. If you need total volume, the mean is the right tool.
2. Mean 4; deviations -2, 0, 2; squares sum to 8; divide by 2 gives 4; the standard deviation is 2.
3. SE = 12 / 8 = 1.5; interval 30 +/- 2.94, about 27.1 to 32.9.
4. Four times as much: 256, because SE shrinks with the square root of n.
5. Exactly -1: the points lie on a perfect downward line.
6. The respondents opened the email (self-selection), and people who like the product are more likely to open and answer. Also the sample is small, so the interval is wide, roughly 61% to 79%.
7. A p-value is computed assuming there is no effect. It is not the probability that the effect is real. The probability depends on how plausible the effect was before the study.

### Checkpoint

Say aloud:

1. When do the mean and the median differ most, and which do you trust then?
2. Why divide by n - 1 for a sample standard deviation?
3. What does a standard error measure, and what does quadrupling the sample do?
4. What can r not tell you?
5. What is a confounder? Give your own example.
6. In one sentence, what is a p-value?
7. What are the three parts of a testable question?

Common mistakes:

- Reporting a mean for skewed data without looking at the distribution.
- Reading a correlation as a cause.
- Treating a big sample as a cure for a biased sample.
- Saying "significant" without giving the size of the effect.
- Choosing the success criterion after seeing the results.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can estimate the difference between two groups, with an interval and an effect size.
- You can run a two-proportion comparison and a Welch t-test and read both.
- You can compute a rough sample size before an experiment and say whether a past one was big enough.
- You can use a permutation test and a bootstrap when formulas do not fit.
- You can adjust for several tests and say how many false positives to expect.
- You can design a simple randomised experiment and check it for basic problems.

### Core ideas

#### 1. Estimating a difference, with an interval

The question "did B beat A?" is best answered with the size of the gap and its uncertainty. Suppose version A converts 200 of 2,000 visitors (10%) and version B converts 240 of 2,000 (12%). The difference is 2 points. The standard error of a difference of two proportions is sqrt(p1(1 - p1)/n1 + p2(1 - p2)/n2) = sqrt(0.1 x 0.9 / 2,000 + 0.12 x 0.88 / 2,000) = sqrt(0.000045 + 0.0000528) = 0.0099, about one point. A 95% interval is 2 +/- 1.96 x 0.99, which is about 0.1 to 3.9 points. The matching test statistic is 2.02 and the p-value is about 0.043.

So the honest report is: "B converted about 2 points better (95% interval roughly 0.1 to 3.9 points)." Note how wide that is: the data fit a gain of almost nothing and a gain of nearly four points. The p-value just under 0.05 hides that. Always give the interval.

For means, Welch's t-test is the safe default for comparing two groups: it does not assume equal spreads or equal sizes. The difference of means has standard error sqrt(s1²/n1 + s2²/n2), and software does the rest. Always decide beforehand whether you are interested in one direction or both; the default is both.

#### 2. Effect size and statistical versus practical significance

A **p-value** reflects both the size of an effect and the size of the sample. With enough data, a trivial effect becomes "significant". Suppose two groups have standard deviation 10 and sizes 20,000 each, and a gap of 0.5. The standard error of the gap is 10 x sqrt(2 / 20,000) = 0.1, so the test statistic is 5 and the p-value is far below 0.001. Yet 0.5 on a spread of 10 is tiny.

An **effect size** puts the gap on a common scale. Cohen's d is the gap divided by the pooled standard deviation: here 0.5 / 10 = 0.05. Common rough labels are 0.2 small, 0.5 medium, 0.8 large, but treat them as a starting point, since what matters is the context. A 0.5-minute cut in delivery time may be worth millions across a fleet, or nothing.

The practical report has three parts: the gap in real units, its interval, and a sentence about whether it matters to the decision. The reverse also happens: with a small sample a large and genuinely important effect can fail to reach p below 0.05. "Not significant" means "not shown", not "not there".

#### 3. Power and sample size

**Power** is the probability that a test detects an effect of a given size if it is really there. It depends on the effect size, the spread, the sample size and the significance level. For a two-group comparison of proportions at the 5% level (two-sided) and 80% power, a common approximation is n per group = (1.96 + 0.84)² x (p1 q1 + p2 q2) / (p1 - p2)².

For 10% against 12%: (2.80)² = 7.85; p1 q1 + p2 q2 = 0.09 + 0.1056 = 0.1956; (0.02)² = 0.0004. So n = 7.85 x 0.1956 / 0.0004, about 3,840 per group. The test in idea 1 used 2,000 per group, so its power for a true 2-point lift was only about 52%: it was nearly a coin flip whether it would "detect" a real improvement. That is also why its interval was so wide.

Plan the sample before you run the experiment, not after. If you cannot afford the sample you need, either target a bigger effect, accept lower power and say so, or do not run a test that cannot answer the question. A test stopped early because "it looks significant" breaks the error rates and inflates false positives.

#### 4. Permutation tests and the bootstrap

When formulas do not fit, resampling gives the same answers with no algebra. A **permutation test** asks: if the group labels meant nothing, how often would shuffling them give a gap at least this large? Group A has values 3, 5, 7 (mean 5) and group B has 6, 8, 10 (mean 8), a gap of 3. There are 20 ways to choose which three of the six values are labelled A. The gap is (2 x sum of A - 39) / 3, so a gap of 3 or more in either direction needs the sum of A to be at most 15 or at least 24. Counting the 20 splits, 4 qualify (sums 14, 15, 24, 25). So the two-sided p-value is 4 / 20 = 0.20. With six data points nothing can be shown, which is the honest answer.

The **bootstrap** gives an interval: resample each group with replacement, same size, thousands of times, compute the statistic each time, and take the 2.5th and 97.5th percentiles. It works for medians, ratios and other awkward quantities. Its weakness is tiny samples and heavy tails: it cannot invent information the sample lacks. Resample the **unit of analysis**: resample days, not rows within days, if days are what vary independently.

#### 5. Many tests, and what to do about them

Each test at the 5% level has a 5% chance of a false alarm when nothing is going on. Run 20 independent tests and the chance of at least one false alarm is 1 - 0.95^20, about 64%; expect one false positive on average. Reporting only the one that "worked" is the classic way to mislead without lying.

Two remedies. First, **state the primary question in advance** and treat everything else as exploratory, to be confirmed with fresh data. Second, **adjust**. The simplest adjustment is Bonferroni: divide the threshold by the number of tests. With 5 tests the threshold is 0.01. If the p-values are 0.012, 0.03, 0.04, 0.20 and 0.60, none passes, though three are below 0.05. Bonferroni is conservative; other methods trade a little power for control of the false-discovery rate. Either way, tell the reader how many comparisons you looked at, including the ones you quietly dropped.

#### 6. Randomised experiments, and how they go wrong

Random assignment makes the groups the same on average in everything, including things you never measured. That is why a well-run experiment supports a causal claim in a way no analysis of observational data can. The steps: choose the unit (user, store, day), randomise at that unit, fix the outcome and the sample size in advance, run for the planned time, and analyse as planned.

Check for **sample ratio mismatch**. If you planned a 50/50 split of 10,000 users and got 5,200 and 4,800, the expected spread is sqrt(10,000 x 0.5 x 0.5) = 50, so a gap of 200 from 5,000 is 4 standard deviations: the chance under a true 50/50 split is about 6 in 100,000. Something is broken in the assignment or the logging, and the results cannot be trusted until it is fixed.

Other traps: users who see both versions, a novelty effect that fades after the first week, peeking and stopping early, and treating clicks as independent when users are the true unit. Many business changes cannot be randomised; Level 4 returns to that.

### Practice on your own

1. Compute the 10% versus 12% comparison by hand, then with a library function for a two-proportion test, and match the interval and p-value.
2. Simulate 1,000 experiments with a true 2-point lift (10% to 12%) and 2,000 per group. Count the share that reach p below 0.05; it should be near 50%. Repeat with 3,840 per group and see about 80%.
3. Reproduce the permutation test on 3, 5, 7 and 6, 8, 10 by enumerating all 20 splits in a script. Check 0.20.
4. Run 20 comparisons of random noise against random noise, 500 times. Count how often at least one is "significant", and compare with 64%.
5. Generate two groups of 20,000 with a true gap of 0.5 on a spread of 10. Run a t-test, compute Cohen's d, and write what you would tell a manager.
6. Simulate a 50/50 assignment of 10,000 users 1,000 times. How often is the split worse than 5,200 / 4,800?

### Exercises

1. A: 30 of 300 convert; B: 45 of 300. Compute the difference in points, its standard error, and an approximate 95% interval.
2. A study finds a gap of 0.3 with p = 0.001 and Cohen's d = 0.03. Is this good news? Explain.
3. How many tests at the 5% level give a 50% chance of at least one false positive? (Estimate with 1 - 0.95^k.)
4. Why does peeking at an experiment every day and stopping when p is below 0.05 give too many false positives?
5. Use the permutation method for groups 1, 2 against 3, 4 (means 1.5 and 3.5). What is the smallest two-sided p-value possible with so few points?
6. With 8 tests and Bonferroni, what threshold applies? Would p = 0.01 pass?
7. You planned 1,000 users per arm but got 1,060 and 940. Compute the test statistic and decide whether to worry.
8. Explain, as to a manager, why "no significant difference" does not mean "no difference".

### Answers and hints

1. Rates 10% and 15%, difference 5 points. SE = sqrt(0.1 x 0.9 / 300 + 0.15 x 0.85 / 300) = sqrt(0.0003 + 0.000425) = 0.0269. Interval 5 +/- 5.3, about -0.3 to +10.3 points. It just includes zero.
2. Probably not. The effect is tiny relative to the spread (d = 0.03); the tiny p-value comes from a huge sample. Whether 0.3 matters depends on the cost and the unit.
3. 1 - 0.95^13 = 0.487 and 1 - 0.95^14 = 0.512, so about 14 tests.
4. Each look is another chance for noise to cross the threshold, so the overall false-positive rate is far above 5%. Fix the sample size beforehand, or use a method designed for sequential looks.
5. There are 6 ways to choose two of four values for group one. The most extreme splits are {1,2} and {3,4}, each giving a gap of 2, so 2 of 6 = 0.33 two-sided. With four data points you can never get below 0.33.
6. 0.05 / 8 = 0.00625, so p = 0.01 does not pass.
7. Expected 1,000 each; SD = sqrt(2,000 x 0.25) = 22.4; (1,060 - 1,000) / 22.4 = 2.7. Yes, worry: about 7 in 1,000 by chance, so investigate before trusting results.
8. "Not significant" means the data did not rule out zero; it may also not rule out a large effect. Show the interval and say what sizes of effect it covers.

### Checkpoint

Say aloud:

1. What belongs in the report of an A/B test beyond "significant"?
2. Why can a trivial effect be significant, and an important one not?
3. What decides how large an experiment must be?
4. When would you choose a permutation test or a bootstrap?
5. What is the chance of a false positive across 20 tests?
6. Why does random assignment support a causal claim?
7. What is sample ratio mismatch and what do you do about it?

Common mistakes:

- Reporting a p-value with no interval and no size.
- Running a test that could never have detected the effect you hoped for.
- Stopping when the number first looks good.
- Counting rows as independent when users or days are the real unit.
- Reporting the one significant result out of many.

## Level 3: Advanced

### What you will be able to do

- You can fit a straight line by hand, read its slope, intercept and R², and check the residuals.
- You can evaluate any model against a baseline on data it has not seen, with a split that respects time.
- You can explain overfitting and spot it from the gap between training and test error.
- You can read a confusion matrix and choose between precision, recall and accuracy for a decision.
- You can scale features, cluster with k-means, and judge a clustering honestly.
- You can backtest a forecast against naive and seasonal-naive baselines.

### Core ideas

#### 1. Linear regression, by hand

Regression fits the line that minimises the sum of squared vertical gaps. Reuse the data from Level 1: x = 1 to 5, y = 2, 4, 5, 4, 5. The slope is the sum of the x and y deviation products over the sum of squared x deviations: 6 / 10 = 0.6. The intercept makes the line pass through the means: 4 - 0.6 x 3 = 2.2. So the prediction is y = 2.2 + 0.6x: each extra unit of x goes with 0.6 more y, on average.

Predictions at x = 1 to 5: 2.8, 3.4, 4.0, 4.6, 5.2. Residuals (actual minus predicted): -0.8, 0.6, 1.0, -0.6, -0.2, which add up to zero. The sum of squared residuals is 0.64 + 0.36 + 1.00 + 0.36 + 0.04 = 2.40. The total variation in y (sum of squared deviations from its mean) is 6. So R² = 1 - 2.40 / 6 = 0.60, matching r squared from before.

Read slope with care. It says "associated with", not "causes", unless the data came from an experiment. Plot residuals against the fitted values: a curve or a fan shape means a straight line is the wrong shape or the spread changes. Predicting at x = 6 gives 5.8, but extrapolating beyond the data you have seen is a guess, not an estimate. Add more predictors and the same logic holds: each coefficient is the association holding the others fixed, which is only meaningful if the predictors are not nearly copies of each other.

#### 2. Honest evaluation: a baseline and a held-out test

A model is judged on data it never saw during fitting. Split the data into a training part to fit on and a test part to score on. When time matters, split by date: train on the past, test on the most recent stretch. A random split lets the model peek at days next to those it is tested on, and the score flatters it.

Always compare with a **baseline**: the simplest sensible predictor, usually "predict the training average" for numbers or "predict the most common class". Suppose the training mean is 45 and four test values are 40, 50, 60, 70. The baseline predicts 45 each time, with errors 5, 5, 15, 25, so the mean absolute error (MAE) is 50 / 4 = 12.5. A model predicting 42, 53, 58, 66 has errors 2, 3, 2, 4, an MAE of 11 / 4 = 2.75. It beats the baseline by a wide margin. Had it scored 12, it would have earned nothing.

Keep the test set untouched until the end. If you try many models and keep the best test score, you have used the test set to choose, and the score is optimistic. For choices, use a separate validation set or cross-validation, and score the winner once on the test set. With a few hundred rows, expect the test score to be noisy: report an interval, or repeat across several time splits.

#### 3. Overfitting

A model that is too flexible learns the noise in the training data. Take 10 points that follow a gentle line plus random noise. A ninth-degree polynomial can pass through all 10 exactly: training error is zero. On new points it swings wildly between and beyond the training values, and test error is far larger than that of a straight line. The signature of overfitting is a large gap: very low training error, much higher test error.

Remedies, roughly in order of how often they help: more data; a simpler model; fewer features; **regularisation** (a penalty on large coefficients, as in ridge and lasso regression); for trees, limits on depth; and early stopping. Complexity is not a virtue. If a straight line scores nearly as well as a boosted ensemble, use the line: it is faster, easier to explain and less likely to break.

Leakage is the sneaky cousin: a feature that carries the answer, such as profit when predicting revenue, or a field recorded after the outcome. A test score that looks too good to be true, such as R² of 0.99 on a messy business problem, should send you hunting for leakage before you celebrate. Ask of every feature: will I know this at the moment I need the prediction?

#### 4. Classification metrics and rare events

Predicting a category (will this order be late?) needs different scores. Take 1,000 orders, of which 50 are late. A model flags 60 orders; of those, 30 are really late. The **confusion matrix**: true positives 30, false positives 30, false negatives 20 (late orders missed), true negatives 920.

Accuracy = (30 + 920) / 1,000 = 95%. Sounds excellent, but a model that never flags anything scores 950 / 1,000, also 95%, while catching nothing. This is the **accuracy trap** for rare events. **Precision** = 30 / 60 = 50% (of flagged orders, how many were truly late). **Recall** = 30 / 50 = 60% (of late orders, how many were caught). The F1 score, the harmonic mean, is 2 x 0.5 x 0.6 / 1.1 = 0.545.

Which to favour depends on cost. If a missed late order costs 50 and a false alarm costs 5, recall matters more; if each flag triggers an expensive manual check, precision does. Most models output a probability, and the **threshold** at which you act is a business decision: lowering it catches more events and adds more false alarms. Choose it from costs, on a validation set, not from the default of 0.5.

#### 5. Clustering: grouping without labels

Clustering groups similar items when there is no right answer to learn from, as in customer or store segments. K-means picks k centres and assigns each point to the nearest one, then moves each centre to the mean of its points, and repeats.

Tiny example: values 1, 2, 3, 10, 11, 12 with k = 2 and centres 2 and 11. The groups are {1, 2, 3} and {10, 11, 12}, and the within-group sum of squared distances is (1 + 0 + 1) + (1 + 0 + 1) = 4. The **silhouette** score checks fit: for the point 1, the mean distance to its own group is (1 + 2) / 2 = 1.5, and to the other group (9 + 10 + 11) / 3 = 10; its silhouette is (10 - 1.5) / 10 = 0.85, close to the maximum of 1.

Two rules. **Scale features first**: k-means uses distances, so a column in hundreds (revenue) swamps one in fractions (margin). Units A (revenue 500, margin 0.30), B (520, 0.10) and C (900, 0.30): unscaled, A is 20 from B and 400 from C, so margin is effectively ignored. Second, **clusters are a description, not a discovery**: different features, scaling or k give different groups. Choose k with the silhouette as a guide, but also ask whether each group can be named and treated differently. With only a dozen items, treat the result as exploration.

#### 6. Forecasting and the backtest

A forecast is a prediction about the future, so test it by hiding the most recent stretch and predicting it (a **backtest**). Two baselines: **naive** (repeat the last value) and **seasonal naive** (repeat the same period one cycle ago).

Example with a weekly pattern. Week 1: 100, 110, 120, 130, 140, 200, 220. Week 2: 104, 112, 124, 134, 146, 204, 224. Actuals for week 3: 108, 118, 128, 138, 150, 208, 230. Naive repeats 224 seven times, with absolute errors 116, 106, 96, 86, 74, 16, 6, so MAE = 500 / 7 = 71.4. Seasonal naive repeats week 2, with errors 4, 6, 4, 4, 4, 4, 6, so MAE = 32 / 7 = 4.6. The seasonal rule is better by a factor of 15 with no modelling at all, and any fancy model must beat 4.6 to earn its keep.

Plot forecasts against actuals, not only the score. Measure error in the same unit the decision uses. Be careful with ratios such as MAPE when actual values can be near zero. One backtest window is one reading: repeat over several windows ("rolling origin") when you can. And remember a forecast assumes the future resembles the past; holidays, price changes and promotions break that, so say so.

### Practice on your own

1. Fit y = 2.2 + 0.6x by hand for the five points, then confirm with a library. Compute residuals, SSE and R², and plot residuals.
2. Generate 120 days of data for a numeric target (a weekday effect, a trend, noise). Train on the first 96 days, test on the last 24, and compute the baseline MAE and a linear model's MAE.
3. Fit polynomial models of degree 1, 3 and 9 to 10 noisy points. Print training and test error for each and see the gap widen.
4. Build a rare-event dataset (5% positive). Train a classifier, compute the confusion matrix, accuracy, precision and recall, and compare with "never flag".
5. Create unit-level features (average revenue, margin, problem rate) for 12 units. Cluster with and without scaling, compare silhouette scores for k = 2 to 5, and name the groups.
6. Reproduce the two-baseline forecast example with the numbers above, then extend it to a longer weekly series and run three rolling backtest windows.

### Exercises

1. Fit the line for x = 1, 2, 3 and y = 2, 4, 6. What are slope, intercept and R²?
2. The training mean is 100; test values are 90, 110, 130. Compute the baseline MAE. A model predicts 95, 105, 125; compute its MAE.
3. A model has training MAE 1.0 and test MAE 9.0. What is the likely problem, and name two remedies.
4. Out of 200 cases, 10 are positive. A model flags 20, of which 8 are true positives. Compute accuracy, precision and recall.
5. Why must you scale before k-means?
6. Seasonal naive uses the last week as the forecast. Why can it beat a complicated model in a backtest, and when will it fail?
7. A colleague scores 15 models on the test set and reports the best. What is wrong?
8. Without computing, explain why reducing the threshold raises recall and lowers precision.

### Answers and hints

1. The points lie on a perfect line: slope 2, intercept 0, R² = 1.
2. Baseline errors 10, 10, 30; MAE = 50 / 3 = 16.7. Model errors 5, 5, 5; MAE = 5.
3. Overfitting (or leakage in training only). Simplify the model, regularise, add data or remove features.
4. TP 8, FP 12, FN 2, TN 178. Accuracy 186 / 200 = 93%; precision 8 / 20 = 40%; recall 8 / 10 = 80%. (Never flagging would score 95% accuracy.)
5. K-means uses distances; unscaled large-unit columns dominate and the rest are ignored.
6. Strongly repeating patterns are hard to beat, and many complex models add only noise. It fails when the pattern changes: holidays, trends, level shifts.
7. The best of 15 is optimistic because the test set has been used for selection. Use validation data for choosing and score the final choice once, on untouched data.
8. A lower threshold flags more cases: more real positives are caught (recall up), but more non-events are flagged too (precision down).

### Checkpoint

Say aloud:

1. What do the slope, intercept and R² of a regression mean?
2. Why a time split, and why a baseline?
3. What is the signature of overfitting?
4. Why is accuracy a poor score for rare events?
5. How do you choose a threshold?
6. Why scale before clustering, and why are clusters not discoveries?
7. What does a backtest tell you, and what does it not?

Common mistakes:

- Using a random split on time-ordered data.
- Reporting a model score with no baseline beside it.
- Selecting on the test set and reporting the same number.
- Using accuracy for a rare event.
- Clustering unscaled features and believing the result.
- Extrapolating a regression beyond the data.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can say when a question needs a causal answer, and what design or assumptions that demands.
- You can plan an analysis so that the number of comparisons you make is honest.
- You can make your work reproducible and reviewable by someone else.
- You can review another scientist's analysis and list what you would ask before agreeing.
- You can check a model for different error rates across groups and describe the trade-offs.
- You can communicate uncertainty and limits to a non-technical audience without hiding them.

### Core ideas

#### 1. Prediction versus explanation versus cause

Three different questions use the same tools. **Prediction**: what will happen? A model can predict well using proxies that nobody could change. **Explanation**: which factors go with the outcome? Descriptive, and prone to confounding. **Cause**: what would happen if we changed something? This needs an experiment or strong assumptions.

Example. Stores with a loyalty programme have higher sales, and a regression says the programme adds 12% revenue. But bigger stores were more likely to adopt the programme, and bigger stores sell more. The 12% is partly size. A randomised rollout across comparable stores would answer the causal question. When randomisation is impossible, there are quasi-experimental designs (before and after with a comparison group, matching, regression discontinuity), each resting on assumptions you must state and defend. Say plainly which of the three questions you answered. "Stores with the programme sell more" is explanation; "the programme raises sales" is cause and needs more than a regression.

#### 2. The garden of forking paths

Every analysis involves choices: which outcome, which subgroup, which time window, how to treat outliers. Each choice multiplies the number of comparisons you could have made, even if you ran only one. Suppose you could look at 4 outcome metrics, in 3 customer groups, over 2 time windows: 24 comparisons. The chance that at least one reaches p below 0.05 by luck alone is 1 - 0.95^24 = 71%.

Protect yourself and your readers. **Pre-register** the plan: write down the question, outcome, groups, window, exclusion rules and decision threshold before looking at results. Keep exploratory findings labelled as such, and confirm them on fresh data or a held-out period. If you made choices after seeing the data, say which and report the alternatives. Resist excluding "outliers" because they spoil the result; set the rule in advance or show both versions. This is not bureaucracy: it is the difference between a finding and a coincidence.

#### 3. Reproducibility

If you cannot rerun your analysis, nobody, including you in six months, can trust it. The minimum: the raw data stays untouched and every transformation is in code; random seeds are set and recorded; the versions of libraries are noted; results are generated by one command from raw to final numbers; and the code lives in version control with readable commit messages. A notebook that only works when cells are run in the order you remember is not reproducible; restart and run it from top to bottom before sharing.

Record decisions as well as code: why a row was dropped, which definition you used, which alternatives you tried. A short README stating the question, the data source and date, the result and the caveats saves hours. Where data is confidential, share the code and a synthetic sample, never the data itself. Tracking tools for experiments exist (see Part 3), but a dated folder and a plain log beat chaos.

#### 4. Reviewing someone else's analysis

Review is the most valuable thing a senior scientist does. Use a standing list. What exactly is the question, and was it set before the analysis? What is the unit, and is it treated as independent when it is not? How many comparisons were made? Is there a baseline, and a fair split? Could any feature leak the answer? Are intervals and effect sizes shown, not only p-values? Does the sample represent the population the claim is about? Do the numbers reconcile with a known total? Would a different reasonable choice change the conclusion?

Example: a colleague says a new onboarding "increased retention, p = 0.04". You ask: how many other outcomes did you check (if ten, the 0.04 is unremarkable)? Were users randomised or self-selected? What is the interval? What was the ratio of users in each arm, and does it match the plan? Review the work, not the person; ask for the code, the plan and the raw counts, in that order. Praise what is solid, so that your criticisms are heard.

#### 5. Fairness, ethics and honesty

Models that look accurate overall can fail some groups more than others. Take a model that flags risky cases at one threshold. In group P, 100 of 1,000 are truly risky and the model catches 60 (recall 60%). In group Q, 100 of 1,000 are truly risky and it catches 30 (recall 30%). The overall number hides the fact that twice as many risky cases in Q go undetected, and if the flag triggers help, Q loses out. Check scores by group wherever a decision affects people, and discuss what "fair" should mean, since several reasonable definitions (equal recall, equal precision, equal flag rates) cannot all hold at once when base rates differ.

Other duties. Use the minimum personal data and aggregate where you can. Do not use a proxy (such as postcode) in a way that reproduces a protected characteristic. Say what the model must not be used for. Do not tune the analysis to the answer a sponsor wants; when pressed, say "the data does not support that" and show what it does support. If an AI assistant helped write the code, you remain responsible: verify it yourself. Findings are leads, not verdicts, until replicated.

#### 6. Operating at team scale

On a team, the failure modes shift from statistics to process. Agree definitions of outcomes and metrics once and keep them in one place. Keep an analysis log of questions, plans and results, including null results, so the team does not rerun failed ideas and so that "we found nothing" is a visible, respected outcome. Use code review for analyses, as engineers do for software. Maintain a library of experiment templates, with sample size calculators and a checklist for sample ratio and instrumentation.

Set up a cadence for revisiting old results: effects found in experiments often shrink when rolled out, and models decay. Keep a standing habit of asking "what would change my mind?" and writing the answer down. Finally, teach: the most useful scientist on a team is the one who helps a product manager ask a testable question and understand a wide interval.

### Practice on your own

1. Take an analysis you did earlier and write a one-page plan as if before the work: question, outcome, unit, groups, window, decision rule. Compare it with what you actually did and list each deviation.
2. Simulate a confounded dataset: store size drives both programme adoption and sales, with no programme effect. Fit a regression of sales on adoption and see the spurious effect, then add size as a predictor.
3. Count your comparisons: run a "fishing expedition" on a random-noise dataset, and report how many comparisons reach p below 0.05.
4. Make an analysis reproducible: raw data untouched, one script from raw to results, seeds recorded, a README. Hand it to someone and have them rerun it.
5. Review a published analysis (a blog post or a paper that you can access) with the standing list and write five comments.
6. Take a classifier you built, compute recall and precision for two subgroups, and write a paragraph on whether you would deploy it.

### Exercises

1. Name the question type (prediction, explanation or cause) for each: "Which customers will churn?"; "What distinguishes churners?"; "Will a discount reduce churn?"
2. You looked at 6 outcomes in 5 segments. How many comparisons, and what is the chance of at least one false positive at the 5% level?
3. Describe how you would test whether a loyalty programme raises sales when you cannot randomise customers.
4. A model has overall accuracy 94% but recall of 80% for group P and 40% for group Q. Write three questions to ask before deploying.
5. List five things that must be in a README for a reproducible analysis.
6. A sponsor asks you to drop two "bad" weeks from the data because they spoil the result. What do you do?

### Answers and hints

1. Prediction; explanation; cause.
2. 30 comparisons; 1 - 0.95^30 = 78.5%.
3. Use a comparison group: a before-and-after comparison between adopting and similar non-adopting stores (difference in differences), or matched stores, stating the assumption that both groups would have moved alike without the programme and checking pre-trends. Report it as weaker than a randomised test.
4. Why does recall differ, and is the data in Q thinner or different? What does a miss cost in each group? Can the threshold or features be changed, and what would that trade off? Who will monitor group performance after launch?
5. The question; data source and extraction date; how to run it; software versions and seeds; the result and caveats; known data problems.
6. Ask why the weeks are bad. Set a rule on grounds that are independent of the result (for example, a documented outage), apply it consistently, and report the results with and without the weeks. Do not drop them just because they spoil the result.

### Checkpoint

Say aloud:

1. What is the difference between predicting and causing?
2. What are forking paths and how do you reduce them?
3. What makes an analysis reproducible?
4. What are your first five review questions for someone else's results?
5. Why can good overall accuracy hide unfair outcomes?
6. What do you do when a sponsor wants a particular answer?
7. What would you keep in a team analysis log?

Common mistakes:

- Selling a prediction or an association as a cause.
- Deciding the analysis after seeing the data and reporting only the winner.
- Sharing a notebook that cannot be rerun.
- Reviewing the headline instead of the plan and the counts.
- Reporting overall accuracy for decisions that affect groups differently.
- Hiding null results.

## Capstone projects

### 1. An A/B-style analysis write-up (small, about 10 hours)

**Brief.** Use real open data or a simulation you build with a known effect (for example, two page versions with conversions, or two delivery routes with times). Write the plan first, then analyse and report.

**Deliverables.** A one-page plan written before analysis; a one-page report with the effect in real units, its interval, an effect size, and a paragraph on what you would not claim; the code; a power and sample-size note.

**Self-assessment rubric** (0 = missing, 1 = partly, 2 = solid; aim for 9 of 12):

- The plan predates the analysis and names outcome, comparison, unit
- The interval and the effect size are reported, not only p
- The unit of analysis is correct
- The sample size was judged against the effect you cared about
- The report states what it does not show
- The code reruns from raw data

### 2. Segmentation with an action per segment (medium, about 25 hours)

**Brief.** Build a feature table for at least 30 entities (customers, stores, routes), scale it, cluster with several k values, and choose and name the segments. Test stability by changing the features or the random seed.

**Deliverables.** Feature definitions; silhouette scores for k = 2 to 6; a profile table per segment; names and one recommended action for each; a stability check; a caveats paragraph.

**Rubric** (0 to 2; aim for 11 of 14):

- Features are defined, and ratios use sums
- Features are scaled and the reason is stated
- The choice of k is justified with more than the silhouette
- Each segment has a meaningful name
- Each segment has an action and a way to measure it
- Stability was tested
- The caveats mention small samples and feature dependence

### 3. A forecast that beats seasonal naive (large, about 50 hours)

**Brief.** Choose a time series with at least a year of daily or weekly data (open data or a simulation with trend, seasonality and a shock). Build a forecast, backtest it over several rolling windows, and compare with naive and seasonal-naive baselines. Add a short model card.

**Deliverables.** Backtest design and code; a table of errors per window and method; plots of forecasts against actuals; the final model with intervals; a model card (purpose, data, performance, limits, what would break it); a review by another person.

**Rubric** (0 to 2; aim for 14 of 18):

- Splits respect time, with several windows
- Both baselines are included and beaten, or the report says they were not
- The error measure suits the decision
- No feature leaks the future
- Forecast intervals are shown and their coverage checked
- The model card states limits and failure conditions
- Shocks and holidays are handled or acknowledged
- A reviewer's comments are answered
- Everything reruns from raw data

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| Spreadsheet | First looks, small simulations, hand-checking formulas | When data or repetition exceeds what cells can handle |
| Python (pandas, numpy, scipy) or R | Data wrangling, tests, resampling, simulation | Rarely; you learn more libraries |
| scikit-learn (or R equivalents) | Regression, classification, clustering, evaluation tools | When you need specialised or large-scale methods |
| statsmodels (or R's built-in modelling) | Regression with full statistical output, intervals, diagnostics | When models need custom likelihoods or Bayesian methods |
| Notebooks (Jupyter-style) | Exploration with notes beside code | When work must run unattended or be reviewed as code |
| Version control (git) | History, collaboration, reproducibility | Never |
| SQL | Getting and shaping data at the source | Never |
| Gradient boosting, SHAP-style explanations, deep learning | Stronger models and explanation (see Part 3) | When the problem demands it and you can evaluate it honestly |

Practice setups are guardrails, not vaults: keep confidential or personal data out of shared notebooks and public tools.

## Glossary

- **Mean**: the sum divided by the count.
- **Median**: the middle value after sorting.
- **Standard deviation**: a typical distance of values from their mean.
- **Standard error**: the typical size of the error in an estimate from a sample.
- **Confidence interval**: a range of values consistent with the data, at a stated level such as 95%.
- **Correlation**: a number from -1 to +1 for the strength of a straight-line link.
- **Confounder**: a factor that influences both the supposed cause and the outcome.
- **Simpson's paradox**: a comparison that reverses when you split by a hidden group.
- **Null hypothesis**: the "nothing is going on" assumption a test is built around.
- **p-value**: the chance of a result at least this extreme if the null hypothesis were true.
- **Effect size**: how large a difference is, on a scale that does not depend on sample size.
- **Power**: the chance a test detects an effect of a given size if it is real.
- **Permutation test**: a test that shuffles group labels to see what chance produces.
- **Bootstrap**: resampling with replacement to estimate uncertainty.
- **Multiple comparisons**: the inflation of false positives when many tests are run.
- **Bonferroni correction**: dividing the significance threshold by the number of tests.
- **Sample ratio mismatch**: an assignment split that deviates from plan by more than chance.
- **Baseline**: a trivial predictor that any model must beat.
- **Overfitting**: learning noise, shown by good training and poor test scores.
- **Leakage**: a feature that contains the answer or information from the future.
- **Regularisation**: a penalty that keeps a model simple.
- **Precision and recall**: of those flagged, the share truly positive; of all positives, the share caught.
- **Threshold**: the probability above which you act on a prediction.
- **K-means**: a method that groups points around k moving centres.
- **Silhouette score**: a measure from -1 to 1 of how well points fit their own cluster.
- **Backtest**: testing a forecast on a held-out recent stretch.
- **Seasonal naive**: forecast equal to the same period one cycle earlier.
- **Pre-registration**: writing the analysis plan before seeing results.
- **Forking paths**: the many analysis choices that multiply the comparisons you could have made.

## Career notes

**Titles this leads to.** Data scientist, applied scientist, research scientist (usually with advanced study), quantitative analyst, decision scientist, experimentation or product analyst, and machine learning engineer with more engineering (Part 3). Titles vary a great deal between organisations, so read the duties, not the title.

**How to show your skill.** Publish the three capstones, written for a non-specialist: a plan made before the analysis, an interval and an effect size, a baseline beside every model, and a clear statement of what you do not claim. A write-up of an idea you tested and rejected impresses more than one more good score. Domain experience is an asset: choose problems from a field you know, since good questions come from context.

**What to learn next.** Deeper statistics (regression diagnostics, Bayesian methods, causal inference, time-series models), machine learning practice (Part 3), data pipelines (Part 4), experimentation platforms, and communication and teaching.

**Certifications.** Some vendors and universities offer data science certificates, and they can help structure study. Check the current exam objectives before paying, as they change, and treat them as a supplement to a portfolio rather than a substitute.

## Match it in the app

This section is for readers who have the companion dashboard running. Nothing above depends on it. Use the Practice workspace, which holds a made-up year of operations data (3,650 records, 10 entities, 365 days, with a weekday pattern and roughly 7 percent problem records), and which you can break freely. The notebooks live in `python_practice/notebooks/` and can read the dashboard's data or the bundled sample file. Each has "Your turn" cells that check your answer.

**Level 1.** Work through `02_pandas_explore` for summaries and plots, and the first part of `11_hypothesis_testing`, which compares weekend and weekday revenue per day. Read its output as you would a coin-flip example: the observed gap, the t statistic, the p-value. The notebook warns that a p-value is not the size of an effect.

**Level 2.** Finish `11_hypothesis_testing`. It shows Welch's t-test with Cohen's d, then the pseudo-replication trap (running the same test on 3,650 records instead of 365 days, which gives an absurdly small p-value), and has two "Your turn" cells: a permutation test (5,000 shuffles of daily values) and a bootstrap interval. Compare your permutation p-value with the t-test's. The app has no A/B experiment tool, so build your own small simulation as in Level 2.

**Level 3.** Open `13_ml_regression` for the sequence baseline, time split, pipeline, leakage check and permutation importance: the split uses the first 80 percent of days to train; the baseline is the training average; adding `profit` as a feature makes R² near perfect, which is leakage. Try your own model in the "Your turn" cell. Then open `05_forecast`: it hides the last 14 days, scores a naive and a training-mean forecast by MAPE, and asks you to build a seasonal forecast that predicts each test day from the same weekday over the last four weeks. Compare with the naive error. The notebook cautions that the sample data was generated with a weekday pattern, so seasonal methods look unusually good. In `12_clustering_entities`, build the per-entity feature table, scale it, pick k by silhouette, and name the segments; remember that 10 entities is a very small sample.

In the browser, the ML Lab at `/ml` lets you pick a task (for example "Predict revenue"), a model and features, then press "Train and evaluate". Read the "Split by time" card and the scores beside the baseline, and watch the high-R² warning when you add a leaky feature such as operational cost. It is a quick way to feel the baseline and leakage ideas before the notebooks.

**Level 4.** The app offers no tools for pre-registration, review or fairness checks, so you do these by hand. Re-read your notebook memos as a reviewer would, using the standing list. As an exercise, compute precision and recall by category from an ML Lab classification run and discuss whether you would deploy it.

**What the app does not cover.** No randomised experiment tooling, power calculator or sample-ratio check. No regression diagnostics or causal methods. The ML Lab uses one time split and a fixed list of features, with no hyperparameter search. The forecast notebook is a single 14-day backtest, not a rolling one. Clustering covers only 10 entities. Reproducibility practice, version control, ethics and communication are skills the app cannot give you. Its insights and flags are rule-based leads, not verdicts.
