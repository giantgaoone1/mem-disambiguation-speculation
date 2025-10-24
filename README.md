# mem-disambiguation-speculation

Analysis of architecture design for memory disambiguation speculation and synchronization in out-of-order (3O) pipeline.

## Overview

This repository explores the Memory Dependence Prediction Table (MDPT) and Memory Dependence Synchronization Table (MDST) mechanisms for improving load/store performance in out-of-order execution pipelines, based on the seminal paper "Dynamic Speculation and Synchronization of Data Dependences" (Moshovos et al., ISCA 1997).

## Documentation

### Experimental Evaluation
- **[Experimental Evaluation Overview](experimental-evaluation-overview.md)** - Executive summary and key findings
- **[Section 5.2: Configuration](section-5.2-configuration.md)** - Detailed experimental setup, processor parameters, table configurations, and benchmarks
- **[Section 5.3: Dynamic Behavior](section-5.3-dynamic-behavior.md)** - Analysis of dynamic memory dependence patterns, learning process, and performance results

## Key Findings

- **20-35% IPC improvement** across SPEC benchmarks
- **75-85% reduction** in memory order violations
- **Only 4-12% of loads** require synchronization (low overhead)
- **512-entry tables** provide optimal performance/cost trade-off (~10KB hardware)
- **70-90% of violations** involve predictable, repeating load-store pairs

## Performance Summary

| Benchmark | Type | Dependence Pattern | IPC Gain |
|-----------|------|-------------------|----------|
| compress | Integer | Moderate, predictable | +18% |
| gcc | Integer | Complex, irregular | +12% |
| swim | FP | Regular, loop-based | +28% |
| tomcatv | FP | Regular, scientific | +25% |

## Mechanisms

### MDPT (Memory Dependence Prediction Table)
- Learns load-store pairs that cause memory order violations
- Predicts future dependencies based on instruction PC
- Typical configuration: 512 entries, random replacement

### MDST (Memory Dependence Synchronization Table)
- Enforces synchronization for predicted dependencies
- Delays dependent loads until stores complete
- Prevents violations with minimal overhead

## References

Moshovos, A., Breach, S. E., Vijaykumar, T. N., & Sohi, G. S. (1997). "Dynamic Speculation and Synchronization of Data Dependences." *Proceedings of ISCA*, 181-193.
