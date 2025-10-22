# Memory Disambiguation Speculation Architecture for 3-Stage OoO Pipeline

## Overview

This document describes the architecture design for memory disambiguation speculation, synchronization, and memory-level parallelism (MLP) in a 3-stage out-of-order (3O) pipeline.

## Pipeline Stages

The 3-stage out-of-order pipeline consists of:

1. **Issue Stage**: Instruction dispatch and resource allocation
2. **Execute Stage**: Functional unit execution and address calculation
3. **Commit Stage**: In-order retirement and state update

## Memory Disambiguation Speculation

### Problem Statement

In out-of-order processors, load instructions may execute before earlier store instructions whose addresses are unknown. Memory disambiguation determines whether a load conflicts with a pending store. Incorrect speculation can lead to:
- Performance penalties from recovery
- Complexity in maintaining memory ordering

### Solution Components

#### 1. Load-Store Queue (LSQ)

The LSQ tracks all in-flight memory operations and enables:
- Memory dependency checking
- Speculation validation
- Store-to-load forwarding
- Memory ordering enforcement

**Structure:**
```
LSQ Entry:
  - PC (Program Counter)
  - Address (when computed)
  - Data (for stores)
  - Size (byte/word/dword)
  - Valid bit
  - Speculative bit
  - Sequence number
```

#### 2. Memory Disambiguation Predictor

A predictor that learns memory dependency patterns to improve speculation accuracy.

**Components:**
- Store Set ID Table (SSIT): Maps PCs to store sets
- Last Fetched Store Table (LFST): Tracks the last store in each set
- Confidence counters: Track prediction accuracy

**Operation:**
1. On load issue: Check SSIT for store set membership
2. If member: Wait for stores in the same set
3. If not member or confident: Speculate and issue
4. On misspeculation: Update predictor tables

#### 3. Speculation Mechanism

**Speculative Load Execution:**
1. Load issued when address is ready
2. Check LSQ for address conflicts with pending stores
3. If no conflict (or predicted safe): Execute speculatively
4. Mark load as speculative in ROB
5. Continue execution of dependent instructions

**Validation:**
1. When earlier store address becomes known: Compare with speculative loads
2. If conflict detected: Trigger recovery
3. Update predictor on misspeculation

**Recovery:**
1. Flush pipeline from violating load onward
2. Re-fetch instructions starting from load PC
3. Update speculation predictor

## Synchronization Mechanisms

### Memory Ordering

The architecture enforces memory consistency through:

#### 1. Store Buffer
- Stores held in program order
- Forwarding to younger loads when addresses match
- Drain to memory/cache only at commit

#### 2. Memory Fences
- Explicit synchronization primitives
- Prevent reordering across fence boundaries
- Types: LFENCE (load fence), SFENCE (store fence), MFENCE (memory fence)

#### 3. Atomic Operations
- Read-Modify-Write sequences
- Lock elision for uncontended locks
- LL/SC (Load-Linked/Store-Conditional) support

### Coherence Protocol Integration

- Snoop requests check LSQ for pending operations
- Invalidations can trigger speculation recovery
- Store buffer participates in coherence protocol

## Memory-Level Parallelism (MLP)

### Design Goals

Maximize concurrent memory operations while maintaining correctness.

### Techniques

#### 1. Miss Status Handling Registers (MSHRs)

Track outstanding cache misses:
- Multiple concurrent misses to different cache lines
- Merge requests to the same line
- Out-of-order miss handling

**MSHR Structure:**
```
MSHR Entry:
  - Address tag
  - Valid bit
  - Request type (load/store/prefetch)
  - Waiting instruction IDs
  - Coherence state
```

#### 2. Non-Blocking Caches

- Loads can proceed during cache misses
- Hit-under-miss support
- Miss-under-miss support (multiple concurrent misses)

#### 3. Prefetching Integration

- Hardware prefetchers work with speculative loads
- Prefetch queue separate from demand requests
- Prefetch accuracy affects MLP benefits

#### 4. Bank-Level Parallelism

- Cache banks for parallel access
- LSQ entries can access different banks simultaneously
- Bank conflict detection and arbitration

## 3-Stage Pipeline Integration

### Issue Stage

