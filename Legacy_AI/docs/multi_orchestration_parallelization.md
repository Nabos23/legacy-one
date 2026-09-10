# Multi-Orchestration: Parallelization & Synchronization Architecture

The `RuntimeScheduler` in the multi-orchestration module handles complex agent graphs using a Breadth-First Search (BFS) approach. It natively supports execution fan-outs (parallel branching) and fan-ins (synchronization/join nodes). 

This document outlines the technical flow and data structures used to manage parallel states and thread joining.

---

## 1. Triggering a Fan-Out

The routing logic is driven by the `RoutingEngine.decide_next` method. After an agent finishes its turn, the router evaluates the agent's output against the graph definition to determine the next nodes. 

If the router returns multiple `next_ids` (i.e., `len(next_ids) > 1`), a **Fan-Out** is initiated:

1. **Context Snapshot (`fork_context`)**: Before spawning threads, the scheduler takes a snapshot of the current conversational memory via `memory_bus.get_context()`. This ensures every spawned branch begins with the exact same historical context, preventing race conditions where one branch accidentally reads a sibling branch's newly appended messages.
2. **ThreadPool Invocation**: The scheduler calls `_run_parallel_branches`, which spawns a `ThreadPoolExecutor` with a pool size bounded by `_MAX_PARALLEL_BRANCHES`. 
3. **Thread Dispatch**: Each target ID is dispatched into a new thread running `_run_single_branch`.

---

## 2. Parallel Branch Execution

Once a branch thread starts (`_run_single_branch`), it operates as an independent execution loop:

- **State Isolation**: The branch tracks its own `pending` queue. The first agent executed consumes the static `fork_context`. Subsequent agents invoked within that same branch read the live, updated log from the memory bus.
- **MongoDB State Tracking**: Branches are tracked in the database inside the `branches` array of the orchestration run document. To prevent data clobbering across parallel threads, updates are performed atomically using array filters (`_upsert_branch_state`).
- **Human-in-the-Loop (HITL)**: If a branch triggers HITL (e.g., an agent calls `ask_human` or fails to use a tool), the branch updates its specific `status` to `WAITING_FOR_HUMAN` and halts. The main scheduler recognizes this signal and bubbles the pause up to the user interface.

---

## 3. Converging at Join Nodes

The graph definition defines specific nodes as **Join Points** (`graph.join_points`). When multiple branches are required to converge into a single node, a synchronization barrier is enforced to ensure all dependencies are met before proceeding.

### Arrival & Synchronization
When a branch decides its next step is a Join Node, it executes `_record_join_arrival`:

1. **Atomic Arrival Logging**: The branch uses a MongoDB `$addToSet` operation to atomically add its ID to the `join_arrivals.<join_node_id>` list. Memory state is avoided here because each thread (or even a resumed orchestration run) operates in isolation.
2. **Dependency Checking**: The scheduler looks up `graph.reverse_adjacency` to determine exactly which agent IDs must arrive at this join node.
3. **Barrier Check**: It checks if the `required` set is a subset of the `arrived` set.
    - **If False**: The branch goes to sleep. It marks its status as parked and gracefully exits the loop, waiting for siblings.
    - **If True**: The current thread is the **last required arrival** and assumes responsibility for executing the Join Node.

### Post-Join Execution
The thread that successfully breaks the barrier takes over:

1. **Subsuming Siblings**: The executing thread iterates over the siblings that arrived previously and explicitly marks their branch statuses as `COMPLETE` via `_upsert_branch_state`, cleaning up the active thread list.
2. **Merging**: The branch adds the Join Node to its own pending queue and continues executing. The orchestration converges back into a single thread (or continues down a new graph path) seamlessly.
