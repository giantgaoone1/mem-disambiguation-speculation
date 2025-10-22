"""
Synchronization Mechanisms for Memory Ordering

Implements memory fences and atomic operations to ensure
correct memory ordering in the out-of-order pipeline.
"""

from enum import Enum
from typing import Optional


class FenceType(Enum):
    """Types of memory fences"""
    LFENCE = 1  # Load fence - prevent loads from moving before fence
    SFENCE = 2  # Store fence - prevent stores from moving before fence
    MFENCE = 3  # Memory fence - prevent all memory ops from moving before fence


class MemoryFence:
    """
    Memory Fence instruction
    
    Enforces memory ordering by preventing younger operations
    from executing before older operations across the fence.
    """
    
    def __init__(self, fence_type: FenceType, seq_num: int):
        self.fence_type = fence_type
        self.seq_num = seq_num
        self.completed = False
    
    def can_complete(self, older_loads_done: bool, older_stores_done: bool) -> bool:
        """
        Check if fence can complete
        
        Returns: True if all required older operations are done
        """
        if self.fence_type == FenceType.LFENCE:
            return older_loads_done
        elif self.fence_type == FenceType.SFENCE:
            return older_stores_done
        elif self.fence_type == FenceType.MFENCE:
            return older_loads_done and older_stores_done
        return False
    
    def blocks_load(self, load_seq_num: int) -> bool:
        """Check if this fence blocks a younger load"""
        if load_seq_num <= self.seq_num:
            return False  # Older or same age
        
        return self.fence_type in [FenceType.LFENCE, FenceType.MFENCE]
    
    def blocks_store(self, store_seq_num: int) -> bool:
        """Check if this fence blocks a younger store"""
        if store_seq_num <= self.seq_num:
            return False  # Older or same age
        
        return self.fence_type in [FenceType.SFENCE, FenceType.MFENCE]
    
    def __repr__(self):
        status = "completed" if self.completed else "pending"
        return f"Fence({self.fence_type.name}, seq={self.seq_num}, {status})"


class AtomicOperation:
    """
    Atomic Read-Modify-Write Operation
    
    Examples: SWAP, CAS (Compare-And-Swap), Fetch-And-Add
    
    Properties:
    - Atomicity: Appears as single operation to other cores
    - Ordering: Acts as both acquire and release fence
    - Exclusivity: No other operation can access same address
    """
    
    def __init__(self, op_type: str, address: int, seq_num: int):
        self.op_type = op_type  # "SWAP", "CAS", "FADD", etc.
        self.address = address
        self.seq_num = seq_num
        
        self.old_value: Optional[int] = None
        self.new_value: Optional[int] = None
        self.expected_value: Optional[int] = None  # For CAS
        
        self.lock_acquired = False
        self.completed = False
        self.success = False
    
    def execute(self, memory_value: int, write_value: int, 
                expected: Optional[int] = None) -> tuple[bool, int]:
        """
        Execute the atomic operation
        
        Returns: (success, result_value)
        """
        self.old_value = memory_value
        
        if self.op_type == "SWAP":
            # Unconditional swap
            self.new_value = write_value
            self.success = True
            return True, memory_value
        
        elif self.op_type == "CAS":
            # Compare-and-swap
            if expected is None:
                return False, memory_value
            
            self.expected_value = expected
            if memory_value == expected:
                self.new_value = write_value
                self.success = True
                return True, memory_value
            else:
                self.success = False
                return False, memory_value
        
        elif self.op_type == "FADD":
            # Fetch-and-add
            self.new_value = memory_value + write_value
            self.success = True
            return True, memory_value
        
        return False, memory_value
    
    def blocks_operation(self, op_address: int, op_seq_num: int) -> bool:
        """
        Check if this atomic blocks another operation
        
        Atomic operations block all operations to the same address
        until they complete.
        """
        if op_seq_num <= self.seq_num:
            return False  # Older operation
        
        if not self.lock_acquired or self.completed:
            return False  # Not holding lock
        
        # Block if addresses match
        return op_address == self.address
    
    def __repr__(self):
        status = "completed" if self.completed else "pending"
        return (f"Atomic({self.op_type}, addr=0x{self.address:x}, "
                f"seq={self.seq_num}, {status})")


