# Architecture Diagrams

## 3-Stage Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        3-Stage OoO Pipeline                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │    ISSUE     │───▶│   EXECUTE    │───▶│   COMMIT     │              │
│  │    STAGE     │    │    STAGE     │    │    STAGE     │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│        │                    │                    │                       │
│        ▼                    ▼                    ▼                       │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐                │
│  │   ROB    │         │   LSQ    │         │  Memory  │                │
│  │ Allocate │         │  Search  │         │  Update  │                │
│  └──────────┘         └──────────┘         └──────────┘                │
│        │                    │                    │                       │
│        ▼                    ▼                    ▼                       │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐                │
│  │Predictor │         │   MSHR   │         │  Store   │                │
│  │  Query   │         │  Check   │         │  Buffer  │                │
│  └──────────┘         └──────────┘         └──────────┘                │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Load-Store Queue Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load-Store Queue (LSQ)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  HEAD ──▶ [Entry 0] ─┬─▶ Seq: 1, PC: 0x1000, Type: STORE       │
│           [Entry 1] ─┼─▶ Seq: 2, PC: 0x1004, Type: LOAD         │
│           [Entry 2] ─┼─▶ Seq: 3, PC: 0x1008, Type: STORE        │
│           [Entry 3] ─┴─▶ Seq: 4, PC: 0x100C, Type: LOAD         │
│  TAIL ──▶ [Entry 4] ─┬─▶ Empty                                  │
│           [Entry 5] ─┼─▶ Empty                                   │
│           [Entry 6] ─┴─▶ Empty                                   │
│                                                                   │
│  Operations:                                                      │
│  • Allocate new entry at TAIL                                    │
│  • Check dependencies (search from HEAD to current entry)        │
│  • Forward data from matching store                              │
│  • Commit from HEAD (in-order)                                   │
│  • Squash from seq_num (for recovery)                            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Store Set Predictor

```
┌─────────────────────────────────────────────────────────────────┐
│              Store Set Memory Disambiguation Predictor           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────┐                            │
│  │  SSIT (Store Set ID Table)      │                            │
│  ├─────────────────────────────────┤                            │
│  │  PC Index  │  Store Set ID      │                            │
│  ├────────────┼────────────────────┤                            │
│  │    42      │       1            │ ◀─── LD @ 0x1000           │
│  │    58      │       1            │ ◀─── ST @ 0x1008           │
│  │   103      │       3            │ ◀─── LD @ 0x2000           │
│  │   217      │       3            │ ◀─── ST @ 0x2010           │
│  └────────────┴────────────────────┘                            │
│                                                                   │
│  ┌─────────────────────────────────┐                            │
│  │  LFST (Last Fetched Store)      │                            │
│  ├─────────────────────────────────┤                            │
│  │  Store Set │  Last Store Seq#   │                            │
│  ├────────────┼────────────────────┤                            │
│  │      1     │       100          │ ◀─── ST from set 1         │
│  │      3     │       215          │ ◀─── ST from set 3         │
│  └────────────┴────────────────────┘                            │
│                                                                   │
│  Prediction Flow:                                                │
│  1. Load PC → Hash → SSIT Index                                 │
│  2. SSIT[Index] → Store Set ID                                  │
│  3. LFST[Set ID] → Pending Store Seq#                           │
│  4. If pending store exists → Wait, else → Speculate            │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Speculation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              Speculative Load Execution Flow                     │
└─────────────────────────────────────────────────────────────────┘

  Load Instruction
         │
         ▼
  ┌─────────────┐
  │  Calculate  │
  │   Address   │
  └─────────────┘
         │
         ▼
  ┌─────────────────────┐           ┌──────────────┐
  │ Search LSQ for      │──YES───▶  │   Forward    │
  │ matching Store?     │           │     Data     │
  └─────────────────────┘           └──────────────┘
         │ NO                              │
         ▼                                 │
  ┌─────────────────────┐                 │
  │  Query Predictor    │                 │
  │  Can Speculate?     │                 │
  └─────────────────────┘                 │
         │                                 │
    ┌────┴─────┐                          │
    │          │                           │
   YES        NO                           │
    │          │                           │
    ▼          ▼                           │
┌────────┐ ┌─────┐                        │
│Execute │ │Wait │                        │
│Spec.   │ │for  │                        │
│Load    │ │Store│                        │
└────────┘ └─────┘                        │
    │          │                           │
    └────┬─────┘                           │
         ▼                                 │
  ┌─────────────────┐                     │
  │  Load Result    │◀────────────────────┘
  │    Available    │
  └─────────────────┘
         │
         ▼
  ┌─────────────────┐
  │  At Commit:     │
  │  Validate       │
  │  Speculation    │
  └─────────────────┘
         │
    ┌────┴─────┐
    │          │
 CORRECT   VIOLATION
    │          │
    ▼          ▼
┌────────┐ ┌──────────┐
│Commit  │ │  Squash  │
│& Free  │ │  & Retry │
└────────┘ └──────────┘
             │
             ▼
      ┌──────────────┐
      │Update        │
      │Predictor     │
      └──────────────┘
```

