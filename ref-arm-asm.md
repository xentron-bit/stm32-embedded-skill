# ARM Thumb-2 Assembly — Cortex-M Reference

STM32 embedded geliştirme için ARM assembly: Cortex-M0/M0+/M3/M4/M7 Thumb-2 instruction set, GCC inline asm, CMSIS intrinsics, startup kodu ve optimizasyon pattern'leri.

---

## Cortex-M Instruction Set Ailesi

| Çekirdek | Instruction Set | 32-bit Instr | Hardware Divide | FPU |
|----------|----------------|-------------|----------------|-----|
| M0/M0+ | Thumb (16-bit only) | Yok | Yok | Yok |
| M3 | Thumb-2 (16+32 bit) | Var | Var (SDIV/UDIV) | Yok |
| M4 | Thumb-2 + DSP | Var | Var | Opsiyonel (FPv4-SP) |
| M7 | Thumb-2 + DSP | Var | Var | Opsiyonel (FPv5) |
| M33 | Thumb-2 + TrustZone | Var | Var | Opsiyonel |

**Kritik Not:** Cortex-M işlemciler ARM modu çalıştırmaz — sadece Thumb/Thumb-2.  
PC'nin bit[0] = 1 olmalı (Thumb state). Fonksiyon pointer'larında `| 1` unutma.

---

## Register Mimarisi

```
r0  - r3   : Argüman / dönüş değeri / scratch (AAPCS)
r4  - r11  : Callee-saved (fonksiyon korumalı)
r12 (ip)   : Intra-procedure scratch (BL/BLX arası güvenilmez)
r13 (sp)   : Stack pointer (PUSH/POP)
r14 (lr)   : Link register (dönüş adresi)
r15 (pc)   : Program counter
```

**CPSR/xPSR Bayrakları:**
```
Bit 31 (N) : Negatif sonuç
Bit 30 (Z) : Sıfır sonuç
Bit 29 (C) : Carry / borrow
Bit 28 (V) : Signed overflow
Bit 27 (Q) : Saturation (M4/M7 DSP)
Bit  5 (T) : Thumb state (her zaman 1, Cortex-M)
```

**Özel kayıtlar (MRS/MSR ile erişilir):**
```
PRIMASK    : Bit[0]=1 → tüm maskable interrupt'ları engelle
BASEPRI    : Eşit veya düşük öncelikli interrupt'ları engelle
FAULTMASK  : Tüm interrupt + fault'ları engelle (NMI hariç)
CONTROL    : Privilege level, stack pointer seçimi, FPU context
```

---

## GAS Assembler Direktifleri

```asm
.syntax unified        @ Unified ARM/Thumb syntax — her zaman kullan
.thumb                 @ Thumb instruction encoding
.thumb_func            @ Sonraki fonksiyon Thumb (BX/BLX hedefi)
.global  symbol        @ Sembolü dışarıya aç
.weak    symbol        @ Zayıf sembol (linker override edebilir)
.type    func, %function  @ ELF function type
.size    func, .-func  @ ELF symbol size (her fonksiyon sonunda)
.section .text         @ Kod bölümü
.section .rodata       @ Salt okunur veri (flash'da kalır)
.section .data         @ Başlangıç değeri olan değişkenler
.section .bss          @ Sıfır başlangıçlı değişkenler
.align   n             @ 2^n sınırına hizala
.word    value         @ 32-bit değer
.hword   value         @ 16-bit değer
.byte    value         @ 8-bit değer
.space   n             @ n byte sıfır
.ascii   "str"         @ String (null terminator yok)
.asciz   "str"         @ Null-terminated string
```

---

## Temel Instruction Set

### Veri Aktarımı

