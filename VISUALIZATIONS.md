# Memory Disambiguation Speculation - Visual Guide

This document provides visual representations of key concepts from the paper analysis.

## 1. MDPT and MDST Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Out-of-Order Processor                        │
│                                                                   │
│  ┌────────────┐    ┌──────────────┐    ┌─────────────┐         │
│  │  Fetch &   │───▶│   Decode &   │───▶│   Issue     │         │
│  │  Predict   │    │   Rename     │    │   Queue     │         │
│  └────────────┘    └──────────────┘    └─────────────┘         │
│                                               │                  │
│                                               ▼                  │
│         ┌──────────────────────────────────────────────┐        │
│         │       Execution Units                        │        │
│         │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐   │        │
│         │  │ ALU  │  │ MUL  │  │LOAD  │  │STORE │   │        │
│         │  └──────┘  └──────┘  └──────┘  └──────┘   │        │
│         └──────────────────────────────────────────────┘        │
│                        │              │                          │
│                        ▼              ▼                          │
│         ┌─────────────────────────────────────────┐             │
│         │     Memory Dependence Prediction        │             │
│         │                                          │             │
│         │  ┌────────────────────────────────┐    │             │
│         │  │  MDPT (Prediction Table)       │    │             │
│         │  │  • Predicts LD-ST dependences  │    │             │
│         │  │  • Stores STPC, LDPC, DIST     │    │             │
│         │  │  • Indexed by PC hash          │    │             │
│         │  └────────────────────────────────┘    │             │
│         │              │                          │             │
│         │              ▼                          │             │
│         │  ┌────────────────────────────────┐    │             │
│         │  │  MDST (Synchronization Table)  │    │             │
│         │  │  • Synchronizes execution      │    │             │
│         │  │  • Stores V, F/E, IDs          │    │             │
│         │  │  • Prevents mis-speculation    │    │             │
│         │  └────────────────────────────────┘    │             │
│         └─────────────────────────────────────────┘             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 2. MDPT Entry Structure

```
╔═══════════════════════════════════════════════════════════════╗
║                    MDPT Entry (64-128 bits)                    ║
╠═══════════╦═══════════╦══════════╦══════════╦═════════╦═══════╣
║   LDPC    ║   STPC    ║  DIST    ║  CONF    ║   TAG   ║   V   ║
║ (16 bits) ║ (16 bits) ║ (8 bits) ║ (2 bits) ║ (20b)   ║ (1b)  ║
╚═══════════╩═══════════╩══════════╩══════════╩═════════╩═══════╝
     │           │           │           │          │        │
     │           │           │           │          │        └──▶ Valid bit
     │           │           │           │          └───────────▶ Address tag
     │           │           │           └──────────────────────▶ Confidence
     │           │           └──────────────────────────────────▶ Dependence distance
     │           └──────────────────────────────────────────────▶ Store PC
     └──────────────────────────────────────────────────────────▶ Load PC

DIST = LDID - STID (dynamic instance separation)
CONF = 2-bit saturating counter (00=low, 11=high confidence)
```

## 3. MDST Entry Structure

```
╔════════════════════════════════════════════════════════════════╗
║                    MDST Entry (32-64 bits)                      ║
╠═════╦═════╦══════════╦══════════╦══════════╦══════════╦═══════╣
║  V  ║ F/E ║   LDPC   ║   STPC   ║   LDID   ║   STID   ║  TAG  ║
║(1b) ║(1b) ║ (12 bits)║ (12 bits)║ (8 bits) ║ (8 bits) ║ (20b) ║
╚═════╩═════╩══════════╩══════════╩══════════╩══════════╩═══════╝
   │     │       │          │          │          │         │
   │     │       │          │          │          │         └──▶ Address tag
   │     │       │          │          │          └────────────▶ Store instance ID
   │     │       │          │          └───────────────────────▶ Load instance ID
   │     │       │          └──────────────────────────────────▶ Store PC
   │     │       └─────────────────────────────────────────────▶ Load PC
   │     └─────────────────────────────────────────────────────▶ Full/Empty sync
   └───────────────────────────────────────────────────────────▶ Valid bit

V:   1 = entry active, 0 = entry free
F/E: F (Full) = store completed, E (Empty) = store pending
```

## 4. Dependence Distance Calculation

### Static vs Dynamic View

