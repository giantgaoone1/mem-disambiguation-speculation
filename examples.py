"""
Example Scenarios for Memory Disambiguation Speculation

Demonstrates the 3O pipeline with various memory patterns:
1. Independent loads and stores
2. Dependent load-store pairs with forwarding
3. Speculation violations and recovery
4. Memory fences and synchronization
5. Memory-level parallelism
"""

from lsq import LoadStoreQueue, MemOpType
from predictor import StoreSetPredictor, SimplePredictor
from synchronization import MemoryFence, FenceType, AtomicOperation, StoreBuffer
from mlp import MSHRFile, BankConflictDetector, PrefetchQueue, MLPTracker


def scenario_1_independent_ops():
    """
    Scenario 1: Independent Loads and Stores
    
    Demonstrates speculative execution of loads that don't conflict
    with earlier stores.
    """
    print("=" * 70)
    print("SCENARIO 1: Independent Loads and Stores")
    print("=" * 70)
    
    lsq = LoadStoreQueue(capacity=8)
    predictor = StoreSetPredictor()
    
    # Store to address 0x1000
    st_idx = lsq.allocate(seq_num=1, pc=0x100, op_type=MemOpType.STORE, size=4)
    lsq.update_address(st_idx, 0x1000)
    lsq.update_data(st_idx, 0xDEAD)
    print(f"ST1: Store 0xDEAD to [0x1000]")
    
    # Load from address 0x2000 (different, no conflict)
    ld_idx = lsq.allocate(seq_num=2, pc=0x104, op_type=MemOpType.LOAD, size=4)
    lsq.update_address(ld_idx, 0x2000)
    
    # Check if load can speculate
    can_spec, wait_seq = predictor.predict_load(0x104)
    print(f"LD1: Load from [0x2000] - Can speculate: {can_spec}")
    
    # Check LSQ for dependencies
    has_dep, fwd_idx, fwd_data = lsq.check_dependency(ld_idx)
    print(f"     LSQ check - Has dependency: {has_dep}")
    
    if not has_dep and can_spec:
        lsq.mark_speculative(ld_idx)
        lsq.mark_completed(ld_idx)
        print(f"     Executed speculatively!")
    
    # Validate at commit - should be correct
    has_dep, fwd_idx, fwd_data = lsq.check_dependency(ld_idx)
    if not has_dep:
        predictor.report_correct_speculation(0x104)
        print(f"     Validation: PASSED - No violation")
    
    print(f"\nFinal LSQ: {lsq}")
    print(f"Predictor: {predictor}\n")


def scenario_2_store_forwarding():
    """
    Scenario 2: Store-to-Load Forwarding
    
    Demonstrates forwarding data from a store to a dependent load.
    """
    print("=" * 70)
    print("SCENARIO 2: Store-to-Load Forwarding")
    print("=" * 70)
    
    lsq = LoadStoreQueue(capacity=8)
    
    # Store to address 0x1000
    st_idx = lsq.allocate(seq_num=1, pc=0x200, op_type=MemOpType.STORE, size=4)
    lsq.update_address(st_idx, 0x1000)
    lsq.update_data(st_idx, 0xBEEF)
    print(f"ST1: Store 0xBEEF to [0x1000]")
    
    # Load from same address 0x1000
    ld_idx = lsq.allocate(seq_num=2, pc=0x204, op_type=MemOpType.LOAD, size=4)
    lsq.update_address(ld_idx, 0x1000)
    print(f"LD1: Load from [0x1000]")
    
    # Check for forwarding opportunity
    has_dep, fwd_idx, fwd_data = lsq.check_dependency(ld_idx)
    
    if fwd_data is not None:
        print(f"     Forwarding from ST1: 0x{fwd_data:X}")
        print(f"     Load completed with forwarded data!")
    else:
        print(f"     Cannot forward (data not ready)")
    
    print(f"\nFinal LSQ: {lsq}\n")


