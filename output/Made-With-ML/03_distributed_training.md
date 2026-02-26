# Chapter 3: Distributed Training

Welcome to Chapter 3! In the previous chapter, **[Model Architecture](02_model_architecture.md)**, we built our "Chef" (the neural network). We combined a pre-trained BERT model with a classifier.

However, right now, our Chef is an amateur. They have the *potential* to cook (the architecture), but they haven't practiced yet (the weights are random). We need to train them.

## The Motivation: The Gym Analogy

Training a model is like sending an athlete to the gym. 
*   **The Goal:** Get fit (minimize error).
*   **The Reps:** The model looks at a batch of data, makes a guess, realizes it's wrong, and adjusts itself.

If you have a massive dataset (millions of text files), training on a single computer is like **one person trying to do 100,000 pushups**. It will take weeks.

**Distributed Training** is the solution. Instead of one person, we hire a **team of athletes** (multiple CPUs or GPUs). We split the 100,000 pushups so that 10 people do 10,000 each simultaneously. They finish 10x faster.

This chapter explains how we use a library called **Ray** to coordinate this team.

---

## The Concept: Data Parallelism

We use a specific strategy called **Data Parallelism**.

1.  **Replicate the Model:** Every worker (CPU/GPU) gets an exact copy of the untrained model.
2.  **Split the Data:** We slice our dataset into "shards". If we have 4 workers, each gets 25% of the data.
3.  **Train Simultaneously:** Each worker calculates errors on its own chunk of data.
4.  **Sync:** The workers talk to each other to average their findings and update the model together.

## How to Use It (The Interface)

We don't want to manually manage cables connecting computers. We use **Ray Train**.

The main entry point is the `TorchTrainer`. Think of this as the "Coach" who manages the athletes. We tell the Coach how many workers we want and what training function they should run.

### Defining the Resources (Scaling Config)

First, we define how big our team is using `ScalingConfig`.

```python
from ray.train import ScalingConfig

# Define our gym capacity
scaling_config = ScalingConfig(
    num_workers=2,              # Number of "Athletes"
    use_gpu=False,              # Are we using GPUs?
    resources_per_worker={      # Hardware per athlete
        "CPU": 1, 
        "GPU": 0
    }
)
```
*Explanation: Here we are asking for 2 workers, each using 1 CPU. Ray will automatically find these resources on your machine (or cluster).*

### The Manager (TorchTrainer)

Next, we initialize the Trainer. We pass in the datasets and the function that contains the training logic (`train_loop_per_worker`).

```python
from ray.train.torch import TorchTrainer

# Initialize the Coach
trainer = TorchTrainer(
    train_loop_per_worker=train_loop_per_worker,
    train_loop_config={"batch_size": 256, "num_epochs": 5},
    scaling_config=scaling_config,
    datasets={"train": train_ds, "val": val_ds},
)

# Start the workout!
results = trainer.fit()
```
*Explanation: When we call `trainer.fit()`, Ray spins up the 2 workers we requested, sends the data to them, and executes the training loop.*

---

## Under the Hood: The Training Loop

What exactly happens inside `train_loop_per_worker`? This is the set of instructions every athlete follows.

Let's look at the flow of a single training step (one batch of data).

```mermaid
sequenceDiagram
    participant Data as Dataset Shard
    participant Model as Model
    participant Loss as Loss Function
    participant Opt as Optimizer (Update)

    Data->>Model: Input: "Intro to CNNs"
    Model->>Model: Forward Pass (Predict)
    Model->>Loss: Output: "NLP" (Wrong!)
    Loss->>Loss: Calculate Error (Loss)
    Loss->>Opt: Backward Pass (Calculate Gradients)
    Opt->>Model: Update Weights (Learn)
```

### Implementation Details

We define this logic in `madewithml/train.py`. Let's break down the code into small, understandable pieces.

### 1. Setup and Data Sharding

When the worker starts, it needs to know which piece of the data belongs to it.

