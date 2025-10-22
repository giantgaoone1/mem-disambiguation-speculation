# Memory Disambiguation Speculation Architecture

A comprehensive implementation and analysis of memory disambiguation speculation, synchronization mechanisms, and memory-level parallelism (MLP) for a 3-stage out-of-order (3O) pipeline.

## Overview

This project implements the core components required for speculative memory disambiguation in modern out-of-order processors. The design balances performance, complexity, and power efficiency while maintaining correctness in the presence of memory dependencies.

## Architecture Components

### 1. Load-Store Queue (LSQ) - `lsq.py`

The LSQ is the central structure for tracking in-flight memory operations.

**Features:**
- Tracks all loads and stores with their addresses, data, and metadata
- Enables memory disambiguation by detecting address conflicts
- Provides store-to-load forwarding when data is ready
- Supports speculation tracking and recovery
- Enforces memory ordering constraints

**Key Operations:**
- `allocate()` - Reserve LSQ entry for memory operation
- `check_dependency()` - Detect conflicts and forwarding opportunities
- `squash_from()` - Recovery from speculation violations

### 2. Memory Disambiguation Predictor - `predictor.py`

Implements two prediction strategies:

#### Store Set Predictor (Primary)
Based on "Memory Dependence Prediction using Store Sets" by Chrysos & Emer.

**Components:**
- **SSIT (Store Set ID Table)**: Maps PCs to store sets
- **LFST (Last Fetched Store Table)**: Tracks pending stores per set
- **Confidence Counters**: 2-bit saturating counters for prediction confidence

**Operation:**
1. On load: Check if PC belongs to a store set
2. If yes and low confidence: Wait for pending stores in set
3. If no or high confidence: Speculate freely
4. On violation: Create/merge store sets, reduce confidence

#### Simple Predictor (Alternative)
- Per-PC 2-bit saturating counter
- Simpler but less accurate than Store Set

### 3. 3-Stage Pipeline - `pipeline.py`

Implements a simplified out-of-order pipeline with three stages:

#### Issue Stage
- Instruction dispatch and decode
- ROB and LSQ allocation
- Dependency checking
- Speculation prediction

#### Execute Stage
- Address calculation
- Memory disambiguation checks
- Speculative load execution
- Store-to-load forwarding
- Cache/MSHR access

#### Commit Stage
- In-order instruction retirement
- Speculation validation
- Store buffer drain
- Recovery on violation

**Key Structures:**
- Reorder Buffer (ROB) for precise exceptions
- Register file (simplified)
- Memory (simplified byte-addressable)

### 4. Synchronization Mechanisms - `synchronization.py`

Implements memory ordering primitives:

#### Memory Fences
- **LFENCE**: Load fence - serializes loads
- **SFENCE**: Store fence - serializes stores
- **MFENCE**: Memory fence - serializes all memory operations

#### Atomic Operations
- **CAS**: Compare-And-Swap
- **SWAP**: Atomic exchange
- **FADD**: Fetch-And-Add
- Lock acquisition and release semantics

#### Store Buffer
- Holds committed stores before memory write
- Enables store-to-load forwarding
- Supports store coalescing
- Participates in coherence protocol

#### LL/SC (Load-Link/Store-Conditional)
- Lock-free synchronization primitive
- Reservation tracking
- Automatic invalidation on conflicts

### 5. Memory-Level Parallelism (MLP) - `mlp.py`

Maximizes concurrent memory operations:

#### MSHR (Miss Status Handling Registers)
- Tracks outstanding cache misses
- Enables multiple concurrent misses (miss-under-miss)
- Merges requests to same cache line
- Supports both demand and prefetch requests

**Features:**
- Hit-under-miss support
- Request merging for bandwidth efficiency
- Separate tracking of loads and stores

#### Bank Conflict Detection
- Models banked cache organization
- Detects conflicts when multiple requests hit same bank
- Tracks bank busy cycles
- Reports conflict statistics

#### Prefetch Queue
- Separate queue for prefetch requests
- Prevents prefetch interference with demand requests
- Tracks prefetch accuracy and timeliness
- Supports confidence-based prefetching

