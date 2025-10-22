# Quick Start Guide

## Memory Disambiguation Speculation Architecture

This guide will help you quickly understand and use the memory disambiguation speculation architecture implementation.

## Installation

No installation required! This is a pure Python implementation with no external dependencies.

**Requirements:**
- Python 3.7 or higher
- Standard library only (no pip packages needed)

## Quick Test

Run the integration test to verify everything works:

```bash
python3 test_integration.py
```

Expected output:
```
🎉 ALL TESTS PASSED! 🎉
The memory disambiguation speculation architecture is working correctly.
```

## Running Examples

### 1. View All Example Scenarios

```bash
python3 examples.py
```

This demonstrates:
- Independent load/store operations
- Store-to-load forwarding
- Speculation violations and recovery
- Memory fences
- Memory-level parallelism
- Atomic operations
- Store buffer behavior

### 2. Test Individual Components

**Load-Store Queue:**
```bash
python3 lsq.py
```

**Memory Disambiguation Predictor:**
```bash
python3 predictor.py
```

**Synchronization Primitives:**
```bash
python3 synchronization.py
```

**Memory-Level Parallelism:**
```bash
python3 mlp.py
```

**3-Stage Pipeline:**
```bash
python3 pipeline.py
```

## Using the Components

### Example: Creating a Load-Store Queue

```python
from lsq import LoadStoreQueue, MemOpType

# Create LSQ with 16 entries
lsq = LoadStoreQueue(capacity=16)

# Allocate a store
st_idx = lsq.allocate(seq_num=1, pc=0x1000, op_type=MemOpType.STORE, size=4)
lsq.update_address(st_idx, 0x2000)
lsq.update_data(st_idx, 0xDEADBEEF)

# Allocate a load
ld_idx = lsq.allocate(seq_num=2, pc=0x1004, op_type=MemOpType.LOAD, size=4)
lsq.update_address(ld_idx, 0x2000)

# Check for dependencies and forwarding
has_dep, fwd_idx, fwd_data = lsq.check_dependency(ld_idx)
if fwd_data is not None:
    print(f"Forwarding: 0x{fwd_data:X}")
```

### Example: Using the Store Set Predictor

```python
from predictor import StoreSetPredictor

# Create predictor
predictor = StoreSetPredictor()

# Predict if a load can speculate
load_pc = 0x1000
can_speculate, wait_seq = predictor.predict_load(load_pc)

if can_speculate:
    print("Execute load speculatively")
else:
    print(f"Wait for store sequence {wait_seq}")

# Report violation if speculation was wrong
store_pc = 0x1008
predictor.report_violation(load_pc, store_pc)

# Future predictions will be more conservative
can_speculate, wait_seq = predictor.predict_load(load_pc)
```

### Example: Simulating the Pipeline

```python
from pipeline import Pipeline, Instruction, InstructionType

# Create pipeline
pipeline = Pipeline(rob_size=32, lsq_size=16)

# Create instructions
instructions = [
    Instruction(pc=0x1000, instr_type=InstructionType.STORE, 
                src_regs=[1, 2], immediate=0),
    Instruction(pc=0x1004, instr_type=InstructionType.LOAD,
                dst_reg=3, src_regs=[1], immediate=0),
]

# Set up state
pipeline.registers[1] = 0x2000  # Base address
pipeline.registers[2] = 0xBEEF  # Data to store

# Run simulation
for cycle in range(20):
    pipeline.cycle_step(instructions)
    if not instructions:
        break

# View results
stats = pipeline.get_stats()
print(f"IPC: {stats['ipc']:.2f}")
print(f"Violations: {stats['speculation_violations']}")
```

### Example: Using Synchronization Primitives

```python
from synchronization import MemoryFence, FenceType, AtomicOperation

# Memory fence
fence = MemoryFence(FenceType.MFENCE, seq_num=10)
if fence.blocks_load(15):
    print("Load must wait for fence")

# Atomic compare-and-swap
cas = AtomicOperation("CAS", address=0x1000, seq_num=20)
success, old_val = cas.execute(
    memory_value=42,
    write_value=100,
    expected=42
)
print(f"CAS: success={success}, old_value={old_val}")
```

### Example: Memory-Level Parallelism