```asm
@ Register ← immediate
mov  r0, #42           @ r0 = 42 (8-bit + rotate, sınırlı)
movw r0, #0x1234       @ r0 = 0x1234 (16-bit immediate, Thumb-2)
movt r0, #0x5678       @ r0[31:16] = 0x5678 → r0 = 0x56781234
mov  r0, r1            @ r0 = r1

@ Ldr pseudo-instruction (assembler literal pool kullanır)
ldr  r0, =0xDEADBEEF  @ r0 = 0xDEADBEEF (herhangi bir 32-bit değer)
ldr  r0, =SomeLabel    @ r0 = label adresi

@ Register ↔ special register
mrs  r0, PRIMASK       @ r0 = PRIMASK
msr  PRIMASK, r0       @ PRIMASK = r0
mrs  r0, CONTROL       @ r0 = CONTROL
mrs  r0, PSP           @ r0 = Process Stack Pointer
msr  PSP, r0           @ Process Stack Pointer = r0
```

### Aritmetik ve Mantık

```asm
@ Format: op{cond}{s} Rd, Rn, Op2
add  r0, r1, r2        @ r0 = r1 + r2
add  r0, r0, #4        @ r0 += 4
adc  r0, r1, r2        @ r0 = r1 + r2 + C (carry)
sub  r0, r1, r2        @ r0 = r1 - r2
sbc  r0, r1, r2        @ r0 = r1 - r2 - borrow
rsb  r0, r1, #0        @ r0 = 0 - r1 (negate — M0'da mul yok, bu kullanılır)
mul  r0, r1, r2        @ r0 = r1 * r2 (düşük 32-bit)
mla  r0, r1, r2, r3   @ r0 = r1*r2 + r3

@ Mantık
and  r0, r1, r2        @ r0 = r1 & r2
orr  r0, r1, r2        @ r0 = r1 | r2
eor  r0, r1, r2        @ r0 = r1 ^ r2
bic  r0, r1, r2        @ r0 = r1 & ~r2 (bit clear)
mvn  r0, r1            @ r0 = ~r1
orn  r0, r1, r2        @ r0 = r1 | ~r2 (Thumb-2 only)

@ Karşılaştırma (sonuç yok, sadece flag)
cmp  r0, r1            @ flags ← r0 - r1
cmn  r0, r1            @ flags ← r0 + r1
tst  r0, r1            @ flags ← r0 & r1 (bit testi)
teq  r0, r1            @ flags ← r0 ^ r1 (eşitlik testi, Thumb-2)

@ Division (M3/M4/M7 only — M0'da yok!)
sdiv r0, r1, r2        @ r0 = r1 / r2 (işaretli)
udiv r0, r1, r2        @ r0 = r1 / r2 (işaretsiz)

@ Barrel shifter
lsl  r0, r1, #3        @ r0 = r1 << 3
lsr  r0, r1, #3        @ r0 = r1 >> 3 (mantıksal)
asr  r0, r1, #3        @ r0 = r1 >> 3 (aritmetik, işaret korunur)
ror  r0, r1, #3        @ r0 = r1 rotate right 3

@ Barrel shifter içinde kullanım (tek cycle, Thumb-2 32-bit form)
add  r0, r1, r2, lsl #2   @ r0 = r1 + (r2 << 2)  — 4x multiply + add
ldr  r0, [r1, r2, lsl #2] @ r0 = *(r1 + r2*4) — array index
```

### Bellek Erişimi