#### MLP Tracker
- Monitors memory-level parallelism
- Reports average and peak MLP
- Calculates MLP utilization
- Identifies parallelism opportunities

## Example Scenarios - `examples.py`

The examples demonstrate:

1. **Independent Operations**: Speculative execution of non-conflicting loads
2. **Store-to-Load Forwarding**: Data forwarding from store to dependent load
3. **Speculation Violation**: Detection and recovery from incorrect speculation
4. **Memory Fences**: Ordering enforcement with synchronization primitives
5. **Memory-Level Parallelism**: Concurrent cache miss handling
6. **Atomic Operations**: CAS and fetch-and-add semantics
7. **Store Buffer**: Buffering and forwarding behavior

## Design Documentation - `architecture.md`

Comprehensive documentation covering:
- Pipeline stage details
- Memory disambiguation strategy
- Synchronization mechanisms
- MLP optimization techniques
- Design trade-offs
- Performance considerations
- Verification methodology

## Usage

### Running Individual Components

Test each component independently:

```bash
# Test Load-Store Queue
python3 lsq.py

# Test Memory Disambiguation Predictor
python3 predictor.py

# Test Synchronization Primitives
python3 synchronization.py

# Test MLP Components
python3 mlp.py

# Test 3-Stage Pipeline
python3 pipeline.py
```

### Running Example Scenarios

Execute all demonstration scenarios:

```bash
python3 examples.py
```

This will run through all seven scenarios showing different aspects of memory disambiguation and speculation.

## Key Design Decisions

### 1. Speculation Aggressiveness
- Default: Optimistic speculation with Store Set predictor
- Learns from violations to reduce future misspeculations
- Confidence-based throttling to balance performance and recovery cost

### 2. LSQ Organization
- Unified queue for loads and stores (simpler implementation)
- Alternative: Split load and store queues (more parallelism)
- Trade-off: Complexity vs. flexibility

### 3. Recovery Mechanism
- Full pipeline flush from violating instruction
- Alternative: Selective replay (more complex but faster)
- Trade-off: Simplicity vs. performance

### 4. MLP Support
- MSHRs enable multiple concurrent misses
- Bank-level parallelism reduces conflicts
- Prefetching separated to avoid interference

### 5. Synchronization
- Explicit fence instructions for ordering
- Atomic operations for lock-free algorithms
- Store buffer for performance and ordering

## Performance Considerations

### Factors Affecting Performance

1. **LSQ Size**: Larger LSQ → More in-flight memory ops → Higher MLP
2. **MSHR Count**: More MSHRs → More concurrent misses → Better MLP
3. **Predictor Accuracy**: Higher accuracy → Fewer violations → Better performance
4. **Bank Count**: More banks → Less conflict → Higher throughput

### Trade-offs

- **Area**: Larger structures (LSQ, MSHRs) increase die area
- **Power**: Speculation on wrong paths wastes energy
- **Complexity**: More aggressive policies increase design complexity
- **Latency**: Prediction lookup may be on critical path

## Future Enhancements

Potential extensions to the design:

1. **Advanced Predictors**
   - Neural network-based prediction
   - Context-sensitive store sets
   - Load-value prediction

2. **Optimizations**
   - Partial store-to-load forwarding
   - Load-load ordering relaxation
   - Victim cache for speculative data

3. **Multi-core Support**
   - Cache coherence integration
   - Cross-core speculation
   - Directory-based tracking

4. **Power Management**
   - Adaptive speculation based on energy budget
   - Selective LSQ entry allocation
   - Dynamic MSHR sizing

## References

1. Chrysos, G., and Emer, J. "Memory Dependence Prediction using Store Sets"
2. Moshovos, A., et al. "Dynamic Speculation and Synchronization of Data Dependences"
3. Yoaz, A., et al. "Speculation Techniques for Improving Load Related Instruction Scheduling"
4. Karkhanis, T., and Smith, J. "A Day in the Life of a Data Cache Miss"

## Implementation Notes

- Written in Python for clarity and educational purposes
- Real hardware implementations would use RTL (Verilog/VHDL)
- Simplified memory model (no cache hierarchy details)
- Focus on core algorithms and data structures

## License

This is an educational implementation for understanding memory disambiguation and speculation in out-of-order processors.