```
PROGRAM CODE (Static View):
─────────────────────────────────
Address 0x1000:  ST  R1, [R2]     ← STPC = 0x1000
Address 0x1010:  ADD R3, R4, R5
Address 0x1020:  MUL R6, R7, R8
Address 0x1030:  LD  R9, [R2]     ← LDPC = 0x1030
─────────────────────────────────
Static Distance = 0x1030 - 0x1000 = 0x30 (48 bytes)
❌ MDPT does NOT use this!


EXECUTION STREAM (Dynamic View):
──────────────────────────────────────────────
Cycle 10:  ST  R1, [R2]  (STID=42, STPC=0x1000)  ┐
Cycle 11:  ADD R3, R4, R5 (ID=43)                 │
Cycle 12:  MUL R6, R7, R8 (ID=44)                 │ DIST = 5
Cycle 13:  SUB ...        (ID=45)                 │ instructions
Cycle 14:  OR  ...        (ID=46)                 │
Cycle 15:  LD  R9, [R2]  (LDID=47, LDPC=0x1030)  ┘
──────────────────────────────────────────────
Dynamic Distance (DIST) = LDID - STID = 47 - 42 = 5
✅ MDPT uses this!
```

### Why Dynamic Distance Matters

```
LOOP EXAMPLE:
─────────────────────────────────────────────────────────
for (i = 0; i < 100; i++) {
    array[i] = compute(i);      // Store (STPC=0x1000)
    x = array[i];               // Load  (LDPC=0x1030)
}
─────────────────────────────────────────────────────────

Iteration 1:  STID=10, LDID=15  → DIST=5   (same STPC, LDPC)
Iteration 2:  STID=20, LDID=25  → DIST=5   (same STPC, LDPC)
Iteration 3:  STID=30, LDID=35  → DIST=5   (same STPC, LDPC)
...

MDPT Entry: STPC=0x1000, LDPC=0x1030, DIST=5
This single entry handles ALL iterations!
```

## 5. V and F/E Bit State Transitions

```
MDST Entry Lifecycle:
═════════════════════════════════════════════════════════════

State 1: ENTRY FREE
┌──────────────────┐
│  V = 0           │  Entry is available for allocation
│  F/E = X         │  (don't care state)
└──────────────────┘
         │
         │ MDPT predicts dependence
         ▼
State 2: ENTRY ALLOCATED (Store Pending)
┌──────────────────┐
│  V = 1           │  Entry is active
│  F/E = E (Empty) │  Store hasn't completed - LOAD MUST WAIT!
│  LDPC, STPC set  │
│  LDID, STID set  │
└──────────────────┘
         │
         │ Store completes execution
         ▼
State 3: STORE COMPLETED
┌──────────────────┐
│  V = 1           │  Entry still active
│  F/E = F (Full)  │  Store done - LOAD CAN PROCEED!
│  Data is ready!  │
└──────────────────┘
         │
         │ Load executes and completes
         ▼
State 4: ENTRY FREED
┌──────────────────┐
│  V = 0           │  Entry released back to free pool
│  F/E = X         │  Ready for next dependence
└──────────────────┘
```

## 6. Execution Timeline Example

```
TIME FLOW: Dependent Load-Store Pair
═══════════════════════════════════════════════════════════════════

Cycle 0:  Store dispatched (ST R1, [R2])
          STID=42, STPC=0x1000
          └─▶ MDPT lookup: No prediction yet
          
Cycle 5:  Load dispatched (LD R3, [R2])
          LDID=47, LDPC=0x1030
          └─▶ MDPT lookup: Predicts dependence on STPC=0x1000
              └─▶ Allocate MDST entry:
                  V=1, F/E=E, STPC=0x1000, LDPC=0x1030
                  STID=42, LDID=47, DIST=5

Cycle 6:  Load ready to execute
          └─▶ Check MDST: F/E=E (Empty)
              └─▶ BLOCKED! Must wait for store

Cycle 10: Store completes execution
          └─▶ Update MDST: F/E=F (Full)
              └─▶ Signal waiting load

Cycle 11: Load unblocked and executes
          └─▶ Reads correct value from store
              └─▶ Success! No mis-speculation

Cycle 12: Load completes
          └─▶ Free MDST entry: V=0

═══════════════════════════════════════════════════════════════════

KEY INTERACTIONS:
─────────────────
V bit:   Controls whether entry exists (resource management)
F/E bit: Controls whether load can execute (synchronization)
DIST:    Helps schedule when load should check store status
```

## 7. Performance Impact Visualization

```
IPC (Instructions Per Cycle) Comparison:
═════════════════════════════════════════════════════════════

Conservative (Always Stall):
┌────────────────────────────────────┐
│████████████                        │  IPC = 1.5
└────────────────────────────────────┘

MDPT + MDST (This Paper):
┌────────────────────────────────────┐
│████████████████████                │  IPC = 2.0  (+33%)
└────────────────────────────────────┘

Aggressive (Always Speculate):
┌────────────────────────────────────┐
│██████████████████                  │  IPC = 1.9  (mis-spec penalty)
└────────────────────────────────────┘

Perfect (Oracle):
┌────────────────────────────────────┐
│█████████████████████               │  IPC = 2.1
└────────────────────────────────────┘

═════════════════════════════════════════════════════════════

Prediction Accuracy vs Performance:
───────────────────────────────────────────────
Accuracy    IPC Gain    Notes
───────────────────────────────────────────────
> 95%       +30-40%     Excellent - almost optimal
85-95%      +20-30%     Good - most benchmarks here
70-85%      +10-20%     Moderate - still worthwhile
< 70%       +0-10%      Poor - mis-spec overhead high
───────────────────────────────────────────────
```

