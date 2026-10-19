/* Memory map shared by tb_top.sv and the ISS: 16 KiB starting at address 0.
 *   0x0000 - 0x1FFF  code (.text)
 *   0x2000 - 0x3FFF  data (.data, .rodata, .bss) and, for C programs, the stack
 *                    (crt0.S starts sp at 0x4000 and it grows down)
 */
OUTPUT_ARCH("riscv")
ENTRY(_start)

SECTIONS
{
  . = 0x0000;
  .text : { *(.text.init) *(.text) *(.text.*) }

  . = 0x2000;
  .data : { *(.data) *(.data.*) *(.sdata) *(.sdata.*) *(.rodata) *(.rodata.*) *(.srodata*) }
  .bss  : { *(.bss) *(.bss.*) *(.sbss) *(.sbss.*) *(COMMON) }

  _end = .;
  ASSERT(SIZEOF(.text) <= 0x2000, "code does not fit below 0x2000")
}
