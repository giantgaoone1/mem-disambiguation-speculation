"""
Load-Store Queue (LSQ) Implementation for Memory Disambiguation

The LSQ tracks all in-flight memory operations and enables:
- Memory dependency checking
- Speculation validation
- Store-to-load forwarding
- Memory ordering enforcement
"""

from enum import Enum
from typing import Optional, List, Tuple


class MemOpType(Enum):
    """Memory operation type"""
    LOAD = 1
    STORE = 2
    ATOMIC = 3


class LSQEntry:
    """
    Load-Store Queue Entry
    
    Tracks a single memory operation with its metadata
    """
    
    def __init__(self, seq_num: int, pc: int, op_type: MemOpType, size: int):
        self.seq_num = seq_num          # Sequence number for ordering
        self.pc = pc                    # Program counter
        self.op_type = op_type          # Load, Store, or Atomic
        self.size = size                # Operation size in bytes
        
        self.address: Optional[int] = None      # Memory address (when computed)
        self.data: Optional[int] = None         # Data (for stores)
        self.address_valid = False              # Address has been computed
        self.data_valid = False                 # Data is ready (for stores)
        self.speculative = False                # Operation is speculative
        self.completed = False                  # Operation completed
        self.committed = False                  # Operation committed
        
    def __repr__(self):
        addr_str = f"0x{self.address:08x}" if self.address_valid else "unknown"
        return (f"LSQEntry(seq={self.seq_num}, pc=0x{self.pc:08x}, "
                f"type={self.op_type.name}, addr={addr_str}, "
                f"spec={self.speculative}, comp={self.completed})")