1. Instruction decode and dependency check
2. LSQ entry allocation for memory ops
3. Speculation prediction lookup
4. Resource reservation

**Memory Operation Handling:**
- Allocate LSQ entry
- Check SSIT for store set
- Determine speculation policy
- Wait for dependencies or issue speculatively

### Execute Stage

1. Address calculation
2. LSQ search for conflicts
3. Cache access or MSHR allocation
4. Store-to-load forwarding

**Speculative Load Execution:**
```
1. Calculate effective address
2. Search store queue for conflicts
   - If match found and data ready: Forward
   - If match found and data not ready: Stall
   - If no match: Proceed speculatively
3. Access cache or allocate MSHR
4. Mark speculation state in ROB
```

### Commit Stage

1. In-order commit from ROB
2. Store buffer drain
3. Speculation validation
4. Exception handling

**Memory Commit:**
```
For Loads:
  - Verify no violations occurred
  - Release LSQ entry
  
For Stores:
  - Write to cache/memory
  - Update coherence state
  - Release LSQ entry
```

## Performance Optimizations

### 1. Store-to-Load Forwarding

- Fast path when addresses match exactly
- Partial forwarding for size mismatches
- Multiple forwarding sources

### 2. Aggressive Load Speculation

- Predict loads independent unless proven otherwise
- Confidence-based speculation
- Selective replay vs. full pipeline flush

### 3. Victim Cache for Evicted Speculative Data

- Hold recently evicted lines
- Reduce penalty of speculation misses
- Small fully-associative cache

### 4. Speculation Throttling

- Reduce speculation under high misspeculation rate
- Adaptive policies based on accuracy
- Energy-aware speculation

## Design Trade-offs

### Complexity vs. Performance

- **More aggressive speculation**: Higher IPC but more complex recovery
- **Larger LSQ**: More MLP but higher area/power
- **Sophisticated predictor**: Better accuracy but longer access time

### Power Considerations

- Speculation consumes energy on wrong paths
- LSQ search/CAM operations are power-intensive
- Trade-off speculation aggressiveness for power efficiency

### Area Constraints

- LSQ size limited by CAM area
- MSHR count affects cache size
- Predictor table sizing

## Example Scenarios

### Scenario 1: Independent Load After Store

```assembly
STORE R1 -> [R2]      ; ST1
LOAD [R4] -> R5       ; LD1 (different address)
```

**Operation:**
1. ST1 enters LSQ, address not ready
2. LD1 issued speculatively (predictor says safe)
3. LD1 accesses cache, gets data
4. ST1 address calculated later, no conflict
5. Both commit in order

### Scenario 2: Dependent Load After Store

```assembly
STORE R1 -> [R2]      ; ST1
LOAD [R2] -> R5       ; LD1 (same address)
```

**Operation:**
1. ST1 enters LSQ with address
2. LD1 issued, LSQ search finds ST1
3. Forward data from ST1 to LD1
4. LD1 continues with forwarded data
5. Both commit in order

### Scenario 3: Misspeculation

```assembly
STORE R1 -> [R2]      ; ST1 (address unknown)
LOAD [R4] -> R5       ; LD1 (speculative)
ADD R5, R6 -> R7      ; dependent on LD1
```

**If R2 == R4:**
1. LD1 issued speculatively
2. Dependent instructions execute
3. ST1 address calculated, conflict detected
4. Pipeline flush from LD1
5. Re-execute LD1 and dependents
6. Update predictor: LD1 depends on ST1

## Verification and Validation

### Test Cases

1. **Correctness Tests**
   - Load-store dependencies
   - Store-to-load forwarding
   - Memory ordering
   - Atomic operations

2. **Performance Tests**
   - MLP measurement
   - Speculation accuracy
   - Recovery latency
   - Throughput benchmarks

3. **Corner Cases**
   - Multiple stores to same address
   - Partial address overlaps
   - Cache line boundaries
   - Exception handling during speculation

## References

- Chrysos, G., and Emer, J. "Memory Dependence Prediction using Store Sets"
- Moshovos, A., et al. "Dynamic Speculation and Synchronization of Data Dependences"
- Yoaz, A., et al. "Speculation Techniques for Improving Load Related Instruction Scheduling"
