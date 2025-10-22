"""
Memory-Level Parallelism (MLP) Support

Implements structures and mechanisms to maximize concurrent
memory operations while maintaining correctness.
"""

from enum import Enum
from typing import Optional, List, Dict, Set


class MSHRState(Enum):
    """MSHR entry state"""
    INVALID = 0
    PENDING = 1
    COMPLETED = 2


class MSHREntry:
    """
    Miss Status Handling Register (MSHR) Entry
    
    Tracks an outstanding cache miss and associated requests
    """
    
    def __init__(self, address: int, line_address: int):
        self.address = address                  # Original request address
        self.line_address = line_address        # Cache line address
        self.state = MSHRState.PENDING
        
        # Waiting instructions
        self.waiting_loads: List[int] = []      # Sequence numbers of waiting loads
        self.waiting_stores: List[int] = []     # Sequence numbers of waiting stores
        
        # Request metadata
        self.is_prefetch = False
        self.issue_cycle = 0
        self.complete_cycle = 0
        
    def add_waiter(self, seq_num: int, is_store: bool = False):
        """Add an instruction waiting for this miss"""
        if is_store:
            self.waiting_stores.append(seq_num)
        else:
            self.waiting_loads.append(seq_num)
    
    def get_latency(self) -> int:
        """Get miss latency in cycles"""
        if self.state == MSHRState.COMPLETED:
            return self.complete_cycle - self.issue_cycle
        return -1
    
    def __repr__(self):
        return (f"MSHR(addr=0x{self.line_address:x}, state={self.state.name}, "
                f"waiters={len(self.waiting_loads) + len(self.waiting_stores)})")


