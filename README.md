# Memory Disambiguation Speculation

Comprehensive analysis of the architecture design for memory disambiguation speculation and synchronization in out-of-order (OOO) pipelines.

## Overview

This repository contains detailed analysis and documentation of the **Dynamic Speculation and Synchronization of Data Dependences** paper by Andreas Moshovos et al. (ISCA 1997).

## Documentation

### ⭐ [THREE_QUESTIONS.md](THREE_QUESTIONS.md) - **START HERE**
Direct, detailed answers to the three specific questions:
1. MDPT dependence distance: LDID/STID vs LDPC/STPC?
2. MDST F/E and V entries: What are their functions?
3. Section 5 evaluation: Core methodology and results?

### 📄 [PAPER_ANALYSIS.md](PAPER_ANALYSIS.md)
Comprehensive analysis answering three key questions about the paper:
1. Does MDPT dependence distance (DIST) use LDID/STID or LDPC/STPC?
2. What are the functions of F/E and V entries in MDST?
3. What are the core methodology and evaluation results from Section 5?

### 📊 [VISUALIZATIONS.md](VISUALIZATIONS.md)
Visual diagrams and ASCII art representations of:
- MDPT and MDST architecture
- Entry structures and bit layouts
- State transition diagrams
- Execution timelines
- Performance comparisons
- Hardware cost analysis

### 🔍 [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
Quick reference guide with:
- Direct answers to the three questions
- Key terminology definitions
- Core concepts at a glance
- Practical examples
- Implementation checklist
- Common misconceptions clarified

## Quick Answers

### Q1: DIST uses LDID/STID or LDPC/STPC?
**Answer: LDID/STID (dynamic instance IDs)**
- DIST measures dynamic instruction separation, not static code distance
- Essential for handling loops and varying execution patterns

### Q2: F/E vs V entries in MDST?
**Answer: Different roles**
- **V (Valid)**: Entry management - is this slot active?
- **F/E (Full/Empty)**: Synchronization - is the data ready?

### Q3: Section 5 Evaluation Summary?
**Answer: Strong results**
- **15-30% average speedup** over conservative scheduling
- **20KB hardware cost** (very modest)
- **Best on regular workloads** (arrays, loops)

## Paper Reference

**Title:** Dynamic Speculation and Synchronization of Data Dependences  
**Authors:** Andreas Moshovos, Scott E. Breach, T. N. Vijaykumar, Gurindar S. Sohi  
**Conference:** ISCA 1997  
**URL:** [Paper PDF](https://www.eecg.utoronto.ca/~moshovos/research/isca.data-dep-spec.pdf)

## Key Contributions

1. **Memory Dependence Prediction Table (MDPT)**: Predicts load-store dependences
2. **Memory Dependence Synchronization Table (MDST)**: Provides safe synchronization
3. **Dynamic instance tracking**: Uses LDID/STID for accurate runtime tracking
4. **Practical hardware**: Only ~20KB storage + ~3500 gates required

## Usage

Start with [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for a high-level overview, then dive into [PAPER_ANALYSIS.md](PAPER_ANALYSIS.md) for detailed explanations. Refer to [VISUALIZATIONS.md](VISUALIZATIONS.md) for diagrams and visual aids.