```asm
@ Temel yükleme/saklama
ldr  r0, [r1]          @ r0 = *(uint32_t *)r1
ldrh r0, [r1]          @ r0 = *(uint16_t *)r1 (zero extend)
ldrb r0, [r1]          @ r0 = *(uint8_t *)r1 (zero extend)
ldrsh r0, [r1]         @ r0 = *(int16_t *)r1 (sign extend)
ldrsb r0, [r1]         @ r0 = *(int8_t *)r1 (sign extend)

str  r0, [r1]          @ *(uint32_t *)r1 = r0
strh r0, [r1]          @ *(uint16_t *)r1 = r0 (low 16-bit)
strb r0, [r1]          @ *(uint8_t *)r1 = r0 (low 8-bit)

@ Offset adresleme
ldr  r0, [r1, #8]      @ r0 = *(uint32_t *)(r1 + 8)
ldr  r0, [r1, r2]      @ r0 = *(uint32_t *)(r1 + r2)
ldr  r0, [r1, r2, lsl #2] @ r0 = *(uint32_t *)(r1 + r2*4)

@ Pre-indexed with write-back
ldr  r0, [r1, #4]!     @ r1 += 4; r0 = *r1

@ Post-indexed
ldr  r0, [r1], #4      @ r0 = *r1; r1 += 4

@ Multiple register load/store (RTOS context save/restore'da kullanılır)
ldmia r0!, {r4-r11}    @ r4..r11 = *r0; r0 += 32 (increment after)
stmia r0!, {r4-r11}    @ *r0 = r4..r11; r0 += 32
ldmdb r0!, {r4-r11}    @ r0 -= 32; r4..r11 = *r0 (decrement before)

@ Stack push/pop (ldmdb sp / stmia sp eşdeğeri)
push {r4-r7, lr}       @ SP -= n*4; *(SP+offset) = r4,r5,r6,r7,lr
pop  {r4-r7, pc}       @ r4,r5,r6,r7,pc = *SP; SP += n*4
```

### Dallanma ve Kontrol Akışı

```asm
@ Dallanma
b    label             @ PC = label
bl   func              @ LR = PC+4; PC = func (C fonksiyon çağrısı)
bx   lr                @ PC = LR (fonksiyondan dönüş)
blx  r0                @ LR = PC+4; PC = r0 (register'dan çağrı)

@ Koşullu dallanma
beq  label             @ Z=1 ise
bne  label             @ Z=0 ise
bcs  label             @ C=1 ise (unsigned >=)
bcc  label             @ C=0 ise (unsigned <)
bmi  label             @ N=1 ise (negatif)
bpl  label             @ N=0 ise (pozitif)
bvs  label             @ V=1 ise (overflow)
bvc  label             @ V=0 ise
bhi  label             @ unsigned > (C=1 & Z=0)
bls  label             @ unsigned <= (C=0 | Z=1)
bge  label             @ signed >= (N=V)
blt  label             @ signed < (N≠V)
bgt  label             @ signed > (Z=0 & N=V)
ble  label             @ signed <= (Z=1 | N≠V)

@ Compare and branch (M3/M4/M7, short range)
cbz  r0, label         @ r0 == 0 ise dal (flags değiştirmez)
cbnz r0, label         @ r0 != 0 ise dal

@ IT block (Thumb-2: conditional execution)
cmp  r0, #5
it   eq                @ IT eşitlik
moveq r1, #1           @ r0==5 ise r1 = 1
@ Not: armclang -O2 IT block üretir — inline asm'de dikkatli kullan
```

---

## Cortex-M Özel Instruction'lar

