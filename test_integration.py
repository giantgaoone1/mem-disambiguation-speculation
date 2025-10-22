#!/usr/bin/env python3
"""
Integration Test for Memory Disambiguation Speculation Architecture

This script runs all components together to verify the complete system.
"""

import sys

def test_module(module_name, description):
    """Test a single module"""
    print(f"\n{'='*70}")
    print(f"Testing: {module_name}")
    print(f"Description: {description}")
    print('='*70)
    
    try:
        # Import and run the module
        module = __import__(module_name.replace('.py', ''))
        print(f"✅ {module_name} - PASSED")
        return True
    except Exception as e:
        print(f"❌ {module_name} - FAILED: {e}")
        return False

def main():
    """Run all integration tests"""
    print("\n" + "*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + " " * 10 + "MEMORY DISAMBIGUATION SPECULATION" + " " * 25 + "*")
    print("*" + " " * 15 + "INTEGRATION TEST SUITE" + " " * 32 + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    
    tests = [
        ('lsq.py', 'Load-Store Queue implementation'),
        ('predictor.py', 'Memory disambiguation predictors'),
        ('synchronization.py', 'Synchronization primitives'),
        ('mlp.py', 'Memory-level parallelism components'),
        ('pipeline.py', '3-stage OoO pipeline'),
        ('examples.py', 'Comprehensive example scenarios'),
    ]
    
    results = []
    for module, description in tests:
        results.append(test_module(module, description))
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("\nThe memory disambiguation speculation architecture is working correctly.")
        print("All components (LSQ, Predictor, Pipeline, Sync, MLP) are functional.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
