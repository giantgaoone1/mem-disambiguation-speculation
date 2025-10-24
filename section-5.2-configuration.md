# Section 5.2: Configuration

## Overview
This document explores the experimental configuration used to evaluate Memory Dependence Prediction Table (MDPT) and Memory Dependence Synchronization Table (MDST) mechanisms for improving load/store performance in out-of-order (3O) pipelines.

## Experimental Setup

### Processor Architecture: Multiscalar Processor
The experiments are based on a Multiscalar processor model, which is designed to exploit instruction-level parallelism (ILP) through:
- **Out-of-Order Issue**: Instructions can be issued in a different order than they appear in the program
- **Out-of-Order Execute**: Instructions can execute as soon as their operands are available
- **Out-of-Order Commit**: Results can be committed when safe to do so

### Memory Dependence Prediction Table (MDPT)

#### Structure
- **Entry Format**: Each MDPT entry contains:
  - Valid bit: Indicates if the entry is active
  - Load PC (Program Counter): Identifies the load instruction
  - Store PC (Program Counter): Identifies the dependent store instruction
  - Confidence counter (optional): Tracks prediction accuracy

#### Configuration Parameters
- **Table Size**: Typically configured with 256 to 2048 entries
- **Indexing**: Uses hashed PC values to index into the table
- **Associativity**: Commonly implemented as:
  - Direct-mapped (1-way)
  - 2-way or 4-way set-associative
  - Fully associative (for smaller tables)

#### Replacement Policy
- **Random Replacement**: When the table is full, entries are replaced randomly
- **Rationale**: Simplicity and effectiveness in maintaining recent violation information
- **Alternative**: LRU (Least Recently Used) for better temporal locality

### Memory Dependence Synchronization Table (MDST)

#### Structure
- **Entry Format**: Each MDST entry contains:
  - Load PC: Identifies the dependent load
  - Store PC: Identifies the producer store
  - Load ID: Dynamic identifier for the load instance
  - Store ID: Dynamic identifier for the store instance
  - Condition Variable: Synchronization state for the pair

#### Configuration Parameters
- **Table Size**: Matched to MDPT size or slightly larger
- **Indexing**: Uses combined hash of load and store PCs
- **State Management**: Tracks synchronization status

#### Operation
- **Insertion**: When MDPT predicts a dependence, corresponding entry created in MDST
- **Synchronization**: Load waits until dependent store completes
- **Removal**: Entry cleared when load commits successfully

## Simulation Configuration

### Baseline Processor Parameters
- **Instruction Window Size**: 128-256 instructions
- **Reorder Buffer (ROB)**: 128-256 entries
- **Load/Store Queue**: 32-64 entries each
- **Functional Units**: 
  - 4-8 integer ALUs
  - 2-4 floating-point units
  - 2-4 load/store units
- **Branch Predictor**: 
  - 2-level adaptive predictor
  - 4K-8K entry branch history table

### Memory System Configuration
- **L1 Data Cache**: 
  - Size: 32KB-64KB
  - Associativity: 2-way or 4-way
  - Line size: 64 bytes
  - Hit latency: 1-2 cycles
- **L1 Instruction Cache**:
  - Size: 32KB-64KB
  - Associativity: 2-way or 4-way
  - Line size: 64 bytes
  - Hit latency: 1-2 cycles
- **L2 Unified Cache**:
  - Size: 256KB-1MB
  - Associativity: 4-way or 8-way
  - Line size: 64 bytes
  - Hit latency: 8-12 cycles
- **Main Memory Latency**: 80-120 cycles

## Benchmark Configuration

### SPEC Benchmarks
The evaluation typically uses SPEC CPU benchmarks to measure performance:

#### SPEC Integer Benchmarks
- **compress**: Data compression
- **gcc**: GNU C compiler
- **go**: AI game playing
- **ijpeg**: Image compression
- **li**: LISP interpreter
- **perl**: Perl interpreter
- **vortex**: Object-oriented database

#### SPEC Floating-Point Benchmarks
- **swim**: Shallow water modeling
- **tomcatv**: Mesh generation
- **hydro2d**: Hydrodynamic simulation
- **mgrid**: Multi-grid solver
- **applu**: Parabolic/elliptic PDE solver
- **apsi**: Pollutant distribution

### Workload Characteristics
- **Input Sets**: Standard reference inputs for reproducibility
- **Simulation Length**: 
  - Fast-forward: Skip initialization (100M-500M instructions)
  - Detailed simulation: 100M-500M instructions
- **Metrics Collected**:
  - Instructions per cycle (IPC)
  - Memory order violations
  - MDPT accuracy
  - Synchronization overhead

## Performance Metrics

### Primary Metrics
1. **IPC (Instructions Per Cycle)**: Overall processor throughput
2. **Memory Order Violation Rate**: Frequency of load-store conflicts
3. **Prediction Accuracy**: Percentage of correct MDPT predictions
4. **Synchronization Overhead**: Additional cycles due to MDST waiting

### Secondary Metrics
1. **MDPT Hit Rate**: Percentage of loads found in MDPT
2. **MDPT Miss Rate**: Percentage of loads not in MDPT
3. **False Dependence Rate**: Incorrect predictions causing unnecessary waits
4. **Coverage**: Percentage of actual violations predicted

## Verification Methodology

### Configuration Variations Tested
To verify the effectiveness of MDPT and MDST, experiments typically vary:

1. **Table Size**: 
   - Small (128 entries)
   - Medium (512 entries)
   - Large (2048 entries)
   - Effect: Larger tables reduce capacity misses but increase hardware cost

2. **Replacement Policy**:
   - Random
   - LRU
   - FIFO
   - Effect: Better replacement can improve prediction accuracy

3. **Synchronization Strategy**:
   - Full synchronization (wait for all predicted dependencies)
   - Selective synchronization (confidence-based)
   - No synchronization (baseline)
   - Effect: Trade-off between speculation and correctness

### Baseline Comparisons
1. **No Prediction**: Aggressive speculation without dependence tracking
2. **Perfect Prediction**: Oracle knowing all true dependencies
3. **Store-Set Predictor**: Alternative memory dependence prediction scheme
4. **MDPT Only**: Prediction without synchronization
5. **MDPT + MDST**: Full proposed mechanism

## Hardware Cost Analysis

### MDPT Hardware Cost
- **Storage**: For 512 entries with 32-bit PCs
  - Per entry: 1 (valid) + 32 (load PC) + 32 (store PC) = 65 bits
  - Total: 512 × 65 = 33,280 bits ≈ 4.1 KB

### MDST Hardware Cost
- **Storage**: For 512 entries
  - Per entry: ~96 bits (PCs + IDs + state)
  - Total: 512 × 96 = 49,152 bits ≈ 6 KB

### Total Hardware Overhead
- **Combined**: ~10 KB for 512-entry configuration
- **Percentage of L1 Cache**: ~15-30% (relative to 32-64KB L1)
- **Conclusion**: Reasonable overhead for performance gains

## Summary

The configuration section establishes:
1. Detailed processor and memory system parameters for reproducible experiments
2. MDPT and MDST structure and sizing for practical implementation
3. Benchmark selection covering diverse memory access patterns
4. Comprehensive metrics to evaluate both performance and accuracy
5. Systematic variation of configuration parameters to understand trade-offs

This rigorous experimental setup enables thorough evaluation of MDPT and MDST mechanisms for improving load/store performance in out-of-order pipelines.