```asm
@ Interrupt kontrolü
cpsid i                @ PRIMASK=1: tüm interrupt'ları kapat (CPSID I)
cpsie i                @ PRIMASK=0: interrupt'ları aç (CPSIE I)
cpsid f                @ FAULTMASK=1: fault + interrupt kapat
cpsie f                @ FAULTMASK=0: fault + interrupt aç

@ Memory barriers — cache/store buffer sıralaması
dsb                    @ Data Synchronization Barrier
dmb                    @ Data Memory Barrier
isb                    @ Instruction Synchronization Barrier (pipeline flush)

@ Power
wfi                    @ Wait For Interrupt (sleep)
wfe                    @ Wait For Event
sev                    @ Send Event (diğer core'u uyandır, M4/M7 multi-core)
nop                    @ No operation (sıralaması korunur, NOP hint)

@ Debug
bkpt #0                @ Breakpoint (debugger halt)

@ Sistem çağrısı (RTOS)
svc  #0                @ Supervisor Call — RTOS sistem servisi

@ Özel kayıt işlemleri
mrs  r0, IPSR          @ Current exception number (0=thread mode)
mrs  r0, EPSR          @ Execution PSR
mrs  r0, MSP           @ Main Stack Pointer değerini oku

@ Byte reverse (endianness)
rev  r0, r1            @ Big↔Little endian 32-bit word
rev16 r0, r1           @ Her 16-bit yarısını byte-swap
revsh r0, r1           @ 16-bit halfword swap + sign extend

@ Bit manipulation (Thumb-2)
clz  r0, r1            @ Count Leading Zeros (bsr/bit-scan eşdeğeri)
rbit r0, r1            @ Reverse all bits
ubfx r0, r1, #8, #8   @ Unsigned Bit Field Extract: r0 = r1[15:8]
sbfx r0, r1, #8, #8   @ Signed Bit Field Extract (sign extend)
bfi  r0, r1, #8, #8   @ Bit Field Insert: r0[15:8] = r1[7:0]
bfc  r0, #8, #8        @ Bit Field Clear: r0[15:8] = 0

@ Exclusive access (atomic operations — spinlock, mutex)
ldrex r0, [r1]         @ Exclusive load (monitor set)
strex r2, r0, [r1]     @ Exclusive store: r2=0 success, r2=1 fail
clrex                  @ Clear exclusive monitor
```

---

## CMSIS Intrinsics — Inline Assembly Alternatifi

Uygulama kodunda ham asm yerine CMSIS intrinsics kullan. Daha taşınabilir, derleyici optimize eder.

```c
/* cmsis_compiler.h / core_cmX.h'de tanımlı */

/* Interrupt kontrolü */
__disable_irq()          /* → CPSID I */
__enable_irq()           /* → CPSIE I */
uint32_t p = __get_PRIMASK();    /* → MRS r0, PRIMASK */
__set_PRIMASK(p);                /* → MSR PRIMASK, r0 */
uint32_t b = __get_BASEPRI();
__set_BASEPRI(5 << 4);           /* FreeRTOS: priority value shifted */

/* Memory barriers */
__DSB()   /* → DSB */
__DMB()   /* → DMB */
__ISB()   /* → ISB */

/* Power */
__WFI()   /* → WFI */
__WFE()   /* → WFE */
__SEV()   /* → SEV */

/* Bit operations */
uint32_t clz = __CLZ(value);     /* Count Leading Zeros */
uint32_t rev = __REV(value);     /* Byte swap */
uint32_t rbit = __RBIT(value);   /* Bit reverse */

/* Saturation (M4/M7 DSP) */
int32_t sat = __SSAT(value, 16); /* Saturate to 16-bit signed */
uint32_t usat = __USAT(value, 8); /* Saturate to 8-bit unsigned */

/* Exclusive access */
uint32_t val = __LDREXW(addr);
uint32_t result = __STREXW(val, addr);  /* 0=success, 1=fail */
__CLREX();
```

---

## GCC Inline Assembly Syntax

```c
/* Temel form */
__asm("DSB");               /* Simple statement */
__asm volatile("DSB");      /* Sıra değiştirilemez */
__asm volatile("DSB" ::: "memory");  /* Memory clobber — compiler barrier */

/* Extended inline asm */
/* __asm volatile("instruction" : outputs : inputs : clobbers) */

/* Örnek: PRIMASK okuma */
uint32_t primask;
__asm volatile ("MRS %0, PRIMASK" : "=r" (primask) : : "memory");

/* Örnek: PRIMASK yazma */
__asm volatile ("MSR PRIMASK, %0" : : "r" (primask) : "memory");

/* Örnek: Kritik bölge (inline) */
static inline uint32_t enter_critical(void)
{
    uint32_t primask;
    __asm volatile (
        "MRS %0, PRIMASK\n\t"
        "CPSID I\n\t"
        : "=r" (primask) : : "memory"
    );
    return primask;
}

static inline void exit_critical(uint32_t primask)
{
    __asm volatile ("MSR PRIMASK, %0" : : "r" (primask) : "memory");
}

/* Constraint'ler */
/* "=r"  : output, any register */
/* "r"   : input, any register */
/* "+r"  : read-write register */
/* "=&r" : output early-clobber (diğer operandlarla aynı register değil) */
/* "m"   : memory operand */
/* "i"   : immediate */
/* "0"   : first operand ile aynı register */

/* Clobber listesi */
/* "memory" : bellek sırası korunur (compiler barrier) */
/* "cc"     : condition codes (flags) değişebilir */
/* "r0"     : belirli bir register clobber edildi */
```