def scenario_3_speculation_violation():
    """
    Scenario 3: Speculation Violation
    
    Demonstrates detection and recovery from incorrect speculation.
    """
    print("=" * 70)
    print("SCENARIO 3: Speculation Violation and Recovery")
    print("=" * 70)
    
    lsq = LoadStoreQueue(capacity=8)
    predictor = StoreSetPredictor()
    
    # Store to address unknown initially
    st_idx = lsq.allocate(seq_num=1, pc=0x300, op_type=MemOpType.STORE, size=4)
    print(f"ST1: Store to [???] (address not computed yet)")
    
    # Load from address 0x1000 - speculates it's independent
    ld_idx = lsq.allocate(seq_num=2, pc=0x304, op_type=MemOpType.LOAD, size=4)
    lsq.update_address(ld_idx, 0x1000)
    
    can_spec, wait_seq = predictor.predict_load(0x304)
    print(f"LD1: Load from [0x1000] - Can speculate: {can_spec}")
    
    if can_spec:
        lsq.mark_speculative(ld_idx)
        print(f"     Executed speculatively (assumed no conflict)")
    
    # Later: Store address computed to be 0x1000 (conflict!)
    lsq.update_address(st_idx, 0x1000)
    lsq.update_data(st_idx, 0xCAFE)
    print(f"\nST1: Address computed as [0x1000] - CONFLICT DETECTED!")
    
    # Validate load - should find violation
    has_dep, fwd_idx, fwd_data = lsq.check_dependency(ld_idx)
    
    if has_dep and fwd_data is not None:
        print(f"     Violation: Should have forwarded 0x{fwd_data:X}")
        print(f"     Recovery: Flush and re-execute from LD1")
        
        # Update predictor
        predictor.report_violation(load_pc=0x304, store_pc=0x300)
        print(f"     Predictor updated - will wait for ST1 in future")
    
    # Re-execute after recovery
    print(f"\nRe-execution:")
    predictor.register_store(0x300, seq_num=1)
    can_spec, wait_seq = predictor.predict_load(0x304)
    print(f"     LD1 prediction: Can speculate: {can_spec}, Wait for: {wait_seq}")
    
    print(f"\nFinal Predictor: {predictor}\n")


def scenario_4_memory_fences():
    """
    Scenario 4: Memory Fences
    
    Demonstrates memory ordering enforcement with fences.
    """
    print("=" * 70)
    print("SCENARIO 4: Memory Fences and Ordering")
    print("=" * 70)
    
    lsq = LoadStoreQueue(capacity=8)
    
    # Store before fence
    st1_idx = lsq.allocate(seq_num=1, pc=0x400, op_type=MemOpType.STORE, size=4)
    lsq.update_address(st1_idx, 0x1000)
    lsq.update_data(st1_idx, 0x1111)
    print(f"ST1: Store to [0x1000] (seq=1)")
    
    # Memory fence
    fence = MemoryFence(FenceType.MFENCE, seq_num=2)
    print(f"FENCE: MFENCE (seq=2)")
    
    # Load after fence
    ld1_idx = lsq.allocate(seq_num=3, pc=0x408, op_type=MemOpType.LOAD, size=4)
    lsq.update_address(ld1_idx, 0x2000)
    print(f"LD1: Load from [0x2000] (seq=3)")
    
    # Check if load can execute
    if fence.blocks_load(3):
        print(f"     LD1 blocked by fence - must wait")
        
        # Check if fence can complete
        st1_done = True  # Assume ST1 completed
        ld_before_fence_done = True  # No loads before fence
        
        if fence.can_complete(ld_before_fence_done, st1_done):
            fence.completed = True
            print(f"     Fence completed - LD1 can now execute")
    
    print(f"\nFence state: {fence}\n")


def scenario_5_memory_level_parallelism():
    """
    Scenario 5: Memory-Level Parallelism
    
    Demonstrates concurrent cache misses and MLP tracking.
    """
    print("=" * 70)
    print("SCENARIO 5: Memory-Level Parallelism")
    print("=" * 70)
    
    mshr = MSHRFile(num_entries=4, line_size=64)
    mlp_tracker = MLPTracker()
    banks = BankConflictDetector(num_banks=4, line_size=64)
    
    print("Simulating multiple concurrent cache misses...\n")
    
    # Miss 1: Load from 0x1000
    idx1 = mshr.allocate(0x1000, seq_num=1, cycle=10)
    mlp_tracker.record_cycle(1)
    print(f"Cycle 10: LD1 miss to [0x1000] - MSHR[{idx1}]")
    
    # Miss 2: Load from 0x2000 (different line, different bank)
    idx2 = mshr.allocate(0x2000, seq_num=2, cycle=11)
    mlp_tracker.record_cycle(2)
    print(f"Cycle 11: LD2 miss to [0x2000] - MSHR[{idx2}] (concurrent)")
    
    # Miss 3: Load from 0x3000
    idx3 = mshr.allocate(0x3000, seq_num=3, cycle=12)
    mlp_tracker.record_cycle(3)
    print(f"Cycle 12: LD3 miss to [0x3000] - MSHR[{idx3}] (concurrent)")
    
    # Request to same line as Miss 1 - should merge
    idx4 = mshr.allocate(0x1010, seq_num=4, cycle=13)
    mlp_tracker.record_cycle(3)  # Still 3 outstanding
    print(f"Cycle 13: LD4 miss to [0x1010] - MSHR[{idx4}] (merged with LD1)")
    
    # Complete misses
    mshr.complete(idx1, cycle=20)
    mlp_tracker.record_cycle(2)
    print(f"Cycle 20: LD1 completed")
    
    mshr.complete(idx2, cycle=21)
    mlp_tracker.record_cycle(1)
    print(f"Cycle 21: LD2 completed")
    
    mshr.complete(idx3, cycle=22)
    mlp_tracker.record_cycle(0)
    print(f"Cycle 22: LD3 completed")
    
    print(f"\nMSHR Stats: {mshr.get_stats()}")
    print(f"MLP Tracker: {mlp_tracker}")
    
    # Demonstrate bank conflicts
    print(f"\nBank Conflict Analysis:")
    banks.reserve_bank(0x1000, current_cycle=0, latency=1)
    banks.reserve_bank(0x2000, current_cycle=0, latency=1)
    
    can_access = banks.can_access(0x1040, current_cycle=0)  # Same bank as 0x1000
    print(f"  Access to 0x1040 while 0x1000 busy: {can_access}")
    
    banks.update_cycle(1)
    can_access = banks.can_access(0x1040, current_cycle=1)
    print(f"  Access to 0x1040 after bank free: {can_access}")
    print(f"  {banks}\n")