```python
from mlp import MSHRFile, MLPTracker

# Create MSHR file
mshr = MSHRFile(num_entries=8, line_size=64)

# Track multiple concurrent misses
idx1 = mshr.allocate(address=0x1000, seq_num=1, cycle=10)
idx2 = mshr.allocate(address=0x2000, seq_num=2, cycle=11)
idx3 = mshr.allocate(address=0x3000, seq_num=3, cycle=12)

print(f"Active MSHRs: {mshr.get_active_count()}")

# Track MLP
mlp = MLPTracker()
for cycle in range(20):
    outstanding = mshr.get_active_count()
    mlp.record_cycle(outstanding)

print(f"Average MLP: {mlp.get_average_mlp():.2f}")
```

## Understanding the Output

### LSQ Output
```
LSQ(capacity=8, size=2, loads=1, stores=1)
```
- capacity: Total entries
- size: Currently used entries
- loads/stores: Count by type

### Predictor Output
```
StoreSetPredictor(predictions=10, violations=2, accuracy=80.0%)
```
- predictions: Total predictions made
- violations: Incorrect speculations
- accuracy: Percentage correct

### Pipeline Output
```
Pipeline(cycle=100, IPC=0.85, violations=3)
```
- cycle: Current cycle number
- IPC: Instructions per cycle
- violations: Speculation violations

## Performance Tuning

### Increasing Memory-Level Parallelism

```python
# Larger MSHR file
mshr = MSHRFile(num_entries=16)  # More concurrent misses

# More cache banks
banks = BankConflictDetector(num_banks=8)  # Less conflicts
```

### Reducing Speculation Violations

```python
# More aggressive predictor
predictor = StoreSetPredictor(
    ssit_size=512,      # Larger table
    max_store_sets=128  # More store sets
)
```

### Optimizing LSQ Size

```python
# Larger LSQ for more in-flight operations
lsq = LoadStoreQueue(capacity=32)

# Larger ROB for more speculation
pipeline = Pipeline(rob_size=64, lsq_size=32)
```

## Debugging Tips

### Enable Detailed Output

Each module has a `__main__` section that runs basic tests:

```bash
python3 lsq.py          # Shows LSQ operations
python3 predictor.py    # Shows prediction behavior
python3 pipeline.py     # Shows pipeline execution
```

### Check Statistics

All components provide `get_stats()` methods:

```python
lsq_stats = lsq.get_stats() if hasattr(lsq, 'get_stats') else {}
predictor_stats = predictor.get_stats()
pipeline_stats = pipeline.get_stats()
```

### Trace Execution

Add print statements to track execution:

```python
# In your code
print(f"Cycle {cycle}: {instruction}")
print(f"LSQ state: {lsq}")
print(f"Predictor: {predictor}")
```

## Common Patterns

### Pattern 1: Store-to-Load Forwarding

```python
# Store followed by dependent load
lsq.allocate(seq_num=1, pc=0x100, op_type=MemOpType.STORE, size=4)
lsq.update_address(0, 0x1000)
lsq.update_data(0, 0xABCD)

lsq.allocate(seq_num=2, pc=0x104, op_type=MemOpType.LOAD, size=4)
lsq.update_address(1, 0x1000)

has_dep, fwd_idx, fwd_data = lsq.check_dependency(1)
# fwd_data should be 0xABCD
```

### Pattern 2: Speculation Learning

```python
# First time: speculate
can_spec, _ = predictor.predict_load(0x1000)  # True

# Violation occurs
predictor.report_violation(load_pc=0x1000, store_pc=0x1008)

# Second time: more conservative
can_spec, _ = predictor.predict_load(0x1000)  # False or wait
```

### Pattern 3: Memory Ordering with Fences

```python
# Store-fence-load sequence
fence = MemoryFence(FenceType.MFENCE, seq_num=2)

# Load after fence must wait
if fence.blocks_load(seq_num=3):
    # Wait for fence to complete
    pass
```

## Further Reading

- **architecture.md**: Detailed architecture design
- **diagrams.md**: Visual representations
- **SUMMARY.md**: Project overview and achievements
- **examples.py**: Comprehensive scenarios

## Support

This is an educational implementation. For questions or issues:
1. Review the documentation files
2. Check the example scenarios
3. Examine the test output
4. Review the source code comments

## Next Steps

1. Read `architecture.md` for design details
2. Study `examples.py` for usage patterns
3. Experiment with different configurations
4. Modify and extend the implementation

Happy exploring! 🚀
