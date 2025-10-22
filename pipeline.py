"""
3-Stage Out-of-Order Pipeline Simulator with Memory Disambiguation

Implements a simplified 3O pipeline:
1. Issue Stage: Instruction dispatch and resource allocation
2. Execute Stage: Functional unit execution and address calculation
3. Commit Stage: In-order retirement and state update
"""

from enum import Enum
from typing import List, Optional, Dict
from lsq import LoadStoreQueue, MemOpType, LSQEntry
from predictor import StoreSetPredictor


class InstructionType(Enum):
    """Instruction types"""
    LOAD = 1
    STORE = 2
    ALU = 3
    BRANCH = 4
    FENCE = 5


class Instruction:
    """Instruction representation"""
    
    def __init__(self, pc: int, instr_type: InstructionType, 
                 dst_reg: Optional[int] = None, 
                 src_regs: Optional[List[int]] = None,
                 immediate: Optional[int] = None):
        self.pc = pc
        self.instr_type = instr_type
        self.dst_reg = dst_reg
        self.src_regs = src_regs or []
        self.immediate = immediate or 0
        
        # Execution state
        self.seq_num: Optional[int] = None
        self.lsq_idx: Optional[int] = None
        self.address: Optional[int] = None
        self.data: Optional[int] = None
        self.issued = False
        self.executed = False
        self.completed = False
        self.committed = False
        self.speculative = False
        
    def __repr__(self):
        return (f"Instr(pc=0x{self.pc:04x}, type={self.instr_type.name}, "
                f"seq={self.seq_num}, spec={self.speculative})")


class ReorderBuffer:
    """
    Reorder Buffer (ROB) for in-order commit
    
    Tracks all in-flight instructions for precise exception handling
    and in-order commit.
    """
    
    def __init__(self, capacity: int = 32):
        self.capacity = capacity
        self.entries: List[Optional[Instruction]] = [None] * capacity
        self.head = 0
        self.tail = 0
        self.size = 0
        
    def is_full(self) -> bool:
        return self.size >= self.capacity
    
    def is_empty(self) -> bool:
        return self.size == 0
    
    def allocate(self, instr: Instruction) -> Optional[int]:
        """Allocate ROB entry for instruction"""
        if self.is_full():
            return None
        
        idx = self.tail
        self.entries[idx] = instr
        self.tail = (self.tail + 1) % self.capacity
        self.size += 1
        
        return idx
    
    def commit_head(self) -> Optional[Instruction]:
        """Commit head instruction if ready"""
        if self.is_empty():
            return None
        
        instr = self.entries[self.head]
        if instr and instr.completed:
            instr.committed = True
            self.entries[self.head] = None
            self.head = (self.head + 1) % self.capacity
            self.size -= 1
            return instr
        
        return None
    
    def squash_from(self, seq_num: int):
        """Squash all instructions from seq_num onwards"""
        idx = self.head
        for _ in range(self.size):
            instr = self.entries[idx]
            if instr and instr.seq_num >= seq_num:
                # Clear from here to tail
                while idx != self.tail:
                    if self.entries[idx]:
                        self.size -= 1
                    self.entries[idx] = None
                    idx = (idx + 1) % self.capacity
                self.tail = idx
                return
            idx = (idx + 1) % self.capacity