### Keil armclang (AC6) Inline Assembly

```c
/* GCC asm syntax — AC6 GCC-compatible mode kullanır */
__asm volatile("DSB" ::: "memory");   /* GCC style — çalışır */

/* Keil __asm() keyword (legacy, AC5 compatible) */
__asm
{
    MRS r0, PRIMASK
    ORR r0, r0, #1
    MSR PRIMASK, r0
}
/* Not: Keil __asm{} bloğu C değişkenlere doğrudan erişemez */
/* Extended GCC inline asm tercih edilmeli */
```

---

## AAPCS Calling Convention

```asm
@ Fonksiyon çağrısı kuralları (Application Binary Interface)
@ r0-r3   : argüman 1-4; return value r0 (veya r0+r1 64-bit için)
@ r4-r11  : çağrılan taraf korum (callee-saved)
@ r12     : scratch (güvenilmez)
@ sp      : 8-byte hizalı olmalı (public interface'de)
@ lr      : dönüş adresi (bl tarafından set edilir)

@ Tipik fonksiyon kalıbı
my_func:
    push {r4-r7, lr}        @ callee-saved + lr kaydet
    @ ... işlem ...
    pop  {r4-r7, pc}        @ restore + pc←lr (dönüş)

@ Büyük yerel değişkenler için sp rezerv
my_func2:
    push {r4-r7, lr}
    sub  sp, sp, #16        @ 16 byte yerel alan
    @ ... sp+0, sp+4, sp+8, sp+12 kullan ...
    add  sp, sp, #16
    pop  {r4-r7, pc}

@ r0-r3 argüman geçişi
@ void func(uint32_t a, uint32_t b, uint32_t c, uint32_t d)
@   r0=a, r1=b, r2=c, r3=d
@ 5. argüman: [sp, #0] üzerinden stack'ten

@ FPU (M4/M7): s0-s15, d0-d7 scratch; s16-s31, d8-d15 callee-saved
@ Lazy stacking: FPU register'ları CONTROL.FPCA=1 ise otomatik context save
```

---

## Startup Kodu Yapısı

### Vektör Tablosu ve Reset Handler (GAS, STM32H7)

