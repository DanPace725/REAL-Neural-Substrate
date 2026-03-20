# REAL Neural Substrate — Plain English Overview

_What this project is, what we found, and why it matters_

---

## What Problem Are We Trying to Solve?

Most AI systems today — like the ones that recognize faces in photos or translate languages — learn by looking at millions of examples and slowly adjusting billions of tiny settings inside themselves until they get good at a task. Think of it like a student who reads every textbook ever written before taking a single test.

This works, but it has a big catch: it takes an enormous amount of data, a huge amount of computing power, and a lot of time. And when the task changes even a little, you often have to start the whole learning process over from scratch.

**REAL asks a different question:** What if, instead of one giant system that reads everything at once, you had a team of tiny, independent agents — each one responsible for just its little corner of the problem — and they learned by doing, the same way people do?

---

## The Big Idea: Learning by Surviving

Imagine a team of workers passing boxes along an assembly line. Each worker only knows about the boxes coming to them and the workers right next to them. They don't see the whole factory. They don't get instructions from a boss watching everything at once.

But here's the twist: each worker has a limited energy supply. If they do their job well and the box gets to the end of the line correctly, energy flows back to them as a reward. If they waste energy sending boxes the wrong way, they start to run out and slow down.

Over time, each worker learns — through pure trial and error with their own tiny energy budget — which moves are worth making. They don't share a brain. They don't have a teacher. They just survive or they don't.

That's basically what REAL does. The "boxes" are small packets of information. The "workers" are simple computer agents called nodes. The "assembly line" is a network connecting them. And "energy" is a resource called ATP (borrowed from how real cells in your body store and spend energy).

When the system gets something right, a little energy ripples back through the path that worked. The nodes along that path get a bit stronger. Over time, the network gets better at routing things correctly — not because anyone told it to, but because the paths that work survive, and the paths that don't slowly fade away.

---

## What Does It Remember?

Here's one of the most interesting parts of the project. Each node keeps a kind of memory called a **substrate** — think of it like a worn groove in a path. The more a node uses a particular route and gets rewarded for it, the cheaper and easier that route becomes to use again in the future.

This memory persists between sessions. So if you train the network on one task and then ask it to do a related task, it doesn't start from zero. The worn grooves from the first task give it a head start on the second. This is called **carryover**, and testing whether it really works — and how well — has been a major focus of the experiments.

---

## What Did We Actually Test?

The project has been tested in two main ways.

### 1. Routing puzzles with context clues

The first set of tests used artificial puzzles where the network had to learn that the right answer depends on a hidden clue (called a "context"). Think of it like this: if the light is red, turn left. If the light is green, turn right. But the network has to figure out the rule by itself, just from seeing what works and what doesn't.

The tests showed:
- The network learns these context-dependent rules from a surprisingly small number of examples — often just 18 tries.
- When the rules change slightly (a new task), the network's memory from the old task gives it a real advantage. It's not starting over.
- When the network has to infer the hidden clue on its own — without being told which light is on — it actually transfers better to new tasks. That sounds strange, but it makes sense: if you never got attached to "this is the red-light rule," you don't get confused when the rules change.

### 2. Predicting whether a room is occupied

The second test used real sensor data from a building — CO₂ levels, temperature, humidity, light, and motion — to predict whether a room had people in it. This is a real-world problem that companies actually care about (for things like smart building systems and energy efficiency).

This was a tougher, messier test because the data wasn't designed for this system — it was just real sensor readings from a real building.

The results:
- An early version of the test was broken in ways that made the system look terrible. Once those problems were fixed, it performed dramatically better.
- After all the fixes were in place, the REAL system reached **95.2% F1 score** (a standard measure of accuracy that accounts for both false positives and missed detections).
- For comparison, a conventional AI trained the normal way — using all the available data and standard learning techniques — scored **96.3%**.
- **REAL came within 1.1 percentage points of the conventional AI, without using global learning or a fixed training dataset.** It learned while doing, one session at a time.

---

## What Do These Results Actually Mean?

### The gap with conventional AI is almost gone

A year ago, nobody would have expected a system built this way — with no global brain, no giant training run, no backpropagation — to come within a whisker of a well-trained classifier on a real dataset. The fact that it does is genuinely surprising and encouraging.

### It learns more efficiently

On the routing puzzles, the REAL system reached good performance after just 18 examples. The best conventional neural network doing the same task needed roughly 8 to 9 times more examples to reach the same level. This matters a lot in situations where you can't collect huge amounts of data.

### Memory actually transfers

One of the core claims of the project was that the "worn grooves" in the network's memory would carry over usefully to new situations. The experiments confirmed this. When you take the memory built up during one set of sessions and load it into a fresh system facing a new session, the new system performs better than one starting from nothing. The knowledge really does carry.

### The system regulates itself

When the network was given room to grow new connections (a feature called **morphogenesis**, which is a fancy word for "growing new structure"), it turned out to only grow in places where it was actually struggling. Where it was already doing well, it didn't bother. That kind of self-regulation is hard to program deliberately — here it emerged naturally from the energy rules.

---

## What Are the Implications?

### AI that learns on the fly

Most AI today is trained once, frozen, and then deployed. REAL points toward systems that keep learning as they run, adapting to new situations without needing to stop and be retrained. This is much closer to how animals learn.

### AI that works with less data

In many real-world situations — medical monitoring, industrial sensors, rare events — you simply can't collect millions of training examples. A system that can learn meaningfully from dozens or hundreds of examples instead of millions could open up applications that current AI can't touch.

### AI that doesn't forget

One persistent problem with conventional AI is that when you teach it something new, it sometimes forgets what it knew before ("catastrophic forgetting"). The REAL tests showed that multi-step learning chains — learning task A, then B, then C — didn't erase earlier knowledge. The network added to what it knew rather than overwriting it.

### A different philosophy about what intelligence is

Most AI is built top-down: you design a loss function, gather data, and optimize. REAL is built bottom-up: you set up the rules of survival, release the agents, and see what emerges. The results so far suggest that useful, transferable intelligence can in fact emerge from purely local, self-interested behavior — no global teacher required. That's a meaningful proof of concept, even at this early stage.

---

## Where Does It Stand Now?

This is still a research prototype, not a finished product. There are known gaps to close — particularly around making the system more sensitive to minority cases (like occupied rooms that are hard to detect), and testing how well the memory carries across longer chains of sessions. But the trajectory over the past few weeks has been striking: from a broken first test, to matching a conventional AI on a real-world dataset, in a single focused sprint of experimentation.

The project is at the stage where the core ideas have been validated in a real test environment. The next step is turning those validated ideas into something more robust and broadly usable.

---

_Written for a general audience. Technical details and source documents are in `SYNTHESIS.md` and the `docs/` folder._