class MSHRFile:
    """
    MSHR File for tracking multiple outstanding cache misses
    
    Enables:
    - Hit-under-miss: New hits while miss is pending
    - Miss-under-miss: Multiple concurrent misses
    - Request merging: Combine requests to same line
    """
    
    def __init__(self, num_entries: int = 8, line_size: int = 64):
        self.num_entries = num_entries
        self.line_size = line_size
        self.entries: List[Optional[MSHREntry]] = [None] * num_entries
        
        # Statistics
        self.total_misses = 0
        self.merged_requests = 0
        self.concurrent_misses_peak = 0
        
    def _get_line_address(self, address: int) -> int:
        """Get cache line address"""
        return (address // self.line_size) * self.line_size
    
    def is_full(self) -> bool:
        """Check if all MSHR entries are occupied"""
        return all(entry is not None for entry in self.entries)
    
    def lookup(self, address: int) -> Optional[int]:
        """
        Look up MSHR for address
        
        Returns: MSHR index if found, None otherwise
        """
        line_addr = self._get_line_address(address)
        for i, entry in enumerate(self.entries):
            if entry and entry.line_address == line_addr:
                return i
        return None
    
    def allocate(self, address: int, seq_num: int, is_store: bool = False,
                 is_prefetch: bool = False, cycle: int = 0) -> Optional[int]:
        """
        Allocate MSHR entry for a new miss
        
        Returns: MSHR index if allocated, None if full
        """
        line_addr = self._get_line_address(address)
        
        # Check if already tracking this line
        idx = self.lookup(address)
        if idx is not None:
            # Merge request
            self.entries[idx].add_waiter(seq_num, is_store)
            self.merged_requests += 1
            return idx
        
        # Find free entry
        for i, entry in enumerate(self.entries):
            if entry is None:
                new_entry = MSHREntry(address, line_addr)
                new_entry.add_waiter(seq_num, is_store)
                new_entry.is_prefetch = is_prefetch
                new_entry.issue_cycle = cycle
                self.entries[i] = new_entry
                
                self.total_misses += 1
                
                # Update peak concurrent misses
                active = sum(1 for e in self.entries if e is not None)
                self.concurrent_misses_peak = max(self.concurrent_misses_peak, active)
                
                return i
        
        return None
    
    def complete(self, idx: int, cycle: int = 0) -> Optional[MSHREntry]:
        """
        Mark MSHR entry as completed
        
        Returns: The completed entry
        """
        if 0 <= idx < self.num_entries and self.entries[idx]:
            entry = self.entries[idx]
            entry.state = MSHRState.COMPLETED
            entry.complete_cycle = cycle
            return entry
        return None
    
    def free(self, idx: int):
        """Free an MSHR entry"""
        if 0 <= idx < self.num_entries:
            self.entries[idx] = None
    
    def get_active_count(self) -> int:
        """Get number of active MSHR entries"""
        return sum(1 for e in self.entries if e is not None)
    
    def get_stats(self) -> Dict[str, int]:
        """Get MSHR statistics"""
        return {
            'total_misses': self.total_misses,
            'merged_requests': self.merged_requests,
            'peak_concurrent': self.concurrent_misses_peak,
            'active_entries': self.get_active_count()
        }
    
    def __repr__(self):
        active = self.get_active_count()
        return f"MSHRFile(entries={self.num_entries}, active={active})"


class BankConflictDetector:
    """
    Cache Bank Conflict Detection
    
    Modern caches are divided into banks for parallel access.
    This class detects and handles bank conflicts.
    """
    
    def __init__(self, num_banks: int = 4, line_size: int = 64):
        self.num_banks = num_banks
        self.line_size = line_size
        
        # Track which bank is busy
        self.bank_busy: List[bool] = [False] * num_banks
        self.bank_ready_cycle: List[int] = [0] * num_banks
        
        # Statistics
        self.total_accesses = 0
        self.bank_conflicts = 0
        
    def _get_bank(self, address: int) -> int:
        """Determine which bank an address maps to"""
        line_addr = (address // self.line_size)
        return line_addr % self.num_banks
    
    def can_access(self, address: int, current_cycle: int) -> bool:
        """Check if address can be accessed (no bank conflict)"""
        self.total_accesses += 1
        bank = self._get_bank(address)
        
        if self.bank_busy[bank] and self.bank_ready_cycle[bank] > current_cycle:
            self.bank_conflicts += 1
            return False
        
        return True
    
    def reserve_bank(self, address: int, current_cycle: int, latency: int = 1):
        """Reserve a bank for access"""
        bank = self._get_bank(address)
        self.bank_busy[bank] = True
        self.bank_ready_cycle[bank] = current_cycle + latency
    
    def update_cycle(self, current_cycle: int):
        """Update bank availability based on current cycle"""
        for i in range(self.num_banks):
            if self.bank_ready_cycle[i] <= current_cycle:
                self.bank_busy[i] = False
    
    def get_conflict_rate(self) -> float:
        """Get bank conflict rate"""
        if self.total_accesses == 0:
            return 0.0
        return (self.bank_conflicts / self.total_accesses) * 100
    
    def __repr__(self):
        busy_count = sum(self.bank_busy)
        conflict_rate = self.get_conflict_rate()
        return (f"BankConflict(banks={self.num_banks}, busy={busy_count}, "
                f"conflict_rate={conflict_rate:.1f}%)")


class PrefetchQueue:
    """
    Hardware Prefetch Queue
    
    Separates prefetch requests from demand requests to avoid
    interference and enable better memory-level parallelism.
    """
    
    def __init__(self, capacity: int = 8):
        self.capacity = capacity
        self.queue: List[Dict] = []
        
        # Statistics
        self.total_prefetches = 0
        self.useful_prefetches = 0
        self.late_prefetches = 0
        self.dropped_prefetches = 0
        
    def is_full(self) -> bool:
        """Check if prefetch queue is full"""
        return len(self.queue) >= self.capacity
    
    def enqueue(self, address: int, confidence: float = 1.0, cycle: int = 0) -> bool:
        """
        Enqueue a prefetch request
        
        Returns: True if enqueued successfully
        """
        if self.is_full():
            self.dropped_prefetches += 1
            return False
        
        entry = {
            'address': address,
            'confidence': confidence,
            'issue_cycle': cycle,
            'consumed': False
        }
        self.queue.append(entry)
        self.total_prefetches += 1
        return True
    
    def check_hit(self, address: int) -> bool:
        """
        Check if a demand request hits in prefetch queue
        
        Returns: True if hit (prefetch was useful)
        """
        for entry in self.queue:
            if entry['address'] == address:
                if not entry['consumed']:
                    entry['consumed'] = True
                    self.useful_prefetches += 1
                    return True
        return False
    
    def dequeue(self) -> Optional[Dict]:
        """Dequeue oldest prefetch request"""
        if self.queue:
            return self.queue.pop(0)
        return None
    
    def get_accuracy(self) -> float:
        """Get prefetch accuracy"""
        if self.total_prefetches == 0:
            return 0.0
        return (self.useful_prefetches / self.total_prefetches) * 100
    
    def __repr__(self):
        accuracy = self.get_accuracy()
        return (f"PrefetchQueue(size={len(self.queue)}/{self.capacity}, "
                f"accuracy={accuracy:.1f}%)")


class MLPTracker:
    """
    Memory-Level Parallelism Tracker
    
    Monitors and reports MLP metrics for performance analysis
    """
    
    def __init__(self):
        self.cycle_outstanding_misses: List[int] = []
        self.total_cycles = 0
        
    def record_cycle(self, outstanding_misses: int):
        """Record number of outstanding misses for this cycle"""
        self.cycle_outstanding_misses.append(outstanding_misses)
        self.total_cycles += 1
    
    def get_average_mlp(self) -> float:
        """Get average memory-level parallelism"""
        if not self.cycle_outstanding_misses:
            return 0.0
        
        # Average outstanding misses across all cycles
        total = sum(self.cycle_outstanding_misses)
        return total / len(self.cycle_outstanding_misses)
    
    def get_peak_mlp(self) -> int:
        """Get peak memory-level parallelism"""
        if not self.cycle_outstanding_misses:
            return 0
        return max(self.cycle_outstanding_misses)
    
    def get_utilization(self) -> float:
        """Get MLP utilization (% of cycles with outstanding misses)"""
        if not self.cycle_outstanding_misses:
            return 0.0
        
        cycles_with_misses = sum(1 for x in self.cycle_outstanding_misses if x > 0)
        return (cycles_with_misses / len(self.cycle_outstanding_misses)) * 100
    
    def __repr__(self):
        avg_mlp = self.get_average_mlp()
        peak_mlp = self.get_peak_mlp()
        util = self.get_utilization()
        return (f"MLPTracker(avg={avg_mlp:.2f}, peak={peak_mlp}, "
                f"util={util:.1f}%)")


if __name__ == "__main__":
    print("Testing Memory-Level Parallelism Components...\n")
    
    # Test MSHR File
    print("1. MSHR File:")
    mshr = MSHRFile(num_entries=4, line_size=64)
    print(f"   Created: {mshr}")
    
    # Allocate some misses
    idx1 = mshr.allocate(address=0x1000, seq_num=1, cycle=10)
    idx2 = mshr.allocate(address=0x2000, seq_num=2, cycle=11)
    idx3 = mshr.allocate(address=0x1040, seq_num=3, cycle=12)  # Same line as 0x1000
    
    print(f"   After allocations: {mshr}")
    print(f"   Stats: {mshr.get_stats()}")
    
    # Test Bank Conflict Detector
    print("\n2. Bank Conflict Detector:")
    banks = BankConflictDetector(num_banks=4, line_size=64)
    print(f"   Created: {banks}")
    
    # Simulate accesses
    can_access = banks.can_access(0x1000, current_cycle=0)
    print(f"   Can access 0x1000 at cycle 0: {can_access}")
    banks.reserve_bank(0x1000, current_cycle=0, latency=2)
    
    can_access = banks.can_access(0x1040, current_cycle=1)  # Same bank
    print(f"   Can access 0x1040 at cycle 1: {can_access}")
    
    banks.update_cycle(2)
    can_access = banks.can_access(0x1040, current_cycle=2)
    print(f"   Can access 0x1040 at cycle 2: {can_access}")
    print(f"   {banks}")
    
    # Test Prefetch Queue
    print("\n3. Prefetch Queue:")
    pf = PrefetchQueue(capacity=4)
    print(f"   Created: {pf}")
    
    pf.enqueue(address=0x3000, confidence=0.9, cycle=0)
    pf.enqueue(address=0x3040, confidence=0.8, cycle=1)
    print(f"   After 2 prefetches: {pf}")
    
    hit = pf.check_hit(0x3000)
    print(f"   Demand for 0x3000 (hit={hit})")
    print(f"   {pf}")
    
    # Test MLP Tracker
    print("\n4. MLP Tracker:")
    mlp = MLPTracker()
    print(f"   Created: {mlp}")
    
    # Simulate some cycles
    for cycle in range(10):
        outstanding = min(cycle, 3)  # Ramp up to 3 concurrent misses
        mlp.record_cycle(outstanding)
    
    print(f"   {mlp}")