## Memory-Level Parallelism Components

```
┌─────────────────────────────────────────────────────────────────┐
│              Memory-Level Parallelism Architecture               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────┐             │
│  │         MSHR File (8 entries)                  │             │
│  ├────────────────────────────────────────────────┤             │
│  │ [0] Miss to 0x1000 - Waiting: LD1, LD4        │             │
│  │ [1] Miss to 0x2000 - Waiting: LD2             │             │
│  │ [2] Miss to 0x3000 - Waiting: LD3, ST1        │             │
│  │ [3] Empty                                      │             │
│  │ [4] Empty                                      │             │
│  │ [5] Prefetch 0x4000 - Waiting: none           │             │
│  └────────────────────────────────────────────────┘             │
│                          │                                       │
│                          ▼                                       │
│  ┌────────────────────────────────────────────────┐             │
│  │         Cache Bank Organization                │             │
│  ├─────────┬─────────┬─────────┬─────────┐        │             │
│  │ Bank 0  │ Bank 1  │ Bank 2  │ Bank 3  │        │             │
│  ├─────────┼─────────┼─────────┼─────────┤        │             │
│  │  BUSY   │  FREE   │  FREE   │  BUSY   │        │             │
│  │ 0x1000  │         │         │ 0x3000  │        │             │
│  └─────────┴─────────┴─────────┴─────────┘        │             │
│                                                                   │
│  ┌────────────────────────────────────────────────┐             │
│  │         Prefetch Queue                         │             │
│  ├────────────────────────────────────────────────┤             │
│  │ [0x4000] Confidence: 0.9                       │             │
│  │ [0x4040] Confidence: 0.8                       │             │
│  │ [0x4080] Confidence: 0.7                       │             │
│  └────────────────────────────────────────────────┘             │
│                                                                   │
│  Features:                                                        │
│  • Up to 8 concurrent cache misses (MSHR capacity)               │
│  • Bank-level parallelism (4 banks)                              │
│  • Separate prefetch queue to avoid interference                 │
│  • Request merging for same cache line                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Synchronization Mechanisms

```
┌─────────────────────────────────────────────────────────────────┐
│                  Synchronization Primitives                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Memory Fences:                                                  │
│  ┌──────────┐                                                    │
│  │  LFENCE  │──▶ No younger loads before older loads complete   │
│  └──────────┘                                                    │
│  ┌──────────┐                                                    │
│  │  SFENCE  │──▶ No younger stores before older stores complete │
│  └──────────┘                                                    │
│  ┌──────────┐                                                    │
│  │  MFENCE  │──▶ Full memory barrier (loads + stores)           │
│  └──────────┘                                                    │
│                                                                   │
│  Atomic Operations:                                              │
│  ┌────────────────────────────────────┐                         │
│  │  CAS (Compare-And-Swap)            │                         │
│  │  if (mem == expected) {            │                         │
│  │      mem = new_value;              │                         │
│  │      return true;                  │                         │
│  │  } else {                           │                         │
│  │      return false;                 │                         │
│  │  }                                  │                         │
│  └────────────────────────────────────┘                         │
│                                                                   │
│  Store Buffer:                                                   │
│  ┌────────────────────────────────────┐                         │
│  │  HEAD ──▶ [0x1000] = 0xAA          │                         │
│  │           [0x1004] = 0xBB          │                         │
│  │  TAIL ──▶ [0x1000] = 0xCC          │ ◀─ Newest (forwarded)  │
│  └────────────────────────────────────┘                         │
│  • Drain oldest first to memory                                 │
│  • Forward from newest matching entry                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Complete System Integration