class StoreBuffer:
    """
    Store Buffer for holding committed stores before draining to memory
    
    Provides:
    - Store-to-load forwarding
    - Memory ordering
    - Coalescing of stores to same address
    """
    
    def __init__(self, capacity: int = 8):
        self.capacity = capacity
        self.entries: list[Optional[dict]] = []
    
    def is_full(self) -> bool:
        return len(self.entries) >= self.capacity
    
    def add_store(self, address: int, data: int, size: int, seq_num: int):
        """Add a store to the buffer"""
        entry = {
            'address': address,
            'data': data,
            'size': size,
            'seq_num': seq_num,
            'drained': False
        }
        self.entries.append(entry)
    
    def forward_to_load(self, address: int, size: int) -> Optional[int]:
        """
        Forward data to a load if available
        
        Searches buffer from newest to oldest for matching address
        """
        # Search in reverse (newest first)
        for entry in reversed(self.entries):
            if entry['address'] == address and entry['size'] >= size:
                return entry['data']
        
        return None
    
    def drain_oldest(self) -> Optional[dict]:
        """
        Drain oldest store from buffer to memory
        
        Returns: The drained entry, or None if empty
        """
        if not self.entries:
            return None
        
        # Find oldest non-drained entry
        for i, entry in enumerate(self.entries):
            if not entry['drained']:
                entry['drained'] = True
                # Remove from buffer
                return self.entries.pop(i)
        
        return None
    
    def has_pending_stores(self, before_seq_num: Optional[int] = None) -> bool:
        """
        Check if there are pending stores
        
        If before_seq_num is provided, only check stores older than it
        """
        for entry in self.entries:
            if not entry['drained']:
                if before_seq_num is None or entry['seq_num'] < before_seq_num:
                    return True
        return False
    
    def __repr__(self):
        pending = sum(1 for e in self.entries if not e['drained'])
        return f"StoreBuffer(capacity={self.capacity}, pending={pending})"


class LoadLinkStoreConditional:
    """
    Load-Link/Store-Conditional (LL/SC) Support
    
    Provides lock-free synchronization primitive
    """
    
    def __init__(self):
        # Track LL reservations per address
        self.reservations: dict[int, int] = {}  # address -> seq_num
    
    def load_link(self, address: int, seq_num: int) -> None:
        """
        Perform load-link operation
        
        Creates a reservation for this address
        """
        self.reservations[address] = seq_num
    
    def store_conditional(self, address: int, seq_num: int) -> bool:
        """
        Perform store-conditional operation
        
        Returns: True if store succeeds (reservation still valid)
        """
        if address not in self.reservations:
            return False  # No reservation
        
        if self.reservations[address] != seq_num:
            return False  # Reservation invalidated
        
        # Success - clear reservation
        del self.reservations[address]
        return True
    
    def invalidate_reservation(self, address: int):
        """
        Invalidate reservation for address
        
        Called when another core writes to the address
        """
        if address in self.reservations:
            del self.reservations[address]
    
    def __repr__(self):
        return f"LL/SC(active_reservations={len(self.reservations)})"


if __name__ == "__main__":
    print("Testing Synchronization Mechanisms...\n")
    
    # Test Memory Fence
    print("1. Memory Fence:")
    fence = MemoryFence(FenceType.MFENCE, seq_num=10)
    print(f"   Created: {fence}")
    print(f"   Blocks load 15? {fence.blocks_load(15)}")
    print(f"   Blocks store 15? {fence.blocks_store(15)}")
    print(f"   Can complete? {fence.can_complete(True, True)}")
    
    # Test Atomic Operation
    print("\n2. Atomic Operation:")
    atomic = AtomicOperation("CAS", address=0x1000, seq_num=20)
    print(f"   Created: {atomic}")
    
    # Simulate CAS that succeeds
    success, old_val = atomic.execute(memory_value=5, write_value=10, expected=5)
    print(f"   CAS(5->10, expected=5): success={success}, old_value={old_val}")
    
    # Simulate CAS that fails
    atomic2 = AtomicOperation("CAS", address=0x1004, seq_num=21)
    success, old_val = atomic2.execute(memory_value=5, write_value=10, expected=7)
    print(f"   CAS(5->10, expected=7): success={success}, old_value={old_val}")
    
    # Test Store Buffer
    print("\n3. Store Buffer:")
    sb = StoreBuffer(capacity=4)
    print(f"   Created: {sb}")
    sb.add_store(address=0x1000, data=0xDEAD, size=4, seq_num=30)
    sb.add_store(address=0x1004, data=0xBEEF, size=4, seq_num=31)
    print(f"   After 2 stores: {sb}")
    
    fwd_data = sb.forward_to_load(address=0x1000, size=4)
    print(f"   Forward to load at 0x1000: 0x{fwd_data:x}" if fwd_data else "   No forward")
    
    # Test LL/SC
    print("\n4. Load-Link/Store-Conditional:")
    llsc = LoadLinkStoreConditional()
    print(f"   Created: {llsc}")
    
    llsc.load_link(address=0x2000, seq_num=40)
    print(f"   After LL: {llsc}")
    
    success = llsc.store_conditional(address=0x2000, seq_num=40)
    print(f"   SC with matching seq: success={success}")
    
    llsc.load_link(address=0x2000, seq_num=41)
    success = llsc.store_conditional(address=0x2000, seq_num=42)
    print(f"   SC with mismatched seq: success={success}")
