# C Code Style — Embedded / STM32

Kaynak: [MaJerle/c-code-style](https://github.com/MaJerle/c-code-style) — embedded geliştirmeye odaklanarak özetlenmiş.

## Araç: clang-format

Projeye `.clang-format` dosyası ekle ve IDE'de kayıt sonrası otomatik formatlamayı aç.
MaJerle'nin hazır `.clang-format` dosyasını kullan: `https://github.com/MaJerle/c-code-style`

---

## Genel Kurallar

```c
/* Tab yok — 4 boşluk */
/* C11 standardı */

/* Keyword ve parantez arasında 1 boşluk */
if (cond) {}       /* DOĞRU */
if(cond)  {}       /* YANLIŞ */

/* Fonksiyon adı ve parantez arasında boşluk yok */
int32_t a = sum(4, 3);   /* DOĞRU */
int32_t a = sum (4, 3);  /* YANLIŞ */

/* Açan süslü parantez keyword ile aynı satırda */
for (size_t i = 0; i < 10; ++i) {   /* DOĞRU */
for (size_t i = 0; i < 10; ++i)     /* YANLIŞ — ayrı satır */
{

/* Operatörler etrafında 1 boşluk */
a = 3 + 4;      /* DOĞRU */
a=3+4;          /* YANLIŞ */
```

### Yasaklar

```c
/* __ veya _ ile başlayan isim — C'ye özel, kullanma */
int __my_var;   /* YANLIŞ */
int _my_var;    /* YANLIŞ */

/* Tercih edilen prefix'ler */
static void prv_my_func(void);    /* modül-private (static) fonksiyon */
void mylib_int_helper(void);      /* kütüphane-iç, kullanıcıya açık değil */
```

---

## Tipler

```c
/* stdint.h tipleri — her zaman */
uint8_t a;      /* DOĞRU */
unsigned char a;/* Kaçın */

/* size_t — uzunluk ve boyut için */
size_t len;

/* stdbool.h kullanma — 1/0 kullan */
uint8_t is_ready = 0;  /* DOĞRU */
bool is_ready = false; /* YANLIŞ (embedded'da stdbool.h'dan kaçın) */

/* Boolean değişkeni karşılaştırma */
if (is_ready)       /* DOĞRU */
if (!is_ready)      /* DOĞRU */
if (is_ready == 1)  /* YANLIŞ — boolean'ı 1 ile karşılaştırma */
if (is_ready == 0)  /* YANLIŞ — ! kullan */

/* Counter ve sayısal değişkenler */
if (count > 0)      /* DOĞRU — sayısal, açık karşılaştır */
if (count)          /* YANLIŞ — sayısal boolean gibi kullanılmamalı */

/* Pointer NULL kontrolü */
if (ptr == NULL)    /* DOĞRU */
if (!ptr)           /* YANLIŞ — pointer'ı boolean gibi kullanma */

/* VLA (Variable Length Array) kullanma */
void foo(size_t n) {
    int32_t arr[n];  /* YANLIŞ — stack taşması riski */
}
/* Kullan: static array veya fixed-size pool */
```

---

## Değişkenler

```c
/* Kötü: global/static değişkeni bildirimde başlatma */
static int32_t a = 0;   /* YANLIŞ — startup'ta geçersiz olabilir (custom section) */
static int32_t b = 4;   /* YANLIŞ */

/* DOĞRU: init fonksiyonunda başlat */
static int32_t a;
static int32_t b;

void module_init(void) {
    a = 0;
    b = 4;
}

/* Lokal değişkenleri bloğun başında bildir */
void foo(void) {
    /* 1. önce struct/enum */
    my_struct_t s;

    /* 2. integer — geniş unsigned önce */
    uint32_t a;
    int32_t b;
    uint16_t c;
    char d;

    /* 3. float/double */
    float f;

    /* Çalıştırılabilir statement'tan sonra değişken bildirme */
    a = bar();
    int32_t x;  /* YANLIŞ */
}

/* Pointer bildirimi — asterisk tipe yapışık */
char* ptr;      /* DOĞRU */
char *ptr;      /* YANLIŞ (single pointer) */
char *p, *q;    /* DOĞRU (multiple pointer) */

/* const kullanımı */
void send(const void* data, size_t len);  /* data değiştirilmeyecek */
void send(const void* const data, size_t len); /* data ve pointer değişmeyecek */
```

---

## Fonksiyonlar

```c
/* Return type AYRI SATIRDA — MaJerle standardı */
int32_t
my_function(int32_t a, int32_t b) {
    return a + b;
}

static const char*
get_string(void) {
    return "Hello";
}

/* Dışarıdan erişilen her fonksiyonun header'da prototype'ı olmalı */
/* void * döndüren fonksiyonu cast etme */
uint8_t* ptr = func_returning_void_ptr();  /* DOĞRU — void* otomatik promote */
uint8_t* ptr = (uint8_t*)func_returning_void_ptr(); /* YANLIŞ */

/* Pointer döndüren fonksiyon — asterisk return type'a yapışık */
const char* my_func(void);      /* DOĞRU */
const char *my_func(void);      /* YANLIŞ */

/* Fonksiyon prototype hizalaması */
void        set(int32_t a);
my_type_t   get(void);
my_ptr_t*   get_ptr(void);
```

---

## Yapılar ve Enum

```c
/* Typedef ile struct — isim _t suffix'li */
typedef struct {
    uint32_t address;
    uint16_t length;
    uint8_t  flags;
} can_frame_t;

/* Typedef + name (forward declaration için) */
typedef struct can_frame {
    uint32_t address;
} can_frame_t;

/* enum — üyeler BÜYÜK HARF */
typedef enum {
    CAN_STATE_IDLE,
    CAN_STATE_TX,
    CAN_STATE_ERROR,
} can_state_t;

/* C99 başlatma — HER ZAMAN */
can_frame_t frame = {
    .address = 0x100,
    .length  = 8,
    .flags   = 0,
};                  /* trailing comma — clang-format için */

/* Function pointer typedef — _fn suffix */
typedef void (*uart_rx_cb_fn)(uint8_t byte, void* ctx);
```

---

## Bileşik İfadeler

```c
/* Her zaman süslü parantez — tek satır bile olsa */
if (cond) {
    do_a();      /* DOĞRU */
}

if (cond) do_a(); /* YANLIŞ */

/* else — kapanan parantez ile aynı satırda */
if (a) {
    do_a();
} else if (b) {   /* DOĞRU */
    do_b();
} else {
    do_c();
}

/* Boş loop — içi boş süslü parantez */
while (!HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0)) {}   /* DOĞRU */
while (!HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0));      /* YANLIŞ */

/* Loop tercihi: for > do-while > while */
for (size_t i = 0; i < len; ++i) { /* Tercih edilir */ }

/* pre-increment tercih et */
++a;    /* Tercih edilir */
a++;    /* Kaçın */
```

---

## Switch

```c
switch (state) {
    case CAN_STATE_IDLE: {
        uint32_t local_var;
        local_var = prepare();
        handle_idle(local_var);
        break;              /* break süslü içinde */
    }
    case CAN_STATE_TX:
        handle_tx();
        break;
    default:                /* MUTLAKA default */
        break;
}
```

---

## Macro ve Preprocessor

```c
/* Macro isimleri — BÜYÜK HARF + alt çizgi */
#define MAX_NODES    10
#define PI_VALUE     3.14159f

/* Fonksiyon benzeri macro — her parametre parantezli */
#define MIN(x, y)    ((x) < (y) ? (x) : (y))
#define SET_BIT(r, b) ((r) |= (1UL << (b)))

/* Çok satırlı macro — \ ile devam, son satırda yok */
#define INIT_ALL() do {    \
    module_a_init();       \
    module_b_init();       \
} while (0)

/* İçi boş macro — empty statement için */
#define DEBUG_PRINT(x)    /* nothing in release */

/* ifdef bloklarında her satıra yorum */
#ifdef ENABLE_CAN
    can_init();
#else /* ENABLE_CAN */
    /* CAN disabled */
#endif /* ENABLE_CAN */

/* Magic number'lar için macro — asla literal */
#define IWDG_RELOAD_VALUE   0x0AAAU   /* 2.7s at 32kHz LSI */
```

---

## Header / Source Dosya Organizasyonu

```c
/* my_module.h */
#ifndef MY_MODULE_H
#define MY_MODULE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>

/* Public types */
typedef struct { ... } my_module_cfg_t;

/* Public API */
int32_t my_module_init(const my_module_cfg_t* cfg);
void    my_module_process(void);

#ifdef __cplusplus
}
#endif

#endif /* MY_MODULE_H */
```

```c
/* my_module.c */
#include "my_module.h"

/* Private (module-scoped) types */
typedef struct { ... } prv_state_t;

/* Private variables */
static prv_state_t prv_state;

/* Private function declarations */
static void prv_reset(void);
static int32_t prv_validate(const my_module_cfg_t* cfg);

/* Public API implementation */
int32_t
my_module_init(const my_module_cfg_t* cfg) {
    if (prv_validate(cfg) != 0) {
        return -1;
    }
    prv_reset();
    return 0;
}

/* Private implementations */
static void
prv_reset(void) {
    /* ... */
}
```

---

## Yorum Kuralları

```c
/* Tek satır yorum — DOĞRU */
//Bu yorum — YANLIŞ, C'de // kullanma

/*
 * Çok satırlı yorum — her satır space+asterisk
 * ile başlar
 */

/**
 * Sadece Doxygen için — başka yerde çift asterisk kullanma
 */

/* 48 boşluk offset (12 indent) ile satır sonu yorumu */
uint32_t timeout_ms;                /* Milliseconds since last frame */
volatile uint8_t dma_done;          /* Set by DMA ISR on completion */
```

---

## Embedded'a Özel Eklemeler (MaJerle'ye Ek)

```c
/* Peripheral pointer — CMSIS __IO kullan, kendi volatile cast'in değil */
__IO uint32_t* reg = &TIM2->CR1;    /* DOĞRU */
volatile uint32_t* reg = (volatile uint32_t*)0x40000000; /* Kaçın */

/* ISR handler ismi — CMSIS vektörüyle eşleşmeli */
void TIM2_IRQHandler(void) { ... }  /* Tam isim */

/* Bit manipulation — named macro ile */
SET_BIT(RCC->APB1ENR, RCC_APB1ENR_TIM2EN_Pos);   /* DOĞRU */
RCC->APB1ENR |= (1 << 0);                          /* YANLIŞ — magic number */

/* Timeout pattern — HAL_MAX_DELAY asla */
HAL_I2C_Master_Transmit(&hi2c, addr, buf, len, 10); /* 10ms timeout — DOĞRU */
HAL_I2C_Master_Transmit(&hi2c, addr, buf, len, HAL_MAX_DELAY); /* YANLIŞ */

/* sizeof operatörü — her zaman parantez */
malloc(sizeof(my_struct_t));    /* DOĞRU */
malloc(sizeof my_struct_t);     /* YANLIŞ */

/* Pointer tipinden bağımsız sizeof — tip değişince boyut otomatik güncellenir */
my_struct_t* p = malloc(sizeof(*p));   /* Tercih edilir */
my_struct_t* p = malloc(sizeof(my_struct_t)); /* Çalışır ama bağımlı */
```

---

## memcpy — Güvenli Kullanım Kuralları

```c
/* KURAL 1: Her zaman hedef boyutunu kontrol et */

/* YANLIŞ — taşma garantili */
memcpy(dest_buf, src, recv_len);

/* DOĞRU */
if (recv_len > sizeof(dest_buf)) {
    log_error(ERR_OVERFLOW);
    return -1;
}
memcpy(dest_buf, src, recv_len);

/* KURAL 2: Kaynak NULL kontrolü */
if (src == NULL || dest == NULL) { return -1; }
memcpy(dest, src, len);

/* KURAL 3: Örtüşen bölge için memmove kullan */
/* memcpy ile örtüşen bölge: undefined behavior */
/* YANLIŞ */
memcpy(buf + 2, buf, 10);          /* örtüşüyor — UB */
/* DOĞRU */
memmove(buf + 2, buf, 10);         /* örtüşmeyi doğru yönetir */

/* KURAL 4: Protocol çerçevesi — sabit boyut kontrolü */
typedef struct __attribute__((packed)) {
    uint8_t  cmd;
    uint16_t len;
    uint8_t  data[MAX_PAYLOAD];
} Frame_t;

void parse_frame(const uint8_t *raw, uint16_t raw_len)
{
    /* Minimum başlık kontrolü */
    if (raw_len < offsetof(Frame_t, data)) {
        return;   /* header bile gelişmedi */
    }
    /* Payload boyut kontrolü */
    uint16_t payload_len;
    memcpy(&payload_len, &raw[1], 2);   /* misaligned read güvenli — memcpy ile */
    if (payload_len > MAX_PAYLOAD || (offsetof(Frame_t, data) + payload_len) > raw_len) {
        return;   /* menzil dışı */
    }
    Frame_t frame;
    memcpy(&frame, raw, offsetof(Frame_t, data) + payload_len);
}
```

### memcpy Tehlike Tablosu

| Durum | Risk | Çözüm |
|-------|------|-------|
| `memcpy(dst, src, user_len)` | Heap/stack taşması | `user_len > sizeof(dst)` kontrolü |
| `memcpy(buf + offset, src, n)` | `offset + n > buf_size` | İkisini birlikte kontrol et |
| `memcpy` sonrası dizi erişimi | Index dst_len'den büyük | Sadece kopyalanan `n` byte'a eriş |
| protocol field okuma | misaligned UB | `memcpy` veya `__packed` struct |
| `recv_len` negatif/wrap | `uint16_t`: 65535 → 0 overflow | unsigned comparison, `> sizeof` |

---

## Index Sınır Aşımı Analizi

### Yaygın Örüntüler ve Önlemler

```c
/* ÖRÜNTÜ 1: Dizi dizinine doğrudan DMA/CAN verisi kullanma */
void process_can_frame(const uint8_t *data)
{
    uint8_t table_idx = data[0];         /* YANLIŞ: kontrol yok */
    uint32_t val = lookup_table[table_idx];  /* → OOB read */

    /* DOĞRU */
    if (data[0] >= ARRAY_SIZE(lookup_table)) {
        return;   /* geçersiz index */
    }
    uint32_t val = lookup_table[data[0]];
}

/* ÖRÜNTÜ 2: Ring buffer index overflow */
typedef struct {
    uint8_t  buf[RING_BUF_SIZE];       /* power-of-2 boyut zorunlu */
    uint32_t head;
    uint32_t tail;
} ring_buf_t;

/* DOĞRU — mask ile güvenli index */
#define RING_BUF_SIZE 256U              /* 2^8 — mask çalışır */
#define RING_MASK     (RING_BUF_SIZE - 1U)

static inline void ring_push(ring_buf_t *r, uint8_t b)
{
    uint32_t next_head = (r->head + 1U) & RING_MASK;
    if (next_head == r->tail) { return; }   /* dolu */
    r->buf[r->head & RING_MASK] = b;
    r->head = next_head;
}

/* ÖRÜNTÜ 3: Yineleyici taşması — off-by-one */
uint8_t buf[16];
for (size_t i = 0; i <= 16; i++) {    /* YANLIŞ — i=16 OOB */
    buf[i] = 0;
}
for (size_t i = 0; i < 16; i++) {     /* DOĞRU — < değil <= */
    buf[i] = 0;
}

/* ÖRÜNTÜ 4: Negatif index — imzalı/imzasız karışımı */
int32_t offset = get_offset();         /* -1 döndürebilir */
uint8_t val = buf[offset];             /* offset negatifse → OOB */

/* DOĞRU */
if (offset < 0 || (uint32_t)offset >= sizeof(buf)) { return; }
uint8_t val = buf[(uint32_t)offset];

/* ÖRÜNTÜ 5: Çarpımda overflow — büyük indeks hesabı */
uint32_t row = user_row;
uint32_t col = user_col;
uint32_t idx = row * COLS + col;      /* YANLIŞ: row*COLS overflow edebilir */

/* DOĞRU */
if (row >= ROWS || col >= COLS) { return; }
uint32_t idx = row * COLS + col;   /* artık güvenli */
```

### Statik Analiz için Kontrol Listesi

```
□ Dizi boyutu ARRAY_SIZE(arr) macro ile doğrulandı mı?
□ Harici (CAN/UART) veri index olarak kullanılıyor → kontrol var mı?
□ Ring buffer: head/tail hiç negatif olabilir mi? (signed overflow riski)
□ Loop: < mi, <= mi? Off-by-one var mı?
□ İmzalı + imzasız karışımı var mı? (int offset → uint index)
□ Çarpım öncesi bireysel sınır kontrolü yapıldı mı?
□ memcpy len: kullanıcı/dış veriden geliyor → taşma kontrolü
□ Struct pointer casting: packed olmayan struct field'a memcpy mi?
```

---

## Timeout Kontrol Örüntüleri

```c
/* KURAL: Her peripheral çağrısında bounded timeout */

/* Genel timeout guard makrosu */
#define PERIPHERAL_TIMEOUT_MS   10U

/* I2C */
if (HAL_I2C_Master_Transmit(&hi2c1, addr, buf, len,
                              PERIPHERAL_TIMEOUT_MS) != HAL_OK) {
    /* Hata işle — sonsuz bloklama değil */
    handle_i2c_error();
    return -1;
}

/* SPI */
if (HAL_SPI_TransmitReceive(&hspi1, tx, rx, len,
                              PERIPHERAL_TIMEOUT_MS) != HAL_OK) {
    handle_spi_error();
    return -1;
}

/* DMA tamamlanma — semaphore timeout */
if (osSemaphoreAcquire(dma_done_sem, 50U) != osOK) {
    /* DMA timeout — DMA reset gerekebilir */
    HAL_DMA_Abort(&hdma_spi_rx);
    return -1;
}

/* Busy-wait gereken durum — timeout döngüsü */
uint32_t t0 = HAL_GetTick();
while (!is_device_ready()) {
    if ((HAL_GetTick() - t0) >= 100U) {   /* 100ms timeout */
        return -1;   /* cihaz yanıt vermiyor */
    }
}

/* UYARI: uint32_t wraparound güvenli — t0 > HAL_GetTick() olsa bile
 * (HAL_GetTick() - t0) unsigned wrap ile doğru farkı verir
 * (49.7 gün her ~2^32 ms, pratik sorun değil) */

/* RTOS context'te busy-wait yasak — yield et */
uint32_t deadline = osKernelGetTickCount() + 100U;
while (!is_device_ready()) {
    if (osKernelGetTickCount() >= deadline) { return -1; }
    osDelay(1U);   /* scheduler'ı serbest bırak */
}
```

---

## Özet Kontrol Listesi

```
□ .clang-format dosyası projede var mı?
□ 4 boşluk indent — tab yok
□ Tüm değişken/fonksiyon: lowercase + underscore
□ private static fonksiyon: prv_ prefix
□ Typedef struct: _t suffix; enum üyeleri: BÜYÜK
□ C99 struct init: .field = value
□ Global/static init: bildirimde değil, init fonksiyonunda
□ stdint.h tipleri — char/int yerine uint8_t/int32_t
□ stdbool.h yok — uint8_t + 0/1
□ VLA yok — static array veya pool allocator
□ void* cast yok — otomatik promote edilir
□ Pointer karşılaştırma: == NULL / != NULL
□ Boolean: if(flag) / if(!flag) — 1/0 ile karşılaştırma yok
□ Numeric counter: if(count > 0) — if(count) değil
□ Her if/else/for/while'da süslü parantez
□ else kapanan parantezle aynı satırda
□ Boş loop: while(cond) {} — noktalı virgül değil
□ Switch: her case'de break, mutlaka default
□ Return type ayrı satırda (MaJerle standardı)
□ // yorumu yok — /* */ kullan
□ Header: include guard + extern "C" + copyright
□ ISR shared vars: volatile
□ Timeout: HAL_MAX_DELAY yok — her zaman bounded
□ Magic number yok — macro kullan
□ memcpy öncesi: hedef boyutu, NULL, taşma kontrolü yapıldı mı?
□ Dış veri (CAN/UART) dizi indexi olarak: menzil kontrolü yapıldı mı?
□ Ring buffer: RING_MASK ile güvenli mi, power-of-2 boyut mu?
□ Loop: < mı, <= mı? Off-by-one analiz edildi mi?
□ İmzalı index → imzasız dizi: negatif kontrol var mı?
□ Her peripheral HAL çağrısında timeout < HAL_MAX_DELAY
□ Busy-wait: timeout döngüsü var mı?
□ RTOS context busy-wait: osDelay ile yield mi?
```
