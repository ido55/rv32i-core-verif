"""cocotb harness for tb/tb_top.sv: load a program, run the core, check it against the ISS.

Checking happens at two levels:
1. Scoreboard, every retired instruction: the core's retire port must equal the
   `Retire` record from `Iss.step()` (pc, insn, next pc, rd write, store).
2. End of test: the full register file and the full data memory must equal the ISS state.

Timing: the testbench samples the retire port on the FALLING clock edge, when all
combinational logic has settled; the instruction then commits on the next rising edge.
"""

from dataclasses import dataclass, fields

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from model.decoder import IllegalInstruction, decode, to_asm
from model.iss import Iss, Memory, Retire

MEM_WORDS = 4096  # must match tb_top's MEM_WORDS parameter
MEM_BYTES = 4 * MEM_WORDS
CLOCK_PERIOD_NS = 10

CORE_SINGLE_SOURCES = [
    "rtl/rv32i_pkg.sv", "rtl/alu.sv", "rtl/regfile.sv", "rtl/decoder.sv",
    "rtl/branch_unit.sv", "rtl/lsu.sv", "rtl/core_single.sv", "tb/tb_top.sv",
]  # fmt: skip


class ScoreboardMismatch(AssertionError):
    """The core did something different from the golden model."""


def disasm(word: int) -> str:
    try:
        return to_asm(decode(word))
    except IllegalInstruction:
        return f".word 0x{word:08x}  (illegal)"


def format_retire(r: Retire) -> str:
    text = f"pc=0x{r.pc:08x}  {disasm(r.insn):<28}"
    if r.rd:
        text += f" x{r.rd}=0x{r.rd_wdata:08x}"
    if r.mem_wmask:
        text += f" mem[0x{r.mem_addr:08x}]=0x{r.mem_wdata:08x} mask={r.mem_wmask:04b}"
    return text


@dataclass
class RunResult:
    retired: int  # instructions retired, including the final ECALL/EBREAK
    cycles: int  # clock cycles from reset release to the halting instruction
    trace: list[Retire]


class CoreHarness:
    def __init__(self, dut):
        self.dut = dut
        self.iss: Iss | None = None
        self._clock_started = False

    # ---- Setup ----------------------------------------------------------------------

    def load(self, program: list[int], data: dict[int, int] | None = None) -> None:
        """Place `program` at address 0 and `data` ({byte address: word}) in memory.

        The same image goes into the RTL instruction memory, the RTL data memory and
        the ISS memory. Every word is written, which also clears the previous test.
        """
        image = [0] * MEM_WORDS
        image[: len(program)] = program
        for addr, word in (data or {}).items():
            assert addr % 4 == 0, "data must be word-aligned"
            image[addr // 4] = word

        for index, word in enumerate(image):
            self.dut.imem[index].value = word
            self.dut.dmem[index].value = word

        mem = Memory(MEM_BYTES)
        mem.load_words(image, 0)
        self.iss = Iss(mem, pc=0)

    async def _reset(self) -> None:
        if not self._clock_started:
            cocotb.start_soon(Clock(self.dut.clk, CLOCK_PERIOD_NS, units="ns").start())
            self._clock_started = True
        self.dut.rst_n.value = 0
        for _ in range(2):
            await RisingEdge(self.dut.clk)
        # Release on a rising edge: this edge still sees reset, the next one executes pc 0.
        self.dut.rst_n.value = 1

    # ---- Run ------------------------------------------------------------------------

    async def run(self, max_cycles: int = 10_000, expect_trap: bool = False) -> RunResult:
        """Run until ECALL/EBREAK (or an illegal instruction if `expect_trap`)."""
        assert self.iss is not None, "call load() first"
        dut = self.dut
        await self._reset()

        trace: list[Retire] = []
        cycles = 0
        while True:
            await FallingEdge(dut.clk)
            cycles += 1
            if cycles > max_cycles:
                raise ScoreboardMismatch(self._report(f"no halt within {max_cycles} cycles", trace))
            if dut.mem_fault.value:
                raise ScoreboardMismatch(self._report("memory access outside imem/dmem", trace))
            if not dut.rvfi_valid.value:
                continue

            if dut.rvfi_trap.value:
                if expect_trap:
                    break
                insn = int(dut.rvfi_insn.value)
                raise ScoreboardMismatch(self._report(f"core trapped on {disasm(insn)}", trace))

            got = self._read_retire()
            self._check(got, trace)
            trace.append(got)
            if got.halt:
                break

        if expect_trap and not dut.rvfi_trap.value:
            raise ScoreboardMismatch(self._report("expected an illegal-instruction trap", trace))

        # One more cycle: the core must now be halted and retire nothing.
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        assert dut.halted.value == 1 and dut.rvfi_valid.value == 0, "core did not halt"

        self._check_final_state()
        return RunResult(retired=len(trace) + int(expect_trap), cycles=cycles, trace=trace)

    # ---- Checking -------------------------------------------------------------------

    def _read_retire(self) -> Retire:
        d = self.dut
        return Retire(
            pc=int(d.rvfi_pc.value),
            insn=int(d.rvfi_insn.value),
            next_pc=int(d.rvfi_next_pc.value),
            rd=int(d.rvfi_rd.value),
            rd_wdata=int(d.rvfi_rd_wdata.value),
            mem_addr=int(d.rvfi_mem_addr.value),
            mem_wdata=int(d.rvfi_mem_wdata.value),
            mem_wmask=int(d.rvfi_mem_wmask.value),
            halt=bool(d.rvfi_halt.value),
        )

    def _check(self, got: Retire, trace: list[Retire]) -> None:
        try:
            expected = self.iss.step()
        except Exception as exc:  # the program did something the model rejects
            raise ScoreboardMismatch(
                self._report(f"golden model raised {exc!r} at pc=0x{got.pc:08x}", trace)
            ) from exc
        if got == expected:
            return
        diffs = []
        for f in fields(Retire):
            core_value, model_value = getattr(got, f.name), getattr(expected, f.name)
            if core_value != model_value:
                diffs.append(f"  {f.name:<10} core={_fmt(core_value)}  model={_fmt(model_value)}")
        header = f"retire #{len(trace)} mismatch at pc=0x{expected.pc:08x}: {disasm(expected.insn)}"
        raise ScoreboardMismatch(self._report(header + "\n" + "\n".join(diffs), trace))

    def _check_final_state(self) -> None:
        for reg in range(1, 32):
            rtl, model = self.read_reg(reg), self.iss.regs[reg]
            assert rtl == model, f"final x{reg}: core=0x{rtl:08x} model=0x{model:08x}"
        for index in range(MEM_WORDS):
            rtl = int(self.dut.dmem[index].value)
            model = self.iss.mem.load(4 * index, 4)
            assert rtl == model, (
                f"final mem[0x{4 * index:04x}]: core=0x{rtl:08x} model=0x{model:08x}"
            )

    def read_reg(self, reg: int) -> int:
        """Read an architectural register straight from the RTL register file."""
        if reg == 0:
            return 0
        return int(self.dut.u_core.u_regfile.regs_q[reg].value)

    @staticmethod
    def _report(message: str, trace: list[Retire], history: int = 8) -> str:
        lines = [message, f"last {min(history, len(trace))} retired instructions:"]
        lines += ["  " + format_retire(r) for r in trace[-history:]]
        return "\n".join(lines)


def _fmt(value: int | bool) -> str:
    return str(value) if isinstance(value, bool) else f"0x{value:08x}"
