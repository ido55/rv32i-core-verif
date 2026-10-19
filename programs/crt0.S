# Startup code for the C programs: set up a stack, call main(), halt with ECALL.
# main()'s return value is left in a0 for the testbench to check.
    .section .text.init
    .globl _start
_start:
    li   sp, 0x4000      # top of the 16 KiB memory; the stack grows down
    call main
    ecall
