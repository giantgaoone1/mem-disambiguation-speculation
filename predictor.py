"""
Memory Disambiguation Predictor

Implements Store Set predictor to learn memory dependency patterns
and improve speculation accuracy.

Based on "Memory Dependence Prediction using Store Sets" by Chrysos & Emer
"""

from typing import Dict, Optional, Set, Tuple
from collections import defaultdict


class StoreSetPredictor:
    """
    Store Set based memory disambiguation predictor
    
    Uses two tables:
    - SSIT (Store Set ID Table): Maps PCs to store sets
    - LFST (Last Fetched Store Table): Tracks last store in each set
    
    Prediction policy:
    - If load is in a store set, wait for stores in that set
    - Otherwise, speculate freely
    """
    
    def __init__(self, ssit_size: int = 256, max_store_sets: int = 64):
        self.ssit_size = ssit_size
        self.max_store_sets = max_store_sets
        
        # Store Set ID Table: PC -> Store Set ID
        self.ssit: Dict[int, Optional[int]] = {}
        
        # Last Fetched Store Table: Store Set ID -> Store sequence number
        self.lfst: Dict[int, int] = {}
        
        # Confidence counters: PC -> confidence (2-bit saturating)
        self.confidence: Dict[int, int] = defaultdict(lambda: 2)  # Start confident
        
        # Store set allocation
        self.next_store_set_id = 0
        self.free_store_sets: Set[int] = set(range(max_store_sets))
        
        # Statistics
        self.predictions = 0
        self.correct_predictions = 0
        self.violations = 0
        
    def _get_ssit_index(self, pc: int) -> int:
        """Hash PC to SSIT index"""
        return (pc >> 2) % self.ssit_size
    
    def predict_load(self, load_pc: int) -> Tuple[bool, Optional[int]]:
        """
        Predict if a load can execute speculatively
        
        Returns: (can_speculate, wait_for_seq_num)
        - can_speculate: True if load should execute speculatively
        - wait_for_seq_num: Sequence number to wait for (if applicable)
        """
        self.predictions += 1
        
        ssit_idx = self._get_ssit_index(load_pc)
        store_set_id = self.ssit.get(ssit_idx)
        
        # Check confidence
        conf = self.confidence[load_pc]
        
        if store_set_id is None or conf >= 2:
            # Not in a store set or high confidence -> speculate
            return True, None
        
        # In a store set with low confidence
        # Check if there's a pending store in the same set
        if store_set_id in self.lfst:
            last_store_seq = self.lfst[store_set_id]
            # Wait for that store
            return False, last_store_seq
        
        # No pending store in the set -> can speculate
        return True, None
    
    def register_store(self, store_pc: int, seq_num: int):
        """
        Register a store instruction
        
        Updates LFST to track this store as the latest in its set
        """
        ssit_idx = self._get_ssit_index(store_pc)
        store_set_id = self.ssit.get(ssit_idx)
        
        if store_set_id is not None:
            # Update last fetched store in this set
            self.lfst[store_set_id] = seq_num
    
    def clear_store(self, store_pc: int):
        """
        Clear a store from LFST when it commits
        """
        ssit_idx = self._get_ssit_index(store_pc)
        store_set_id = self.ssit.get(ssit_idx)
        
        if store_set_id is not None and store_set_id in self.lfst:
            del self.lfst[store_set_id]
    
    def report_violation(self, load_pc: int, store_pc: int):
        """
        Report a memory ordering violation
        
        Creates or merges store sets for the conflicting load and store
        """
        self.violations += 1
        
        load_idx = self._get_ssit_index(load_pc)
        store_idx = self._get_ssit_index(store_pc)
        
        load_set = self.ssit.get(load_idx)
        store_set = self.ssit.get(store_idx)
        
        if load_set is None and store_set is None:
            # Neither in a set -> create new set
            new_set_id = self._allocate_store_set()
            if new_set_id is not None:
                self.ssit[load_idx] = new_set_id
                self.ssit[store_idx] = new_set_id
        elif load_set is None:
            # Only store in a set -> add load to it
            self.ssit[load_idx] = store_set
        elif store_set is None:
            # Only load in a set -> add store to it
            self.ssit[store_idx] = load_set
        else:
            # Both in sets -> merge sets
            if load_set != store_set:
                # Replace all occurrences of store_set with load_set
                for idx in list(self.ssit.keys()):
                    if self.ssit[idx] == store_set:
                        self.ssit[idx] = load_set
                # Free the store_set
                self.free_store_sets.add(store_set)
        
        # Reduce confidence for this load
        if self.confidence[load_pc] > 0:
            self.confidence[load_pc] -= 1
    
    def report_correct_speculation(self, load_pc: int):
        """
        Report that a speculative load was correct
        
        Increases confidence in future speculation
        """
        self.correct_predictions += 1
        
        # Increase confidence (saturate at 3)
        if self.confidence[load_pc] < 3:
            self.confidence[load_pc] += 1
    
    def _allocate_store_set(self) -> Optional[int]:
        """Allocate a new store set ID"""
        if self.free_store_sets:
            return self.free_store_sets.pop()
        
        # No free sets -> evict one (simple LRU approximation)
        # Find a set not currently in LFST
        for set_id in range(self.max_store_sets):
            if set_id not in self.lfst:
                # Remove from SSIT
                for idx in list(self.ssit.keys()):
                    if self.ssit[idx] == set_id:
                        del self.ssit[idx]
                return set_id
        
        # All sets active -> can't allocate
        return None
    
    def get_stats(self) -> Dict[str, any]:
        """Get predictor statistics"""
        accuracy = (self.correct_predictions / self.predictions * 100 
                   if self.predictions > 0 else 0)
        return {
            'predictions': self.predictions,
            'correct': self.correct_predictions,
            'violations': self.violations,
            'accuracy': accuracy,
            'active_sets': len([v for v in self.ssit.values() if v is not None]),
            'pending_stores': len(self.lfst)
        }
    
    def reset_stats(self):
        """Reset statistics counters"""
        self.predictions = 0
        self.correct_predictions = 0
        self.violations = 0
    
    def __repr__(self):
        stats = self.get_stats()
        return (f"StoreSetPredictor(predictions={stats['predictions']}, "
                f"violations={stats['violations']}, "
                f"accuracy={stats['accuracy']:.1f}%)")


