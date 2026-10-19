"""Build test programs with the RISC-V GCC toolchain into memory images (lists of words).

Two kinds of programs, both linked with programs/link.ld (code at 0x0, data at 0x2000):
- the official riscv-tests rv32ui suite (third_party/riscv-tests) with our minimal
  environment programs/riscv-test-env/riscv_test.h: pass means gp (x3) == 1 at ECALL;
- the C programs in programs/ with crt0.S: main()'s return value is in a0 (x10) at ECALL.

Outputs go to build/, and are rebuilt only when a source file is newer.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_ROOT / "build"
PROGRAMS_DIR = REPO_ROOT / "programs"
RISCV_TESTS_ISA = REPO_ROOT / "third_party" / "riscv-tests" / "isa"

GCC = "riscv64-unknown-elf-gcc"
OBJCOPY = "riscv64-unknown-elf-objcopy"
IMAGE_BYTES = 0x4000  # must match tb_top's memory size

COMMON_FLAGS = [
    "-march=rv32i", "-mabi=ilp32",
    "-nostdlib", "-nostartfiles", "-static",
    "-mno-relax",  # keep every instruction exactly as written (no linker relaxation)
    "-T", str(PROGRAMS_DIR / "link.ld"),
    "-Wl,--no-warn-rwx-segments",
]  # fmt: skip
C_FLAGS = [
    "-O2", "-ffreestanding", "-fno-builtin",
    "-fno-tree-loop-distribute-patterns",  # stop GCC turning loops into memset/memcpy calls
    "-msmall-data-limit=0",  # no gp-relative data: crt0 does not set up gp
    "-Wall", "-Wextra", "-Werror",
]  # fmt: skip

# rv32ui tests that need features this core does not implement.
RISCV_TESTS_EXCLUDED = {
    "fence_i": "self-modifying code; needs Zifencei and a writable instruction memory",
    "ma_data": "misaligned loads/stores, which are out of scope",
}


def toolchain_available() -> bool:
    return shutil.which(GCC) is not None


def _rebuild_needed(target: Path, sources: list[Path]) -> bool:
    if not target.exists():
        return True
    return any(src.stat().st_mtime > target.stat().st_mtime for src in sources)


def _link(sources: list[Path], elf: Path, flags: list[str], deps: list[Path]) -> None:
    if not _rebuild_needed(elf, sources + deps):
        return
    elf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([GCC, *COMMON_FLAGS, *flags, "-o", str(elf), *map(str, sources)], check=True)


def elf_to_image(elf: Path) -> list[int]:
    """Flat memory image from address 0 (gaps filled with zeros), as 32-bit words."""
    binary = elf.with_suffix(".bin")
    if _rebuild_needed(binary, [elf]):
        subprocess.run([OBJCOPY, "-O", "binary", str(elf), str(binary)], check=True)
    data = binary.read_bytes()
    if len(data) > IMAGE_BYTES:
        raise ValueError(f"{elf.name}: image is {len(data)} bytes, memory is {IMAGE_BYTES}")
    data += bytes(-len(data) % 4)
    return [int.from_bytes(data[i : i + 4], "little") for i in range(0, len(data), 4)]


@dataclass(frozen=True)
class Program:
    name: str
    image: list[int]


# ---- riscv-tests ------------------------------------------------------------------------


def riscv_test_names() -> list[str]:
    names = sorted(path.stem for path in (RISCV_TESTS_ISA / "rv32ui").glob("*.S"))
    return [name for name in names if name not in RISCV_TESTS_EXCLUDED]


def build_riscv_test(name: str) -> Program:
    src = RISCV_TESTS_ISA / "rv32ui" / f"{name}.S"
    env = PROGRAMS_DIR / "riscv-test-env"
    macros = RISCV_TESTS_ISA / "macros" / "scalar"
    deps = [
        RISCV_TESTS_ISA / "rv64ui" / f"{name}.S",  # rv32ui/x.S includes rv64ui/x.S
        env / "riscv_test.h",
        macros / "test_macros.h",
        PROGRAMS_DIR / "link.ld",
    ]
    elf = BUILD_DIR / "riscv-tests" / f"rv32ui-{name}.elf"
    _link([src], elf, ["-I", str(env), "-I", str(macros)], [d for d in deps if d.exists()])
    return Program(f"rv32ui-{name}", elf_to_image(elf))


# ---- C programs -------------------------------------------------------------------------


def _expected_fibonacci() -> int:
    a, b = 0, 1
    for _ in range(15):
        a, b = b, a + b
    return a  # fib(15) = 610


def _expected_bubble_sort() -> int:
    """Python copy of programs/bubble_sort.c."""
    mask = 0xFFFF_FFFF
    x, values = 2463534242, []
    for _ in range(32):
        x ^= (x << 13) & mask
        x ^= x >> 17
        x ^= (x << 5) & mask
        values.append(x)
    checksum = 0
    for value in sorted(values):
        checksum = (((checksum << 1) | (checksum >> 31)) & mask) ^ value
    return checksum


# C program name -> expected return value (a0), computed independently of the RTL and ISS.
C_PROGRAMS = {"fibonacci": _expected_fibonacci(), "bubble_sort": _expected_bubble_sort()}


def build_c_program(name: str) -> Program:
    sources = [PROGRAMS_DIR / "crt0.S", PROGRAMS_DIR / f"{name}.c"]
    elf = BUILD_DIR / "programs" / f"{name}.elf"
    _link(sources, elf, C_FLAGS, [PROGRAMS_DIR / "link.ld"])
    return Program(name, elf_to_image(elf))
