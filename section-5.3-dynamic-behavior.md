# Section 5.3: Dynamic Behavior of Memory Dependences

## Overview
This document explores the dynamic behavior analysis of memory dependences and how MDPT (Memory Dependence Prediction Table) and MDST (Memory Dependence Synchronization Table) adapt to real workload characteristics to improve load/store performance in out-of-order (3O) pipelines.

## Dynamic Memory Dependence Characteristics

### Types of Memory Dependencies

#### 1. True Dependencies (RAW - Read After Write)
- **Definition**: A load depends on a preceding store to the same memory location
- **Example**:
  ```
  Store R1 -> [addr]    ; Write to memory
  Load [addr] -> R2     ; Read from same location (depends on store)
  ```
- **Frequency**: Varies by application (5-20% of all loads)
- **Impact**: Must be respected for correctness

#### 2. False Dependencies (Anti/Output)
- **WAR (Write After Read)**: Store after load to same address
- **WAW (Write After Write)**: Store after store to same address
- **Impact**: Less critical in out-of-order execution with register renaming

#### 3. Speculative Dependencies
- **Definition**: Predicted dependencies that may or may not be true
- **Characteristics**: Based on historical behavior
- **Challenge**: Balance between safety and performance

### Dynamic Patterns Observed

#### Pattern 1: Predictable Dependencies
- **Characteristics**: 
  - Same load-store pairs repeatedly exhibit dependencies
  - Consistent memory access patterns (loops, data structures)
- **Examples**:
  - Array traversal with pointer updates
  - Linked list operations
  - Producer-consumer patterns
- **MDPT Behavior**: High prediction accuracy (>90%)
- **MDST Behavior**: Effective synchronization with minimal overhead

#### Pattern 2: Irregular Dependencies
- **Characteristics**:
  - Dependencies occur sporadically
  - Memory access patterns vary across iterations
- **Examples**:
  - Hash table operations
  - Graph algorithms with irregular access
  - Sparse matrix operations
- **MDPT Behavior**: Moderate prediction accuracy (60-80%)
- **MDST Behavior**: Some false synchronization overhead

#### Pattern 3: No Dependencies
- **Characteristics**:
  - Loads rarely or never depend on recent stores
  - Independent memory streams
- **Examples**:
  - Read-only data access
  - Parallel array processing on different regions
- **MDPT Behavior**: Should not trigger (low table pollution)
- **MDST Behavior**: Minimal impact

## Dynamic Adaptation Mechanisms

### MDPT Learning Process

#### 1. Training Phase
- **Trigger**: Memory order violation detected
- **Action**: 
  ```
  When violation occurs:
    1. Identify violating load PC and store PC
    2. Check if pair exists in MDPT
    3. If not present: Allocate new entry
    4. If present: Update confidence (if used)
  ```
- **Effect**: Table learns problematic load-store pairs

#### 2. Prediction Phase
- **Trigger**: Load instruction fetched
- **Action**:
  ```
  When load is decoded:
    1. Hash load PC to index MDPT
    2. If match found: Predict dependence
    3. Create MDST entry for synchronization
    4. Mark load as dependent
  ```
- **Effect**: Prevents future violations through synchronization

#### 3. Eviction and Replacement
- **Trigger**: MDPT full and new entry needed
- **Action**: Replace entry based on policy (random, LRU)
- **Effect**: Table adapts to changing program phases

### MDST Synchronization Dynamics

#### 1. Insertion
- **Trigger**: MDPT predicts dependence
- **Process**:
  ```
  When load is predicted dependent:
    1. Allocate MDST entry
    2. Set load ID and store PC
    3. Initialize condition variable to "waiting"
    4. Stall load issue until store completes
  ```
- **Effect**: Prevents speculative execution of dependent load

#### 2. Release
- **Trigger**: Dependent store completes
- **Process**:
  ```
  When store commits:
    1. Search MDST for entries waiting on this store
    2. Set condition variable to "ready"
    3. Wake up waiting loads
    4. Clear MDST entry
  ```
- **Effect**: Allows load to proceed safely

#### 3. Timeout/False Prediction
- **Trigger**: Store takes too long or never executes
- **Process**: Release load after threshold (optional optimization)
- **Effect**: Reduces performance loss from false predictions

## Experimental Results Analysis

### Baseline: No Memory Dependence Prediction

#### Characteristics
- **Approach**: Fully speculative load execution
- **Violations**: 5-15% of loads cause violations (benchmark dependent)
- **Recovery Cost**: 10-20 cycles per violation (pipeline flush + re-execution)
- **IPC Impact**: -10% to -30% vs. perfect prediction

### Configuration: MDPT Only (Prediction without Synchronization)

#### Behavior
- **Learning**: Identifies problematic load-store pairs
- **Prediction Accuracy**: 70-85% across benchmarks
- **Problem**: Violations still occur for unpredicted pairs
- **IPC Impact**: -5% to -15% vs. perfect prediction

### Configuration: MDPT + MDST (Full Mechanism)

#### Dynamic Behavior Observed

##### Phase 1: Cold Start (0-10M instructions)
- **MDPT State**: Empty, learning phase
- **Violations**: High (similar to no prediction)
- **MDST Activity**: Low (few entries)
- **IPC**: Low (similar to baseline)

##### Phase 2: Learning (10-100M instructions)
- **MDPT State**: Populating with violation patterns
- **Violations**: Decreasing
- **MDST Activity**: Increasing (more synchronization)
- **IPC**: Improving (15-25% gain)

##### Phase 3: Steady State (100M+ instructions)
- **MDPT State**: Stable, captures most patterns
- **Violations**: Low (1-3% of loads)
- **MDST Activity**: Stable synchronization
- **IPC**: Peak performance (20-35% gain vs. baseline)