## 8. Hardware Cost Analysis

```
HARDWARE REQUIREMENTS:
═══════════════════════════════════════════════════════════

MDPT (2K entries):
┌─────────────────────────────────────────────────┐
│  Entry Size: 64 bits                            │
│  Total Size: 2048 × 64 = 131,072 bits = 16 KB  │
│  Access: 1 read + 1 write per load/store       │
│  Latency: 1-2 cycles (SRAM)                    │
└─────────────────────────────────────────────────┘

MDST (256 entries):
┌─────────────────────────────────────────────────┐
│  Entry Size: 48 bits                            │
│  Total Size: 256 × 48 = 12,288 bits = 1.5 KB   │
│  Access: Multiple reads/writes per cycle       │
│  Latency: 1 cycle (CAM/SRAM hybrid)            │
└─────────────────────────────────────────────────┘

Additional Logic:
┌─────────────────────────────────────────────────┐
│  Hash Functions: ~500 gates                     │
│  Comparators: ~1000 gates                       │
│  Control Logic: ~2000 gates                     │
│  Total: ~3500 gates + 17.5 KB storage          │
└─────────────────────────────────────────────────┘

TOTAL OVERHEAD: ~20 KB + 3500 gates
(Negligible in modern processors with MB of cache)
```

## 9. Benchmark Categories

```
PERFORMANCE BY WORKLOAD TYPE:
═════════════════════════════════════════════════════════════

High Benefit (30-40% speedup):
┌──────────────────────────────────────────────┐
│  gcc, li, ijpeg                              │
│  Characteristics:                            │
│  • Regular array accesses                    │
│  • Predictable pointer chasing               │
│  • Loop-based computation                    │
└──────────────────────────────────────────────┘

Medium Benefit (15-25% speedup):
┌──────────────────────────────────────────────┐
│  swim, su2cor, tomcatv                       │
│  Characteristics:                            │
│  • Floating-point arrays                     │
│  • Stride patterns                           │
│  • Some irregular accesses                   │
└──────────────────────────────────────────────┘

Low Benefit (5-15% speedup):
┌──────────────────────────────────────────────┐
│  go, compress, m88ksim                       │
│  Characteristics:                            │
│  • Irregular control flow                    │
│  • Unpredictable branches                    │
│  • Pointer-intensive with randomness         │
└──────────────────────────────────────────────┘
```

## 10. Complete System Flow

```
COMPLETE PREDICTION AND SYNCHRONIZATION FLOW:
═════════════════════════════════════════════════════════════════════════

PIPELINE STAGES:
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ FETCH   │─→│ DECODE  │─→│  ISSUE  │─→│ EXECUTE │─→│ COMMIT  │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
                                │               │
                                ▼               ▼
                    ┌───────────────────────────────────┐
                    │  MEMORY DEPENDENCE SUBSYSTEM      │
                    │                                   │
                    │  [1] PREDICT (MDPT)              │
                    │       ▼                           │
                    │  [2] ALLOCATE (MDST)             │
                    │       ▼                           │
                    │  [3] SYNCHRONIZE (F/E)           │
                    │       ▼                           │
                    │  [4] EXECUTE (when safe)         │
                    │       ▼                           │
                    │  [5] UPDATE (learn)              │
                    └───────────────────────────────────┘

DETAILED OPERATION:

Store Instruction:
1. Issue → Hash(STPC) → MDPT lookup
2. Record dependence history
3. If predicted dependent load exists → allocate MDST
4. Set MDST: V=1, F/E=E
5. Execute store
6. Complete → Update MDST: F/E=F
7. Wake dependent loads

Load Instruction:
1. Issue → Hash(LDPC) → MDPT lookup
2. Predict dependent store (if any)
3. Calculate expected STID = LDID - DIST
4. Search MDST for matching entry
5. If found and F/E=E → BLOCK load
6. If found and F/E=F → EXECUTE load
7. If not found → SPECULATE (execute immediately)
8. Commit → Update MDPT confidence
```

---

## Summary

These visualizations illustrate:
1. **DIST uses dynamic IDs** for accurate runtime tracking
2. **V and F/E serve distinct purposes** in entry management and synchronization
3. **MDPT+MDST work together** to enable safe speculation with modest hardware cost
4. **Performance benefits are significant** for regular workloads (15-30% average)

The architecture provides a practical hardware solution for memory disambiguation that balances performance, accuracy, and cost.