class SimplePredictor:
    """
    Simple memory disambiguation predictor
    
    Uses a per-PC 2-bit saturating counter:
    - 0, 1: Don't speculate (wait for earlier stores)
    - 2, 3: Speculate freely
    """
    
    def __init__(self, table_size: int = 256):
        self.table_size = table_size
        # Counter table: PC index -> 2-bit counter
        self.counters: Dict[int, int] = defaultdict(lambda: 3)  # Start optimistic
        
        # Statistics
        self.predictions = 0
        self.violations = 0
    
    def _get_index(self, pc: int) -> int:
        """Hash PC to table index"""
        return (pc >> 2) % self.table_size
    
    def should_speculate(self, load_pc: int) -> bool:
        """Predict if a load should speculate"""
        self.predictions += 1
        idx = self._get_index(load_pc)
        return self.counters[idx] >= 2
    
    def report_violation(self, load_pc: int):
        """Report a memory ordering violation"""
        self.violations += 1
        idx = self._get_index(load_pc)
        # Decrement counter (saturate at 0)
        if self.counters[idx] > 0:
            self.counters[idx] -= 1
    
    def report_correct_speculation(self, load_pc: int):
        """Report a correct speculation"""
        idx = self._get_index(load_pc)
        # Increment counter (saturate at 3)
        if self.counters[idx] < 3:
            self.counters[idx] += 1
    
    def get_stats(self) -> Dict[str, any]:
        """Get predictor statistics"""
        accuracy = ((self.predictions - self.violations) / self.predictions * 100 
                   if self.predictions > 0 else 0)
        return {
            'predictions': self.predictions,
            'violations': self.violations,
            'accuracy': accuracy
        }
    
    def __repr__(self):
        stats = self.get_stats()
        return (f"SimplePredictor(predictions={stats['predictions']}, "
                f"violations={stats['violations']}, "
                f"accuracy={stats['accuracy']:.1f}%)")


if __name__ == "__main__":
    print("Testing Store Set Predictor...")
    
    predictor = StoreSetPredictor()
    
    # Simulate a sequence with a violation
    load_pc = 0x1000
    store_pc = 0x1008
    
    # Initially predict to speculate
    can_spec, wait_seq = predictor.predict_load(load_pc)
    print(f"Initial prediction for load @0x{load_pc:x}: speculate={can_spec}")
    
    # Report violation
    predictor.report_violation(load_pc, store_pc)
    print(f"Reported violation between load @0x{load_pc:x} and store @0x{store_pc:x}")
    
    # Register store
    predictor.register_store(store_pc, seq_num=100)
    
    # Predict again - should now wait
    can_spec, wait_seq = predictor.predict_load(load_pc)
    print(f"After violation, prediction: speculate={can_spec}, wait_for={wait_seq}")
    
    # Clear store
    predictor.clear_store(store_pc)
    
    # Predict again - no pending store
    can_spec, wait_seq = predictor.predict_load(load_pc)
    print(f"After store cleared: speculate={can_spec}")
    
    print(f"\nFinal state: {predictor}")
    print(f"Stats: {predictor.get_stats()}")