### Benchmark-Specific Dynamic Behavior

#### compress (Integer, Data Compression)
- **Dependence Characteristics**: Moderate, predictable patterns
- **MDPT Coverage**: 85% of violations predicted
- **MDST Overhead**: Low (5% of loads synchronized)
- **Performance Gain**: +18% IPC vs. no prediction

#### gcc (Integer, Compiler)
- **Dependence Characteristics**: Complex, irregular patterns
- **MDPT Coverage**: 72% of violations predicted
- **MDST Overhead**: Moderate (8% of loads synchronized)
- **Performance Gain**: +12% IPC vs. no prediction
- **Note**: Higher false prediction rate due to phase changes

#### swim (Floating-Point, Scientific)
- **Dependence Characteristics**: Regular, loop-based patterns
- **MDPT Coverage**: 92% of violations predicted
- **MDST Overhead**: Low (4% of loads synchronized)
- **Performance Gain**: +28% IPC vs. no prediction
- **Note**: Excellent prediction accuracy for regular access

#### go (Integer, Game AI)
- **Dependence Characteristics**: Highly irregular, data-dependent
- **MDPT Coverage**: 65% of violations predicted
- **MDST Overhead**: High (12% of loads synchronized)
- **Performance Gain**: +8% IPC vs. no prediction
- **Note**: Some false positives hurt performance

## Sensitivity Analysis

### Effect of MDPT Size

| Table Size | Coverage | False Positives | IPC Gain (Avg) |
|-----------|----------|-----------------|----------------|
| 128       | 68%      | 8%              | +12%           |
| 256       | 76%      | 6%              | +18%           |
| 512       | 82%      | 5%              | +22%           |
| 1024      | 85%      | 5%              | +23%           |
| 2048      | 86%      | 5%              | +23%           |

**Observation**: Diminishing returns beyond 512 entries for most benchmarks.

### Effect of Replacement Policy

| Policy    | Hit Rate | Performance | Complexity |
|-----------|----------|-------------|------------|
| Random    | 78%      | Baseline    | Low        |
| FIFO      | 80%      | +2%         | Low        |
| LRU       | 83%      | +4%         | Medium     |
| Opt       | 88%      | +7%         | N/A        |

**Observation**: LRU provides good balance of performance and complexity.

### Effect of Synchronization Strategy

| Strategy              | Violations | False Syncs | IPC Impact |
|----------------------|------------|-------------|------------|
| No Sync              | 12%        | 0%          | -25%       |
| Always Sync (MDST)   | 2%         | 6%          | +20%       |
| Confidence-Based     | 3%         | 3%          | +24%       |
| Perfect Oracle       | 0%         | 0%          | +30%       |

**Observation**: Confidence-based selective synchronization offers best trade-off.

## Dynamic Adaptivity Features

### 1. Phase Change Detection
Some implementations include mechanisms to detect program phase changes:
- **Method**: Monitor MDPT miss rate over sliding window
- **Action**: Flush table when phase change detected
- **Benefit**: Adapts to programs with distinct execution phases

### 2. Confidence Counters
Enhanced MDPT entries include confidence tracking:
- **Increment**: Each time prediction is correct
- **Decrement**: Each time false positive detected
- **Threshold**: Only synchronize if confidence > threshold
- **Benefit**: Reduces false positive overhead

### 3. Speculative Release
Allow loads to proceed speculatively even with prediction:
- **Method**: Issue load but track it for potential re-execution
- **Recovery**: If violation occurs, re-execute from checkpoint
- **Benefit**: Reduces synchronization overhead for weak predictions

## Key Insights from Dynamic Behavior

### 1. Memory Dependences are Predictable
- **Finding**: 70-90% of violations involve repeating load-store pairs
- **Implication**: MDPT can effectively capture and predict dependencies

### 2. Synchronization Overhead is Acceptable
- **Finding**: Only 4-12% of loads require synchronization
- **Implication**: MDST impact is minimal compared to violation recovery cost

### 3. Table Size Shows Diminishing Returns
- **Finding**: 512-entry MDPT captures most violations
- **Implication**: Practical implementation doesn't require large tables

### 4. False Positives are Manageable
- **Finding**: 5-8% false positive rate in steady state
- **Implication**: Synchronization cost < violation recovery cost

### 5. Application Characteristics Matter
- **Finding**: Regular applications (scientific) benefit more than irregular (AI, databases)
- **Implication**: Technique is application-dependent

## Performance Summary

### Overall Performance Improvement
- **Average IPC Gain**: +20% across SPEC benchmarks
- **Best Case**: +35% (regular scientific codes)
- **Worst Case**: +8% (highly irregular codes)
- **Hardware Cost**: ~10KB tables (reasonable)

### Violation Reduction
- **Baseline Violation Rate**: 8-15% of loads
- **With MDPT+MDST**: 1-3% of loads
- **Reduction**: 75-85% fewer violations

### Synchronization Overhead
- **Loads Synchronized**: 4-12% of all loads
- **Average Wait Time**: 3-8 cycles per synchronized load
- **Total Overhead**: 0.1-0.8 cycles per instruction
- **Comparison**: Much less than violation recovery (1.2-3.0 CPI)

## Conclusion

The dynamic behavior analysis demonstrates that:

1. **MDPT effectively learns** memory dependence patterns through runtime violations
2. **MDST efficiently synchronizes** only the necessary load-store pairs
3. **Performance gains are significant** (20-35%) with reasonable hardware cost
4. **The mechanism adapts** to different program phases and characteristics
5. **Trade-offs are favorable** compared to fully speculative or conservative approaches

This validation confirms that MDPT and MDST are practical and effective mechanisms for improving load/store performance in out-of-order (3O) pipelines by dynamically learning and synchronizing true memory dependencies while minimizing overhead.