class Pipeline:
    """
    3-Stage Out-of-Order Pipeline with Memory Disambiguation
    
    Stages:
    1. Issue: Dispatch instructions, allocate resources
    2. Execute: Calculate addresses, access cache, speculate
    3. Commit: Retire instructions in order, validate speculation
    """
    
    def __init__(self, rob_size: int = 32, lsq_size: int = 16):
        # Core structures
        self.rob = ReorderBuffer(rob_size)
        self.lsq = LoadStoreQueue(lsq_size)
        self.predictor = StoreSetPredictor()
        
        # Register file (simplified)
        self.registers = [0] * 32
        
        # Memory (simplified - byte addressable)
        self.memory: Dict[int, int] = {}
        
        # Pipeline state
        self.next_seq_num = 0
        self.cycle = 0
        self.pc = 0
        
        # Statistics
        self.instructions_committed = 0
        self.loads_executed = 0
        self.stores_executed = 0
        self.speculation_violations = 0
        self.forwarding_events = 0
        
    def issue_instruction(self, instr: Instruction) -> bool:
        """
        Issue Stage: Allocate resources for instruction
        
        Returns: True if issued successfully
        """
        # Check ROB space
        if self.rob.is_full():
            return False
        
        # Allocate ROB entry
        rob_idx = self.rob.allocate(instr)
        if rob_idx is None:
            return False
        
        # Assign sequence number
        instr.seq_num = self.next_seq_num
        self.next_seq_num += 1
        
        # For memory operations, allocate LSQ entry
        if instr.instr_type in [InstructionType.LOAD, InstructionType.STORE]:
            op_type = MemOpType.LOAD if instr.instr_type == InstructionType.LOAD else MemOpType.STORE
            lsq_idx = self.lsq.allocate(instr.seq_num, instr.pc, op_type, size=4)
            
            if lsq_idx is None:
                # LSQ full - can't issue
                # Need to deallocate ROB entry (simplified - just return False)
                return False
            
            instr.lsq_idx = lsq_idx
            
            # For stores, register with predictor
            if instr.instr_type == InstructionType.STORE:
                self.predictor.register_store(instr.pc, instr.seq_num)
        
        instr.issued = True
        return True
    
    def execute_instruction(self, instr: Instruction) -> bool:
        """
        Execute Stage: Perform operation, calculate address, speculate
        
        Returns: True if execution completed
        """
        if not instr.issued or instr.executed:
            return False
        
        if instr.instr_type == InstructionType.ALU:
            # Simple ALU operation
            result = sum(self.registers[r] for r in instr.src_regs) + instr.immediate
            if instr.dst_reg is not None:
                self.registers[instr.dst_reg] = result
            instr.executed = True
            instr.completed = True
            return True
        
        elif instr.instr_type == InstructionType.LOAD:
            return self._execute_load(instr)
        
        elif instr.instr_type == InstructionType.STORE:
            return self._execute_store(instr)
        
        return False
    
    def _execute_load(self, instr: Instruction) -> bool:
        """Execute a load instruction with speculation"""
        # Calculate address
        base_addr = self.registers[instr.src_regs[0]] if instr.src_regs else 0
        instr.address = base_addr + instr.immediate
        
        # Update LSQ
        if instr.lsq_idx is not None:
            self.lsq.update_address(instr.lsq_idx, instr.address)
        
        # Check for dependencies
        has_dep, fwd_idx, fwd_data = self.lsq.check_dependency(instr.lsq_idx)
        
        if fwd_data is not None:
            # Forward from earlier store
            instr.data = fwd_data
            if instr.dst_reg is not None:
                self.registers[instr.dst_reg] = fwd_data
            self.forwarding_events += 1
            instr.executed = True
            instr.completed = True
            self.loads_executed += 1
            return True
        
        # Check predictor
        can_speculate, wait_seq = self.predictor.predict_load(instr.pc)
        
        if not can_speculate or has_dep:
            # Wait for earlier stores
            return False
        
        # Speculate - access memory
        data = self.memory.get(instr.address, 0)
        instr.data = data
        if instr.dst_reg is not None:
            self.registers[instr.dst_reg] = data
        
        instr.speculative = True
        instr.executed = True
        instr.completed = True  # Will validate at commit
        
        if instr.lsq_idx is not None:
            self.lsq.mark_speculative(instr.lsq_idx)
            self.lsq.mark_completed(instr.lsq_idx)
        
        self.loads_executed += 1
        return True
    
    def _execute_store(self, instr: Instruction) -> bool:
        """Execute a store instruction"""
        # Calculate address
        base_addr = self.registers[instr.src_regs[0]] if len(instr.src_regs) > 0 else 0
        instr.address = base_addr + instr.immediate
        
        # Get data from register
        data_reg = instr.src_regs[1] if len(instr.src_regs) > 1 else 0
        instr.data = self.registers[data_reg]
        
        # Update LSQ
        if instr.lsq_idx is not None:
            self.lsq.update_address(instr.lsq_idx, instr.address)
            self.lsq.update_data(instr.lsq_idx, instr.data)
            self.lsq.mark_completed(instr.lsq_idx)
        
        instr.executed = True
        instr.completed = True
        self.stores_executed += 1
        return True
    
    def commit_instruction(self) -> Optional[Instruction]:
        """
        Commit Stage: Retire head instruction if ready
        
        Validates speculation and updates architectural state
        """
        instr = self.rob.commit_head()
        if instr is None:
            return None
        
        # For loads, validate speculation
        if instr.instr_type == InstructionType.LOAD and instr.speculative:
            violation = self._validate_load(instr)
            if violation:
                # Speculation violation - need to recover
                self.speculation_violations += 1
                self._recover_from_violation(instr)
                return None
            else:
                # Correct speculation
                self.predictor.report_correct_speculation(instr.pc)
        
        # For stores, write to memory
        if instr.instr_type == InstructionType.STORE:
            self.memory[instr.address] = instr.data
            self.predictor.clear_store(instr.pc)
        
        # Free LSQ entry
        if instr.lsq_idx is not None:
            # In real implementation, would properly free the entry
            pass
        
        self.instructions_committed += 1
        return instr
    
    def _validate_load(self, load_instr: Instruction) -> bool:
        """
        Validate a speculative load
        
        Returns: True if violation detected
        """
        if load_instr.lsq_idx is None:
            return False
        
        # Re-check dependencies now that we know all earlier store addresses
        has_dep, fwd_idx, fwd_data = self.lsq.check_dependency(load_instr.lsq_idx)
        
        if fwd_data is not None:
            # Should have forwarded from store
            if load_instr.data != fwd_data:
                return True  # Violation - loaded wrong data
        
        return False
    
    def _recover_from_violation(self, violating_instr: Instruction):
        """
        Recover from memory ordering violation
        
        Flush pipeline and restart from violating instruction
        """
        # Find conflicting store
        if violating_instr.lsq_idx is not None:
            has_dep, fwd_idx, _ = self.lsq.check_dependency(violating_instr.lsq_idx)
            if has_dep and fwd_idx is not None:
                store_entry = self.lsq.entries[fwd_idx]
                if store_entry:
                    # Update predictor
                    self.predictor.report_violation(violating_instr.pc, store_entry.pc)
        
        # Squash from violating instruction
        self.rob.squash_from(violating_instr.seq_num)
        self.lsq.squash_from(violating_instr.seq_num)
        
        # Reset PC to violating instruction
        self.pc = violating_instr.pc
    
    def cycle_step(self, instruction_stream: List[Instruction]):
        """Execute one pipeline cycle"""
        self.cycle += 1
        
        # Commit stage (process head of ROB)
        self.commit_instruction()
        
        # Execute stage (process issued instructions)
        # In real pipeline, would track which instructions are ready
        
        # Issue stage (fetch and issue new instruction)
        if instruction_stream and not self.rob.is_full():
            next_instr = instruction_stream[0]
            if self.issue_instruction(next_instr):
                instruction_stream.pop(0)
    
    def get_stats(self) -> Dict[str, any]:
        """Get pipeline statistics"""
        return {
            'cycles': self.cycle,
            'instructions_committed': self.instructions_committed,
            'loads_executed': self.loads_executed,
            'stores_executed': self.stores_executed,
            'speculation_violations': self.speculation_violations,
            'forwarding_events': self.forwarding_events,
            'ipc': self.instructions_committed / self.cycle if self.cycle > 0 else 0,
            'predictor_stats': self.predictor.get_stats()
        }
    
    def __repr__(self):
        stats = self.get_stats()
        return (f"Pipeline(cycle={self.cycle}, IPC={stats['ipc']:.2f}, "
                f"violations={self.speculation_violations})")


if __name__ == "__main__":
    print("Testing 3-Stage OoO Pipeline with Memory Disambiguation...")
    
    pipeline = Pipeline()
    
    # Create a simple instruction sequence
    # Store then Load from same address
    instructions = [
        Instruction(pc=0x1000, instr_type=InstructionType.STORE, 
                   src_regs=[1, 2], immediate=0),  # ST R2 -> [R1+0]
        Instruction(pc=0x1004, instr_type=InstructionType.LOAD,
                   dst_reg=3, src_regs=[1], immediate=0),  # LD [R1+0] -> R3
    ]
    
    # Set up registers
    pipeline.registers[1] = 0x1000  # Base address
    pipeline.registers[2] = 0xDEAD  # Data to store
    
    # Run simulation
    for i in range(20):
        pipeline.cycle_step(instructions)
        if not instructions:
            break
    
    print(f"\nFinal state: {pipeline}")
    print(f"Stats: {pipeline.get_stats()}")
    print(f"Memory[0x1000] = 0x{pipeline.memory.get(0x1000, 0):x}")
    print(f"R3 = 0x{pipeline.registers[3]:x}")