```asm
.syntax unified
.cpu cortex-m7
.fpu softvfp
.thumb

@ Vektör tablosu — .isr_vector section, scatter/linker'da FIRST olmalı
.section .isr_vector, "a", %progbits
.type g_pfnVectors, %object

g_pfnVectors:
    .word  _estack                  @ Stack top (linker script'ten)
    .word  Reset_Handler
    .word  NMI_Handler
    .word  HardFault_Handler
    .word  MemManage_Handler
    .word  BusFault_Handler
    .word  UsageFault_Handler
    .word  0, 0, 0, 0               @ Reserved
    .word  SVC_Handler
    .word  DebugMon_Handler
    .word  0                        @ Reserved
    .word  PendSV_Handler
    .word  SysTick_Handler
    @ Peripheral IRQ'lar buradan devam eder...
    .word  WWDG_IRQHandler
    .word  PVD_AVD_IRQHandler
    @ ...

@ Reset Handler
.section .text.Reset_Handler
.weak   Reset_Handler
.type   Reset_Handler, %function
Reset_Handler:
    @ Stack pointer genellikle hardware tarafından vektör tablosundan yüklenir
    @ .data section'ı flash'tan RAM'a kopyala
    ldr  r0, =_sdata        @ RAM başlangıcı
    ldr  r1, =_edata        @ RAM sonu
    ldr  r2, =_sidata       @ Flash'taki data kaynağı

    movs r3, #0
copy_loop:
    cmp  r0, r1
    bge  copy_done
    ldr  r4, [r2, r3]
    str  r4, [r0, r3]
    adds r3, r3, #4
    b    copy_loop
copy_done:

    @ .bss section'ı sıfırla
    ldr  r0, =_sbss
    ldr  r1, =_ebss
    movs r2, #0
zero_loop:
    cmp  r0, r1
    bge  zero_done
    str  r2, [r0], #4
    b    zero_loop
zero_done:

    @ C kütüphane init (constructors, __libc_init_array)
    bl   SystemInit
    bl   __libc_init_array
    bl   main
    bx   lr
.size Reset_Handler, .-Reset_Handler

@ Weak default handler — tüm interrupt'lar buraya yönlenir (override edilmezse)
.section .text.Default_Handler
.weak   Default_Handler
.type   Default_Handler, %function
Default_Handler:
    b    Default_Handler    @ Infinite loop (debug: bkpt #0 ekle)
.size Default_Handler, .-Default_Handler

@ Her IRQ için weak alias — override edilebilir
.weak NMI_Handler
.thumb_set NMI_Handler, Default_Handler
.weak HardFault_Handler
.thumb_set HardFault_Handler, Default_Handler
@ ... diğerleri
```

---

## Exclusive Access — Atomic Operations

```asm
@ Spinlock implementasyonu (mutex low-level)
@ uint32_t try_lock(uint32_t *lock) { if(*lock==0) { *lock=1; return 1; } return 0; }
try_lock:
    ldrex  r1, [r0]         @ Exclusive load
    cmp    r1, #0
    bne    lock_fail
    movs   r1, #1
    strex  r2, r1, [r0]    @ Exclusive store
    cmp    r2, #0           @ r2=0: başarılı, r2=1: başka CPU öne geçti
    bne    try_lock          @ Başarısız: tekrar dene
    dmb                     @ Bellek bariyeri — lock'u almadan önce
    movs   r0, #1
    bx     lr
lock_fail:
    clrex                   @ Exclusive monitor'ü temizle
    movs   r0, #0
    bx     lr

@ C eşdeğeri
static inline int32_t atomic_compare_exchange(volatile int32_t *ptr,
                                               int32_t expected,
                                               int32_t desired)
{
    int32_t old;
    int32_t result;
    do {
        old = __LDREXW((volatile uint32_t *)ptr);
        if (old != expected) { __CLREX(); return 0; }
        result = __STREXW((uint32_t)desired, (volatile uint32_t *)ptr);
    } while (result != 0);
    __DMB();
    return 1;
}
```

---

## Optimizasyon Pattern'leri (Thumb-2)

```asm
@ Çarpma: 2^n katsayılar için shift kullan
add r0, r1, r1, lsl #3  @ r0 = r1 * 9 (r1 + r1*8)
rsb r0, r1, r1, lsl #4  @ r0 = r1 * 15 (r1*16 - r1)

@ Döngü: azalan sayaç (cmp gerektirmez — sıfır flag otomatik)
    movs r2, #64            @ 64 iterasyon
loop:
    ldr  r0, [r1], #4      @ *r1 yükle, r1 += 4
    @ ... işlem ...
    subs r2, r2, #1         @ r2--; Z flag set
    bne  loop               @ r2 != 0 → döngü devam

@ Koşullu yürütme (IT block — 3 instrdan az için dal yerine)
cmp  r0, #0
ite  eq                     @ If-Then-Else
moveq r1, #1               @ r0==0 → r1=1
movne r1, #0               @ r0!=0 → r1=0

@ uint32_t max(uint32_t a, uint32_t b) — dalsız
cmp  r0, r1
it   lo
movlo r0, r1               @ a < b ise r0 = b

@ Bit testi ve clear — BICS flag set eder
movs r1, #(1 << 5)
tst  r0, r1                @ bit test (sonuç yok)
bne  bit_set

@ Endian swap (network → host)
rev  r0, r1                @ 32-bit: 0xAABBCCDD → 0xDDCCBBAA

@ Count trailing zeros (via RBIT + CLZ)
rbit r1, r0                @ Bitleri ters çevir
clz  r0, r1                @ Artık leading zeros = trailing zeros

@ Hızlı modulo (2^n — bitwise AND)
and  r0, r0, #(BUF_SIZE - 1)  @ r0 %= BUF_SIZE (BUF_SIZE=2^n ise)
```