```
┌───────────────────────────────────────────────────────────────────┐
│                    Integrated System View                          │
└───────────────────────────────────────────────────────────────────┘

   Instructions                         Memory System
        │                                      │
        ▼                                      │
   ┌─────────┐                                │
   │ Issue   │                                │
   │ Stage   │                                │
   └─────────┘                                │
        │                                      │
   ┌────┴────┐                                │
   │   ROB   │                                │
   │Allocate │                                │
   └────┬────┘                                │
        │                                      │
   ┌────┴────────┐                            │
   │  Predictor  │                            │
   │   Query     │                            │
   └────┬────────┘                            │
        │                                      │
        ▼                                      │
   ┌─────────┐                                │
   │ Execute │                                │
   │ Stage   │                                │
   └─────────┘                                │
        │                                      │
   ┌────┴─────┐                               │
   │   LSQ    │                               │
   │  Search  │                               │
   └────┬─────┘                               │
        │                                      │
   ┌────┴─────┐                     ┌─────────▼────────┐
   │Speculate │────────────────────▶│  MSHR + Cache    │
   │  Load    │                     │  Bank System     │
   └────┬─────┘                     └─────────┬────────┘
        │                                      │
        ▼                                      │
   ┌─────────┐                                │
   │ Commit  │                                │
   │ Stage   │                                │
   └─────────┘                                │
        │                                      │
   ┌────┴──────┐                              │
   │ Validate  │                              │
   │Speculation│                              │
   └────┬──────┘                              │
        │                                      │
   ┌────┴──────┐                    ┌─────────▼────────┐
   │   Store   │───────────────────▶│     Memory       │
   │   Buffer  │                    └──────────────────┘
   └───────────┘

   Data Flow: ━━━▶
   Control:   ─ ─ ▶
```

## Performance Metrics

```
┌─────────────────────────────────────────────────────────────────┐
│                    Key Performance Metrics                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Speculation Accuracy:                                           │
│  ────────────────────────────────────────────                   │
│  Correct Predictions / Total Predictions × 100%                 │
│                                                                   │
│  Memory-Level Parallelism (MLP):                                │
│  ────────────────────────────────────────────                   │
│  Average Outstanding Misses per Cycle                           │
│                                                                   │
│  IPC (Instructions Per Cycle):                                  │
│  ────────────────────────────────────────────                   │
│  Committed Instructions / Total Cycles                          │
│                                                                   │
│  LSQ Utilization:                                               │
│  ────────────────────────────────────────────                   │
│  Average Entries Used / Total Capacity × 100%                   │
│                                                                   │
│  Bank Conflict Rate:                                            │
│  ────────────────────────────────────────────                   │
│  Conflicts / Total Accesses × 100%                              │
│                                                                   │
│  Prefetch Accuracy:                                             │
│  ────────────────────────────────────────────                   │
│  Useful Prefetches / Total Prefetches × 100%                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```
