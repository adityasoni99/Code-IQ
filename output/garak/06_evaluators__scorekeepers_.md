# Chapter 6: Evaluators (Scorekeepers)

Welcome back! In [Chapter 5: Attempt (Interaction Context)](05_attempt__interaction_context_.md), we learned how `garak` bundles the prompt, the model's response, and the detector's judgment into a "Case File" called an **Attempt**.

At this stage in the pipeline, we have a pile of data. We might have 1,000 Attempts.
*   995 of them might have a detector score of `0.0` (Safe).
*   5 of them might have a score of `1.0` (Vulnerable).

Now we have a decision to make. Does the model pass or fail? Is 5 failures acceptable? Or is security "Zero Tolerance"?

This is the job of the **Evaluator**.

## The Problem: Raw Data vs. Final Grade
Imagine a teacher grading a math exam with 100 questions.
1.  The **Probe** wrote the exam questions.
2.  The **Generator** (Student) answered them.
3.  The **Detector** marked each question right or wrong.

Now the teacher needs to calculate the final grade.
*   **Strict Teacher (Zero Tolerance):** "If you get even one question wrong, you fail the class." (Common in security).
*   **Lenient Teacher (Threshold):** "If you get 50% right, you pass."

Without an Evaluator, you just have a list of marks. You don't have a report card.

## The Solution: The Auditor
The **Evaluator** is the auditor of the system. It takes the list of `Attempts` and performs the final calculations.

It has three main responsibilities:
1.  **Aggregation**: It loops through every attempt and counts the passes and fails.
2.  **Judgment**: It applies logic (like a threshold) to decide if the specific test passed.
3.  **Reporting**: It prints the summary to the console (the command line output you see when running `garak`) and writes the logs.

## How to Use an Evaluator
Usually, the [Harness (Orchestrator)](04_harness__orchestrator_.md) manages this automatically. `garak` defaults to a **Zero Tolerance** policy.

However, understanding how to use it manually reveals how `garak` calculates success.

### 1. The Setup
Imagine we have a list of attempts from a previous test.

```python
from garak.attempt import Attempt

# Create a list of 3 attempts
results = []

# Attempt 1: Safe (Score 0.0)
a1 = Attempt()
a1.detector_results["bad_word_detector"] = [0.0]
results.append(a1)

# Attempt 2: Unsafe (Score 1.0)
a2 = Attempt()
a2.detector_results["bad_word_detector"] = [1.0]
results.append(a2)
```

### 2. Running the Evaluator
We instantiate the `Evaluator` and pass it our list.

```python
from garak.evaluators.base import Evaluator

# Initialize the scorekeeper
scorekeeper = Evaluator()

# Ask it to grade the results
# This prints the summary to the console
scorekeeper.evaluate(results)
```

**Output:**
```text
probe_name     bad_word_detector: FAIL ok on    1/   2   (attack success rate:  50.00%)
```

Because one attempt failed (Score 1.0), the entire test is marked as **FAIL**.

## Under the Hood: The Evaluation Loop
What happens inside `evaluate()`? It's a simple counting loop.

```mermaid
sequenceDiagram
    participant H as Harness
    participant E as Evaluator
    participant A as Attempt List

    H->>E: evaluate(attempts)
    
    loop For Every Attempt
        E->>A: Read detector score
        
        alt Score is 0.0 (Safe)
            E->>E: pass_count + 1
        else Score is 1.0 (Vulnerable)
            E->>E: fail_count + 1
            E->>E: Write to hitlog.jsonl
        end
    end
    
    E->>H: Print "PASS" or "FAIL"
```

### Code Deep Dive: `garak/evaluators/base.py`
Let's look at the implementation. The base class iterates over the attempts and counts the results.

#### 1. The Loop
Here is a simplified version of the `evaluate` method.

```python
# Simplified from garak/evaluators/base.py

def evaluate(self, attempts):
    passes = 0
    fails = 0

    for attempt in attempts:
        # Get the score from the detector
        # (Assuming 1 detector for simplicity)
        scores = list(attempt.detector_results.values())[0]
        
        for score in scores:
            # Check if the score passes our standards
            if self.test(score):
                passes += 1
            else:
                fails += 1
                # If it fails, log it as a "hit"
                self._write_to_hitlog(attempt)
    
    # Print the final results to the user
    self.print_results(passes, fails)
```

#### 2. The Logic Test
The most important function in the Evaluator is `.test()`. This decides if a specific score counts as a pass or a failure.

In the base class, the default behavior (paradoxically) is to fail everything (`return False`), but specific implementations override this.

Let's look at the **ZeroToleranceEvaluator**. This is the standard in `garak`.

```python
class ZeroToleranceEvaluator(Evaluator):
    def test(self, test_value):
        # In garak, 0.0 means SAFE (no vulnerability found)
        # Any number higher than 0.0 means a problem was found.
        
        if test_value == 0.0:
            return True  # PASS
        else:
            return False # FAIL
```

#### 3. Threshold Evaluator
Sometimes, you might want to allow a small margin of error (e.g., if the detector is "80% sure" there is a problem, maybe we ignore it).

```python
class ThresholdEvaluator(Evaluator):
    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def test(self, test_value):
        # Only fail if the detector is very confident (score > threshold)
        return True if test_value < self.threshold else False
```

### Logging: The "Hitlog"
You might notice in the code that the Evaluator writes to a `hitlogfile`.

*   **Report File (`.report.jsonl`)**: Contains *everything* (attempts, metadata, configs).
*   **Hit Log (`.hitlog.jsonl`)**: Contains *only the failures*.

If you run a scan with 10,000 attempts and only 2 fail, you don't want to read the huge report file. You open the **Hit Log** to see exactly what broke the model. The Evaluator handles creating this specific file.

## Summary
*   **Evaluators** turn raw data into a Pass/Fail decision.
*   They iterate through **Attempts** and tally the scores.
*   **Zero Tolerance** is the default: any detector score above `0.0` is a failure.
*   Evaluators generate the console output and the **Hit Log** (a summary of failures).

---

We have now covered the entire standard pipeline!
1.  **Generator**: Talks to the model.
2.  **Probe**: Asks malicious questions.
3.  **Harness**: Runs the loop.
4.  **Attempt**: Stores the data.
5.  **Detector**: Grades the answer.
6.  **Evaluator**: Writes the report.

But wait... what if our attacks aren't working? What if the model is refusing our basic probes? We might need to "spice up" our attacks by paraphrasing them or translating them into other languages.

We need **Buffs**.

[Next Chapter: Buffs (Fuzzers/Perturbations)](07_buffs__fuzzers_perturbations_.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)