---

## Linker Script Essentials

```ld
/* STM32H743 için örnek */
MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 2048K
  DTCM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
  AXISRAM (rwx): ORIGIN = 0x24000000, LENGTH = 512K
}

SECTIONS
{
  .isr_vector :
  {
    KEEP(*(.isr_vector))   /* Vektör tablosu */
  } >FLASH

  .text :
  {
    *(.text)
    *(.text*)
    *(.rodata)
  } >FLASH

  /* _sidata: flash'taki data kaynağı */
  _sidata = LOADADDR(.data);

  .data :
  {
    _sdata = .;
    *(.data)
    *(.data*)
    _edata = .;
  } >DTCM AT> FLASH    /* DTCM'de çalış, FLASH'tan yükle */

  .bss :
  {
    _sbss = .;
    *(.bss)
    *(COMMON)
    _ebss = .;
  } >DTCM

  .dma_buffer (NOLOAD) :
  {
    . = ALIGN(32);
    *(.dma_buffer)
    . = ALIGN(32);
  } >AXISRAM   /* DMA buffer — AXI SRAM, DMA erişebilir */

  _estack = ORIGIN(DTCM) + LENGTH(DTCM);
}
```

---

## HardFault Handler — Stack Frame Decode

```asm
@ Keil armclang / GCC: HardFault'ta stack frame'i C handler'a ilet
.thumb_func
.global HardFault_Handler
HardFault_Handler:
    tst  lr, #4            @ EXC_RETURN[2]: PSP mi MSP mi?
    ite  eq
    mrseq r0, MSP          @ Main Stack
    mrsne r0, PSP          @ Process Stack
    ldr  r1, =hard_fault_handler_c
    bx   r1                @ r0 = stack frame pointer

@ C handler
void hard_fault_handler_c(uint32_t *sp)
{
    /* sp[0]=r0, sp[1]=r1, sp[2]=r2, sp[3]=r3
       sp[4]=r12, sp[5]=lr, sp[6]=pc, sp[7]=xpsr */
    volatile uint32_t r0   = sp[0];
    volatile uint32_t pc   = sp[6];
    volatile uint32_t xpsr = sp[7];
    (void)r0; (void)pc; (void)xpsr;
    /* Log veya breakpoint */
    __BKPT(0);
    while (1) {}
}
```

---

## Hızlı Başvuru: M0 vs M3/M4/M7 Farkları

| Özellik | M0/M0+ | M3/M4/M7 |
|---------|--------|----------|
| Instruction width | 16-bit only | 16+32 bit (Thumb-2) |
| Conditional exec | Branch only | IT block + branches |
| Hardware divide | Yok (software) | SDIV/UDIV |
| CLZ/RBIT | Yok | Var |
| Bit field (UBFX/BFI) | Yok | Var |
| LDREX/STREX | Yok | Var |
| IT blocks | Yok | Var |
| Register restrictions | r0-r7 çoğunda | r0-r15 |
| BASEPRI | Yok | Var |
| MPU | Opsiyonel | Var |

**M0 modulo trick (hardware divide yok):**
```asm
@ r0 = r0 % 8 (2^n için AND)
and r0, r0, #7

@ r0 = r0 % 10 (arbitrary — software div gerekir)
@ GCC __aeabi_idivmod() çağırır → birkaç yüz cycle
```