class LoadStoreQueue:
    """
    Load-Store Queue for tracking in-flight memory operations
    
    Provides:
    - Memory disambiguation
    - Store-to-load forwarding
    - Speculation tracking
    - Memory ordering enforcement
    """
    
    def __init__(self, capacity: int = 32):
        self.capacity = capacity
        self.entries: List[Optional[LSQEntry]] = [None] * capacity
        self.head = 0  # Oldest entry (for commit)
        self.tail = 0  # Next free entry (for allocation)
        self.size = 0  # Number of valid entries
        
    def is_full(self) -> bool:
        """Check if LSQ is full"""
        return self.size >= self.capacity
    
    def is_empty(self) -> bool:
        """Check if LSQ is empty"""
        return self.size == 0
    
    def allocate(self, seq_num: int, pc: int, op_type: MemOpType, 
                 size: int) -> Optional[int]:
        """
        Allocate a new LSQ entry
        
        Returns: LSQ index if successful, None if full
        """
        if self.is_full():
            return None
        
        entry = LSQEntry(seq_num, pc, op_type, size)
        idx = self.tail
        self.entries[idx] = entry
        
        self.tail = (self.tail + 1) % self.capacity
        self.size += 1
        
        return idx
    
    def update_address(self, idx: int, address: int):
        """Update address for an LSQ entry"""
        if 0 <= idx < self.capacity and self.entries[idx]:
            self.entries[idx].address = address
            self.entries[idx].address_valid = True
    
    def update_data(self, idx: int, data: int):
        """Update data for a store entry"""
        if 0 <= idx < self.capacity and self.entries[idx]:
            entry = self.entries[idx]
            if entry.op_type == MemOpType.STORE:
                entry.data = data
                entry.data_valid = True
    
    def check_dependency(self, load_idx: int) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Check if a load has a dependency on earlier stores
        
        Returns: (has_conflict, forwarding_idx, forwarding_data)
        - has_conflict: True if there's an address conflict
        - forwarding_idx: Index of store to forward from (if applicable)
        - forwarding_data: Data to forward (if available)
        """
        load_entry = self.entries[load_idx]
        if not load_entry or not load_entry.address_valid:
            return False, None, None
        
        load_addr = load_entry.address
        load_size = load_entry.size
        
        # Search earlier stores (from head to load position)
        idx = self.head
        latest_conflict_idx = None
        can_forward = False
        forward_data = None
        
        while idx != load_idx:
            entry = self.entries[idx]
            if entry and entry.op_type in [MemOpType.STORE, MemOpType.ATOMIC]:
                if entry.address_valid:
                    # Check for address overlap
                    store_addr = entry.address
                    store_size = entry.size
                    
                    # Simple overlap check
                    if self._addresses_overlap(store_addr, store_size, 
                                               load_addr, load_size):
                        latest_conflict_idx = idx
                        # Check if we can forward
                        if (entry.data_valid and 
                            store_addr == load_addr and 
                            store_size >= load_size):
                            can_forward = True
                            forward_data = entry.data
                        else:
                            can_forward = False
                            forward_data = None
                else:
                    # Store with unknown address - potential conflict
                    latest_conflict_idx = idx
                    can_forward = False
                    forward_data = None
            
            idx = (idx + 1) % self.capacity
        
        has_conflict = latest_conflict_idx is not None
        return has_conflict, latest_conflict_idx if can_forward else None, forward_data
    
    def _addresses_overlap(self, addr1: int, size1: int, 
                          addr2: int, size2: int) -> bool:
        """Check if two memory regions overlap"""
        end1 = addr1 + size1
        end2 = addr2 + size2
        return not (end1 <= addr2 or end2 <= addr1)
    
    def mark_speculative(self, idx: int):
        """Mark an operation as speculative"""
        if 0 <= idx < self.capacity and self.entries[idx]:
            self.entries[idx].speculative = True
    
    def mark_completed(self, idx: int):
        """Mark an operation as completed"""
        if 0 <= idx < self.capacity and self.entries[idx]:
            self.entries[idx].completed = True
    
    def commit_head(self) -> Optional[LSQEntry]:
        """
        Commit the oldest entry in the LSQ
        
        Returns: The committed entry, or None if empty
        """
        if self.is_empty():
            return None
        
        entry = self.entries[self.head]
        if entry:
            entry.committed = True
        
        # Free the entry
        self.entries[self.head] = None
        self.head = (self.head + 1) % self.capacity
        self.size -= 1
        
        return entry
    
    def squash_from(self, seq_num: int):
        """
        Squash all entries from seq_num onwards (for speculation recovery)
        """
        idx = self.head
        for _ in range(self.size):
            entry = self.entries[idx]
            if entry and entry.seq_num >= seq_num:
                # Remove this entry and all after it
                while idx != self.tail:
                    if self.entries[idx]:
                        self.entries[idx] = None
                        self.size -= 1
                    idx = (idx + 1) % self.capacity
                self.tail = idx
                return
            idx = (idx + 1) % self.capacity
    
    def get_store_count(self) -> int:
        """Count number of stores in the LSQ"""
        count = 0
        idx = self.head
        for _ in range(self.size):
            entry = self.entries[idx]
            if entry and entry.op_type == MemOpType.STORE:
                count += 1
            idx = (idx + 1) % self.capacity
        return count
    
    def get_load_count(self) -> int:
        """Count number of loads in the LSQ"""
        count = 0
        idx = self.head
        for _ in range(self.size):
            entry = self.entries[idx]
            if entry and entry.op_type == MemOpType.LOAD:
                count += 1
            idx = (idx + 1) % self.capacity
        return count
    
    def __repr__(self):
        return (f"LSQ(capacity={self.capacity}, size={self.size}, "
                f"loads={self.get_load_count()}, stores={self.get_store_count()})")


if __name__ == "__main__":
    # Simple test
    print("Testing Load-Store Queue...")
    
    lsq = LoadStoreQueue(capacity=8)
    print(f"Created: {lsq}")
    
    # Allocate a store
    st_idx = lsq.allocate(seq_num=1, pc=0x1000, op_type=MemOpType.STORE, size=4)
    print(f"Allocated store at index {st_idx}")
    lsq.update_address(st_idx, 0x2000)
    lsq.update_data(st_idx, 0xDEADBEEF)
    
    # Allocate a load
    ld_idx = lsq.allocate(seq_num=2, pc=0x1004, op_type=MemOpType.LOAD, size=4)
    print(f"Allocated load at index {ld_idx}")
    lsq.update_address(ld_idx, 0x2000)
    
    # Check dependency
    has_dep, fwd_idx, fwd_data = lsq.check_dependency(ld_idx)
    print(f"Dependency check: has_dep={has_dep}, fwd_idx={fwd_idx}, fwd_data=0x{fwd_data:08x}" if fwd_data else f"Dependency check: has_dep={has_dep}")
    
    print(f"\nFinal state: {lsq}")
