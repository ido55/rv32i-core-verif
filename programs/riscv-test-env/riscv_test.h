// Minimal riscv-tests environment for this project (replaces riscv-tests' env/p).
// Bare metal, no CSRs, no traps: the standard env needs Zicsr, which this core lacks.
//
// A test ends with ECALL. Result convention (same as the standard env):
//   gp (x3) == 1            pass
//   gp (x3) == 2 * n + 1    test case n failed
#ifndef RV32I_CORE_VERIF_RISCV_TEST_H
#define RV32I_CORE_VERIF_RISCV_TEST_H

#define RVTEST_RV32U .macro init; .endm
#define RVTEST_RV64U .macro init; .endm

#define TESTNUM gp

#define RVTEST_CODE_BEGIN \
  .section .text.init;    \
  .align 2;               \
  .globl _start;          \
_start:                   \
  init;

#define RVTEST_CODE_END ecall

#define RVTEST_PASS \
  fence;            \
  li TESTNUM, 1;    \
  li a0, 0;         \
  ecall

#define RVTEST_FAIL              \
  fence;                         \
1: beqz TESTNUM, 1b;             \
  sll TESTNUM, TESTNUM, 1;       \
  or TESTNUM, TESTNUM, 1;        \
  mv a0, TESTNUM;                \
  ecall

#define RVTEST_DATA_BEGIN .data; .align 4;
#define RVTEST_DATA_END

#endif