```python
# Inside train_loop_per_worker()
import ray.train as train

def train_loop_per_worker(config):
    # 1. Get the specific slice of data for this worker
    train_ds = train.get_dataset_shard("train")
    
    # 2. Define the Model (The Chef)
    model = FinetunedLLM(...) 
    
    # 3. Prepare model for distributed work
    model = train.torch.prepare_model(model)
```
*   `get_dataset_shard`: This is magic. If there are 4 workers, Ray ensures this function returns only 1/4th of the data unique to this specific worker.
*   `prepare_model`: This wraps our PyTorch model so it knows how to communicate with other workers to sync weights.

### 2. The Training Step

Now we loop through the data. This is the core mathematical "workout."

```python
# Inside a helper function: train_step()

    for i, batch in enumerate(ds_generator):
        optimizer.zero_grad()       # 1. Clear previous calculations
        
        z = model(batch)            # 2. Forward Pass (Make a guess)
        
        # 3. Calculate Error (Loss)
        # Compare guess (z) vs actual answer (targets)
        J = loss_fn(z, batch["targets"]) 
        
        J.backward()                # 4. Backward Pass (Calculate corrections)
        optimizer.step()            # 5. Update the model's brain
```
*   **Forward Pass:** The model looks at the text and predicts tags.
*   **Loss (`J`):** A mathematical score of how wrong the model was. High loss = bad guess.
*   **Backward Pass:** We calculate "gradients." This tells us which direction to push the numbers in the model to make the error smaller next time.
*   **Optimizer Step:** We actually change the numbers (weights).

### 3. Evaluation Step

After every "epoch" (going through the whole dataset once), we need to check if the model is actually learning or just memorizing. We test it on the **Validation Set**.

```python
# Inside a helper function: eval_step()

    model.eval()  # Switch to "Test Mode"
    with torch.inference_mode():
        for batch in ds_generator:
            z = model(batch)
            # Calculate loss but DO NOT update weights
            J = loss_fn(z, targets)
            # Save predictions to compare later
            y_preds.extend(torch.argmax(z, dim=1))
```
*   We use `model.eval()` and `torch.inference_mode()` to ensure we don't accidentally train on the test data. We just want to measure performance.

### 4. Saving Checkpoints

If our computer crashes after 3 hours of training, we don't want to start over. We save the model's state periodically.

```python
from ray.train import Checkpoint

    # Save the model to a temporary folder
    model.save(dp=dp)
    
    # Create a Checkpoint object
    checkpoint = Checkpoint.from_directory(dp)
    
    # Report progress to the Head Coach
    train.report({"loss": val_loss}, checkpoint=checkpoint)
```
*   `train.report`: This sends the current loss score and the saved checkpoint back to the central Ray process. It allows us to track graphs of how our model is improving over time.

---

## Putting it All Together

When we run the command to train our model, here is the sequence of events:

1.  **Data Processing:** Loads and processes text (from [Chapter 1](01_data_processing_pipeline.md)).
2.  **Initialization:** The `TorchTrainer` spawns workers based on our `ScalingConfig`.
3.  **Distribution:** Each worker loads the Model Architecture (from [Chapter 2](02_model_architecture.md)) and gets its shard of data.
4.  **Loop:**
    *   Workers train on their data.
    *   Workers sync updates.
    *   Workers evaluate on validation data.
    *   Workers report results.
5.  **Result:** We get a trained model file that knows how to classify our tags!

## Conclusion

We have successfully taken our "amateur" model and put it through a rigorous gym session using **Distributed Training**. By using Ray, we scaled this process across multiple workers, making it fast and efficient.

But wait—we picked some random numbers for our training configuration (like the "Learning Rate" or "Batch Size"). How do we know those were the *best* numbers to use? Maybe a different learning rate would make the model smarter?

To answer that, we need to run experiments to find the perfect settings.

👉 **Next Step:** [Hyperparameter Tuning](04_hyperparameter_tuning.md)

---

Generated by [Code IQ](https://github.com/adityasoni99/Code-IQ)