def scenario_6_atomic_operations():
    """
    Scenario 6: Atomic Operations
    
    Demonstrates atomic read-modify-write operations.
    """
    print("=" * 70)
    print("SCENARIO 6: Atomic Operations")
    print("=" * 70)
    
    # Compare-and-swap (CAS)
    cas = AtomicOperation("CAS", address=0x5000, seq_num=10)
    memory_value = 42
    
    print(f"Memory[0x5000] = {memory_value}")
    print(f"\n1. CAS: Compare-And-Swap")
    
    # Successful CAS
    success, old_val = cas.execute(memory_value=42, write_value=100, expected=42)
    print(f"   CAS(expected=42, new=100): success={success}, old_value={old_val}")
    
    # Failed CAS
    cas2 = AtomicOperation("CAS", address=0x5000, seq_num=11)
    success, old_val = cas2.execute(memory_value=42, write_value=100, expected=50)
    print(f"   CAS(expected=50, new=100): success={success}, old_value={old_val}")
    
    # Fetch-and-add
    print(f"\n2. FADD: Fetch-And-Add")
    fadd = AtomicOperation("FADD", address=0x5004, seq_num=12)
    success, old_val = fadd.execute(memory_value=10, write_value=5)
    print(f"   FADD(value=10, delta=5): success={success}, old_value={old_val}")
    print(f"   New value would be: {fadd.new_value}")
    
    print()


def scenario_7_store_buffer():
    """
    Scenario 7: Store Buffer and Coalescing
    
    Demonstrates store buffering and forwarding.
    """
    print("=" * 70)
    print("SCENARIO 7: Store Buffer")
    print("=" * 70)
    
    sb = StoreBuffer(capacity=4)
    
    print("Adding stores to buffer:")
    sb.add_store(address=0x1000, data=0xAA, size=4, seq_num=1)
    print(f"  ST1: [0x1000] = 0xAA")
    
    sb.add_store(address=0x1004, data=0xBB, size=4, seq_num=2)
    print(f"  ST2: [0x1004] = 0xBB")
    
    sb.add_store(address=0x1000, data=0xCC, size=4, seq_num=3)
    print(f"  ST3: [0x1000] = 0xCC (overwrites ST1)")
    
    print(f"\n{sb}")
    
    # Try forwarding
    print(f"\nForwarding to loads:")
    data = sb.forward_to_load(address=0x1000, size=4)
    print(f"  LD [0x1000]: forwarded=0x{data:X}" if data else "  LD [0x1000]: no forward")
    
    data = sb.forward_to_load(address=0x1004, size=4)
    print(f"  LD [0x1004]: forwarded=0x{data:X}" if data else "  LD [0x1004]: no forward")
    
    # Drain stores
    print(f"\nDraining stores:")
    while sb.entries:
        entry = sb.drain_oldest()
        if entry:
            print(f"  Drained: [0x{entry['address']:X}] = 0x{entry['data']:X}")
    
    print()


def main():
    """Run all example scenarios"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + " " * 10 + "Memory Disambiguation Speculation Examples" + " " * 15 + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")
    
    scenario_1_independent_ops()
    scenario_2_store_forwarding()
    scenario_3_speculation_violation()
    scenario_4_memory_fences()
    scenario_5_memory_level_parallelism()
    scenario_6_atomic_operations()
    scenario_7_store_buffer()
    
    print("=" * 70)
    print("All scenarios completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
