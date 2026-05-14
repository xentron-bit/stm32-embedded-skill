# C Code Style — Embedded / STM32

## Kaynaklar

| Kod | Kaynak | Versiyon |
|-----|--------|----------|
| **M** | [MaJerle/c-code-style](https://github.com/MaJerle/c-code-style) | 2024 |
| **B** | BARR-C: 2018 (Michael Barr, Barr Group) | 2018 |
| **Q** | QuantumLeaps QL-C/C++ Coding Standard | 2022 |
| **N** | NASA/GSFC SEL-94-003 "C Style Guide" | 1994 |
| **E** | ESCR — C, IPA/SEC Japan, Ver 3.0 | 2018 |
| **O** | OpenTitan C/C++ Style Guide (Google/lowRISC) | 2024 |

> Çakışan kurallar için bkz: [§XII Kaynak Uzlaştırma Tablosu](#xii-kaynak-uzla%C5%9Ft%C4%B1rma)

---

## HIZLI INDEX

| Bölüm | Konu | Kaynaklar |
|-------|------|-----------|
| [I. Biçimlendirme](#i-bi%C3%A7imlendirme) | Girintileme, boşluk, satır uzunluğu | M B |
| [I.a Süslü Parantez Stili ⚠](#ia-s%C3%BCsl%C3%BC-parantez-stili) | **UYARI: MaJerle vs BARR-C çakışması** | M B |
| [II. Tipler ve Değişkenler](#ii-tipler-ve-de%C4%9Fi%C5%9Fkenler) | stdint.h, float, volatile, struct | M B N |
| [II.a `volatile` Kuralları](#iia-volatile-kurallar%C4%B1) | ISR/thread/MMIO için zorunlu | B M |
| [II.b Float Politikası](#iib-float-politikas%C4%B1) | float32_t, isfinite, equality | B |
| [II.c bool Politikası ⚠](#iic-bool-politikas%C4%B1) | **UYARI: stdbool.h kullanımı çakışması** | M B |
| [III. İsimlendirme](#iii-i%CC%87simlendirme) | Fonksiyon, değişken, makro, modül prefix | M B Q |
| [IV. Fonksiyonlar](#iv-fonksiyonlar) | Boyut, dönüş, static, inline | M B N |
| [V. Yapılar ve Enum](#v-yap%C4%B1lar-ve-enum) | Typedef, padding, C99 init | M B |
| [VI. Makrolar ve Önişlemci](#vi-makrolar-ve-%C3%B6ni%C5%9Flemci) | Güvenli makro, inline tercih | M B |
| [VII. Bellek Yönetimi](#vii-bellek-y%C3%B6netimi) | Dinamik bellek politikası, pool | N Q |
| [VIII. Kontrol Akışı](#viii-kontrol-ak%C4%B1%C5%9F%C4%B1) | goto, break, bounded loop, switch | M B N E |
| [IX. Hata Yönetimi](#ix-hata-y%C3%B6netimi) | Return kod, assert, guard clause | M B O |
| [X. Dosya Organizasyonu](#x-dosya-organizasyonu) | Header/source yapısı, include sırası | M B N |
| [XI. Yorumlar](#xi-yorumlar) | Doxygen, NASA prolog, BARR-C marker | M B N |
| [XII. Taşınabilirlik](#xii-ta%C5%9F%C4%B1nabilirlik) | Endian, tip boyutu, shift | N B E |
| [XIII. Kaynak Uzlaştırma](#xiii-kaynak-uzla%C5%9Ft%C4%B1rma) | Çakışan kural reconciliation tablosu | — |
| [XIV. Master Kontrol Listesi](#xiv-master-kontrol-listesi) | Tüm kaynaklardan birleşik checklist | — |

---

## I. Biçimlendirme

### Araç: clang-format

Projeye `.clang-format` ekle, IDE'de kayıt sonrası otomatik formatla.
MaJerle hazır config: `https://github.com/MaJerle/c-code-style`

```c
/* Tab yok — 4 boşluk [M B Q] */
/* C11 standardı tercih edilir; C99 kabul edilir [M O] */

/* Keyword ve parantez arasında 1 boşluk [M B] */
if (cond) {}      /* DOĞRU */
if(cond)  {}      /* YANLIŞ */

/* Fonksiyon adı ve parantez: boşluk yok [M B] */
int32_t a = sum(4, 3);    /* DOĞRU */
int32_t a = sum (4, 3);   /* YANLIŞ */

/* Operatörler etrafında 1 boşluk [M B] */
a = 3 + 4;     /* DOĞRU */
a=3+4;         /* YANLIŞ */

/* Satır uzunluğu: 80 karakter tercih [B N]; 100 karakter maks [M O] */

/* LF satır sonu; CRLF kullanma [B §3.6] */
/* Windows'ta .gitattributes: text=auto eol=lf */
```

### I.a Süslü Parantez Stili

> **⚠ UYARI — Kaynak çakışması:** MaJerle aynı satır kullanır; BARR-C ayrı satır ister.
> Proje başında tek bir stil seçip sabit kal. Bu dosyada **MaJerle stili** esas alınmıştır.

```c
/* MaJerle: açan parantez keyword ile AYNI SATIRDA [M] */
for (size_t i = 0; i < 10; ++i) {
    do_work();
}

/* BARR-C §1.3: açan parantez YENİ SATIRDA [B] */
for (size_t i = 0; i < 10; ++i)
{
    do_work();
}

/* Her iki stilde de: else kapanan parantez ile aynı satırda [M B] */
if (a) {
    do_a();
} else if (b) {
    do_b();
} else {
    do_c();
}

/* Her iki stilde de: TEK SATIR BILE SÜSlü PARANTEZ ZORUNLU [M B] */
if (cond) { do_a(); }     /* DOĞRU */
if (cond) do_a();         /* YANLIŞ */

/* Boş loop gövdesi [M] */
while (!ready) {}         /* DOĞRU */
while (!ready);           /* YANLIŞ */
```

---

## II. Tipler ve Değişkenler

### stdint.h Tipleri [M B §5.2 N E]

```c
/* Her zaman stdint.h tipleri kullan */
uint8_t  byte;
uint16_t word;
uint32_t dword;
int32_t  signed_val;
size_t   length;      /* boyut ve offset için */

/* YASAK: belirsiz boyutlu tipler */
int    x;     /* YANLIŞ — platform bağımlı boyut */
short  y;     /* YANLIŞ [B §5.2] */
long   z;     /* YANLIŞ [B §5.2] */
unsigned int u; /* YANLIŞ */

/* char: YALNIZCA string için [B §5.2] */
char name[32];          /* DOĞRU — string buffer */
char c = 'A';           /* DOĞRU — char literal */
uint8_t byte_val;       /* DOĞRU — byte verisi için, char değil */

/* İşaretsiz sabitlere u/U suffix [B §5.3] */
uint32_t mask = 0xFF00U;    /* DOĞRU */
uint32_t mask2 = 0xFF00;    /* YANLIŞ — signed literal [B] */

/* Signed + unsigned karıştırma [B §5.3 E] */
int32_t  a = -1;
uint32_t b = 10U;
if (a < (int32_t)b) { }  /* DOĞRU — cast ile aynı tipe getir */
if (a < b) { }            /* YANLIŞ — implicit conversion [B E] */

/* Bitwise işlem: signed tipe YASAK [B §5.3] */
int32_t x = some_val;
uint32_t masked = (uint32_t)x & 0xFFU;  /* DOĞRU — önce cast */
uint32_t bad = x & 0xFFU;               /* YANLIŞ [B] */
```

### Değişken Bildirimi [M B]

```c
/* static global: init fonksiyonunda başlat (custom section sorunu) [M] */
static int32_t a;
static int32_t b;

void module_init(void) {
    a = 0;
    b = 4;
}

/* Lokal: bloğun başında bildir [M B §5.x] */
void foo(void) {
    my_struct_t s;      /* struct/enum önce */
    uint32_t    a;      /* geniş unsigned */
    int32_t     b;
    uint16_t    c;
    char        d;
    float32_t   f;      /* float en sonda */

    a = bar();
    /* ↑ Buradan sonra yeni değişken bildirme [B] */
}

/* Pointer: asterisk tipe yapışık [M]; veya isme yapışık [B] */
/* Proje içinde tek stil seç */
char* ptr;           /* MaJerle tarzı */
char *ptr;           /* BARR-C tarzı */
char *p, *q;         /* Multi-pointer: her birine asterisk [M B] */

/* const doğru kullanımı */
void send(const void* data, size_t len);          /* data değiştirilmeyecek */
void send(const void* const data, size_t len);    /* ptr de değişmeyecek */

/* VLA: YASAK [M B O N] */
void foo(size_t n) {
    int32_t arr[n];   /* YANLIŞ — stack taşması riski */
}
```

### II.a `volatile` Kuralları [B §1.8 M]

> **KRİTİK:** volatile eksikliği -O2/-Os'ta sessizce bozulur. Derleyici uyarmaz.

```c
/* volatile ZORUNLU: ISR ile paylaşılan değişken */
volatile uint32_t g_rx_count;
void USART1_IRQHandler(void) { ++g_rx_count; }

/* volatile ZORUNLU: thread-shared değişken (RTOS) */
volatile bool g_shutdown_req;

/* volatile ZORUNLU: MMIO (donanım register pointer) [B §1.8] */
volatile uint32_t* const TIM2_CNT = (volatile uint32_t*)0x40000024UL;
/* CMSIS: __IO = volatile — zaten tanımlı, ekstra volatile gerekmez */

/* volatile ZORUNLU: derleyicinin optimize edeceği delay loop */
static volatile uint32_t dummy;
for (volatile uint32_t i = 0; i < 1000U; ++i) { dummy = i; }
/* Daha iyi: DWT cycle counter kullan */

/* volatile YANLIŞ: DMA buffer [B — cache/barrier gerekli, volatile değil] */
/* ↓ Bu yanlış — performance kaybı, cache sorununu çözmez */
volatile uint8_t dma_buf[256];
/* DOĞRU: SCB_CleanDCache / SCB_InvalidateDCache kullan */
__attribute__((aligned(32))) uint8_t dma_buf[256];

/* Multi-byte shared struct: volatile + critical section [B] */
typedef struct { uint32_t timestamp; uint16_t data; } sensor_t;
volatile sensor_t g_sensor;  /* volatile: struct erişimi atomik değil */
/* Okurken: __disable_irq() + memcpy + __enable_irq() */
```

### II.b Float Politikası [B §5.4]

```c
/* BARR-C: float32_t ve float64_t kullan (typedef float/double) */
/* Projede typedef yoksa: bare float/double kabul edilir ama belge */
typedef float  float32_t;
typedef double float64_t;

/* Float EŞITLIK TESTİ: YASAK [B §5.4 M N] */
float32_t f = compute();
if (f == 3.14f)   { }    /* YANLIŞ — floating point representation */
if (f != 0.0f)    { }    /* YANLIŞ */

/* DOĞRU: epsilon karşılaştırma */
#define FLOAT_EPS  1e-6f
if (fabsf(f - 3.14f) < FLOAT_EPS) { }   /* DOĞRU */
if (f > FLOAT_EPS) { }                   /* DOĞRU — sıfır kontrolü */

/* NaN/Inf: isfinite() ile kontrol [B §5.4] */
#include <math.h>
float32_t result = heavy_compute();
if (!isfinite(result)) {
    /* hata yönetimi */
}
```

### II.c bool Politikası [⚠ çakışma]

> **⚠ UYARI:** MaJerle stdbool.h kullanmaz; BARR-C §5.6 stdbool.h kullanımını zorunlu tutar.
> Proje başında tek strateji seç.

```c
/* MaJerle stili: stdbool.h kullanma, uint8_t kullan [M] */
uint8_t is_ready = 0U;    /* false */
uint8_t is_ready = 1U;    /* true */

/* BARR-C §5.6 stili: stdbool.h kullan */
#include <stdbool.h>
bool is_ready = false;
bool is_active = true;

/* Her iki stilde de: boolean test [M B] */
if (is_ready)       { }   /* DOĞRU */
if (!is_ready)      { }   /* DOĞRU */
if (is_ready == 1)  { }   /* YANLIŞ — boolean'ı 1 ile test etme */

/* Sayısal değişkeni boolean gibi kullanma [M B] */
uint32_t count = get_count();
if (count > 0U)     { }   /* DOĞRU */
if (count)          { }   /* YANLIŞ [M] */

/* Pointer NULL kontrolü: açık karşılaştırma [M B E] */
if (ptr != NULL)    { }   /* DOĞRU */
if (ptr == NULL)    { }   /* DOĞRU */
if (ptr)            { }   /* YANLIŞ [M B] */
if (!ptr)           { }   /* YANLIŞ [M B] */
```

---

## III. İsimlendirme [M B §6.1 Q]

```c
/* Modül prefix — tüm public sembollerde zorunlu [M B §6.1 Q] */
/* Format: <module>_<noun/verb> */
int32_t  can_init(const can_cfg_t *cfg);
void     can_tx(uint32_t id, const uint8_t *data, uint8_t len);
uint32_t can_get_error_count(void);

/* Private (static) fonksiyon: prv_ prefix [M] veya module prefix [B] */
static void prv_reset_fifo(void);          /* MaJerle */
static void can_reset_fifo_internal(void); /* BARR-C tarzı */

/* Değişken isimleri: küçük harf + alt çizgi [M B Q] */
uint32_t frame_count;
uint8_t  rx_buffer[64];

/* Makro ve enum üyeleri: BÜYÜK HARF + alt çizgi [M B §6.1] */
#define CAN_MAX_DLC      8U
#define UART_BAUD_115200 115200UL
typedef enum { CAN_STATE_IDLE, CAN_STATE_TX, CAN_STATE_ERROR } can_state_t;

/* İsim uzunluğu: maks 31 karakter [B §6.1] */
/* (C standardı 63'e izin verir ama BARR-C 31'de tutar — linker uyumu) */
uint32_t can_frame_reception_error_count; /* YANLIŞ — 33 karakter */
uint32_t can_rx_err_cnt;                  /* DOĞRU */

/* Typedef suffix kuralları [M B] */
/* _t: struct/enum/typedef tipler */
typedef struct { ... } can_frame_t;
/* _fn: function pointer typedef */
typedef void (*uart_rx_cb_fn)(uint8_t byte, void *ctx);

/* Global değişken: g_ prefix tercih edilir [B Q] */
static volatile uint32_t g_rx_count;

/* QuantumLeaps OOP tarzı (C'de nesne yönelimli) [Q] */
/* Format: Module_method(instance, ...) */
void CAN_init(CAN_t *const me, const CAN_cfg_t *cfg);
void CAN_send(CAN_t *const me, uint32_t id, const uint8_t *data);
```

---

## IV. Fonksiyonlar [M B §6.2 N]

```c
/* Return type AYRI SATIRDA [M] */
int32_t
my_function(int32_t a, int32_t b) {
    return a + b;
}

/* static: modül-private fonksiyon [M B §6.2] */
static int32_t
prv_validate_cfg(const can_cfg_t *cfg) {
    if (cfg == NULL) { return -1; }
    return 0;
}

/* Fonksiyon boyutu [B §6.2 N] */
/* BARR-C: maks 60 satır (2 sayfa) */
/* NASA:   maks 60 satır (bir kağıt parçasına sığsın) */
/* MaJerle: sınır yok ama küçük tut */

/* Tek çıkış noktası (single exit): BARR-C tercih eder [B §6.2] */
/* NASA: mandatory (MISRA benzeri) */
/* MaJerle: guard clause tercih eder */

/* Guard clause tarzı [M O] — geliştirme hızı için uygun */
int32_t can_tx(const uint8_t *data, uint8_t len) {
    if (data == NULL)    { return CAN_ERR_NULL;  }
    if (len == 0U)       { return CAN_ERR_LEN;   }
    if (len > CAN_MAX_DLC) { return CAN_ERR_LEN; }
    /* ana mantık */
    return CAN_OK;
}

/* Tek exit tarzı [B N] — safety-critical için */
int32_t can_tx(const uint8_t *data, uint8_t len) {
    int32_t result = CAN_OK;
    if (data == NULL || len == 0U || len > CAN_MAX_DLC) {
        result = CAN_ERR_PARAM;
    }
    if (result == CAN_OK) {
        /* ana mantık */
    }
    return result;  /* tek return */
}

/* Void döndüren fonksiyon: açık prototype [M B] */
void can_reset(void);     /* DOĞRU — parametre yoksa void yaz */
void can_reset();         /* YANLIŞ — K&R tarzı */

/* void* cast etme [M] */
uint8_t *ptr = get_buffer();         /* DOĞRU — void* promote otomatik */
uint8_t *ptr = (uint8_t*)get_buffer(); /* YANLIŞ */

/* inline: fonksiyon benzeri makro yerine [B §6.3] */
static inline uint16_t swap16(uint16_t v) {
    return (uint16_t)((v << 8U) | (v >> 8U));
}
/* Makro DEĞİL: */
#define SWAP16(v) (((v) << 8) | ((v) >> 8))  /* YANLIŞ [B §6.3] */
```

### Karmaşıklık Limiti [N Q E]

```c
/* McCabe Cyclomatic Complexity: NASA ≤ 10, QuantumLeaps ≤ 10 */
/* Her if/else if/while/for/case = +1, başlangıç = 1 */

/* Complexity 8 — OK */
int32_t parse_frame(const uint8_t *buf, uint16_t len, frame_t *out) {
    if (buf == NULL || out == NULL) { return -1; }  /* +2 */
    if (len < 4U)                   { return -2; }  /* +1 */
    uint16_t payload_len;
    memcpy(&payload_len, &buf[2], 2U);
    if (payload_len > MAX_PAYLOAD)  { return -3; }  /* +1 */
    if (buf[0] == 0x10U) {          /* +1 */
        if (payload_len > 7U) { out->type = FF; }   /* +1 */
        else                  { out->type = SF; }
    } else if (buf[0] == 0x21U) { out->type = CF; } /* +1 */
    else { return -4; }
    return 0;
}
/* Complexity = 1+7 = 8 → OK */
/* > 10 → fonksiyonu böl */
```

---

## V. Yapılar ve Enum [M B §5.5]

```c
/* Typedef + struct: _t suffix [M B] */
typedef struct {
    uint32_t id;
    uint8_t  dlc;
    uint8_t  data[8];
    uint8_t  _pad[3];   /* explicit padding — implicit'den daha iyi [B §5.5] */
} can_frame_t;

/* Compile-time boyut kontrolü — ZORUNLU [B §5.5 O] */
_Static_assert(sizeof(can_frame_t) == 16U, "can_frame_t size mismatch");

/* Struct padding analizi [B §5.5] */
/* KÖTÜ: derleyici gizli padding ekler */
typedef struct {
    uint8_t  cmd;     /* +0 */
    /* 3 byte implicit padding */
    uint32_t addr;    /* +4 */
    uint16_t len;     /* +8 */
    /* 2 byte implicit padding */
} bad_packed_t;       /* sizeof = 12, beklenen = 7 */

/* İYİ: büyükten küçüğe sırala */
typedef struct {
    uint32_t addr;    /* +0 */
    uint16_t len;     /* +4 */
    uint8_t  cmd;     /* +6 */
    uint8_t  _pad;    /* +7 — açık padding */
} good_t;             /* sizeof = 8 */

/* Wire protocol struct: __attribute__((packed)) + _Static_assert [M B E] */
typedef struct __attribute__((packed)) {
    uint8_t  cmd;
    uint32_t addr;    /* packed: unaligned — memcpy ile oku! */
    uint16_t len;
} wire_pkt_t;
_Static_assert(sizeof(wire_pkt_t) == 7U, "wire_pkt_t must be 7 bytes");

/* packed struct'tan alan okuma: memcpy zorunlu [B N] */
uint32_t get_addr(const wire_pkt_t *p) {
    uint32_t v;
    memcpy(&v, &p->addr, sizeof(v));
    return v;
}

/* Enum: her zaman default case [M B] */
typedef enum {
    CAN_STATE_IDLE  = 0,
    CAN_STATE_TX    = 1,
    CAN_STATE_ERROR = 2,
} can_state_t;

/* C99 designated init: HER ZAMAN kullan [M B] */
can_frame_t frame = {
    .id   = 0x100U,
    .dlc  = 8U,
    .data = {0},
    ._pad = {0},
};
```

---

## VI. Makrolar ve Önişlemci [M B §6.3]

```c
/* Makro isimleri: BÜYÜK HARF + alt çizgi [M B] */
#define MAX_NODES       10U
#define IWDG_TIMEOUT_MS 2700U

/* Fonksiyon benzeri makro: HER parametre çift parantez [M B §6.3] */
#define MIN(x, y)         ((x) < (y) ? (x) : (y))
#define SET_BIT(reg, bit) ((reg) |= (1UL << (bit)))
#define CLR_BIT(reg, bit) ((reg) &= ~(1UL << (bit)))

/* Çok satırlı makro: do { } while(0) [M B §6.3] */
#define INIT_ALL() do {  \
    module_a_init();     \
    module_b_init();     \
} while (0)              /* noktalı virgülsüz — çağıran ekler */

/* BARR-C §6.3: fonksiyon benzeri makro YERINE inline tercih [B §6.3] */
/* Makro: tip güvensiz, yan etki riski, debug zorluğu */
static inline uint32_t min_u32(uint32_t x, uint32_t y) { return (x < y) ? x : y; }
/* ↑ Bunun gibi inline kullan, makro değil */

/* Makro yan etki tehlikesi [B §6.3] */
#define SQUARE(x) ((x) * (x))       /* tehlikeli */
int a = 3;
int r = SQUARE(a++);   /* a iki kez artıyor: UB */

/* Conditional compile: her satıra yorum [M] */
#ifdef ENABLE_CAN
    can_init();
#else /* ENABLE_CAN */
    /* CAN devre dışı */
#endif /* ENABLE_CAN */

/* Çıktısız makro: explict empty [M] */
#define DEBUG_LOG(x)    /* release build: no-op */

/* Magic number yasağı [M B N] */
#define UART_BAUD      115200UL    /* DOĞRU */
uint32_t baud = 115200UL;          /* YANLIŞ — magic number */
```

---

## VII. Bellek Yönetimi [N Q M B O]

### Dinamik Bellek Politikası

> **NOT:** NASA/QuantumLeaps safety-critical standartları `malloc/free`'yi tamamen yasaklar.
> Ancak bazı projelerde (middleware, embedded Linux, RTOS heap) kontrolü dinamik
> bellek kaçınılmazdır. Aşağıdaki kurallar **kontrollü kullanım** için geçerlidir.

```c
/* Kategori A: Safety-critical / deterministic gereken sistemler */
/* malloc/free/realloc: YASAK [N Q MISRA-C] */
/* Neden: fragmantasyon, belirsiz latans, leak riski */
/* → Static pool allocator kullan (aşağıda) */

/* Kategori B: Middleware / OS bazlı / başlatma fazı */
/* Kontrollü dinamik bellek: izin verilir, şu koşullarla: */
/*   1. Sadece başlatma fazında alloc (runtime'da serbest bırakma yok) */
/*   2. NULL kontrolü her zaman zorunlu */
/*   3. Allocation başarısızlığı için tanımlı recovery */
/*   4. Leak detection (valgrind, ASAN) ile test edilmiş */

/* DOĞRU — başlatma fazında alloc, sonra serbest bırakma yok */
void system_init(void) {
    g_rx_buf = malloc(RX_BUF_SIZE);
    if (g_rx_buf == NULL) {
        system_fatal_error(ERR_ALLOC_FAIL);  /* tanımlı recovery */
        return;
    }
    memset(g_rx_buf, 0, RX_BUF_SIZE);
}

/* DOĞRU — runtime alloc+free (Kategori B): NULL kontrolü zorunlu */
uint8_t *buf = malloc(len);
if (buf == NULL) {
    return ERR_NO_MEMORY;     /* ZORUNLU — assert değil, return */
}
/* ... kullan ... */
free(buf);
buf = NULL;    /* ZORUNLU: dangling pointer engelle */

/* YANLIŞ — NULL kontrolsüz [N O B] */
uint8_t *buf = malloc(len);
memcpy(buf, src, len);    /* YANLIŞ — NULL crash */

/* YANLIŞ — serbest bıraktıktan sonra kullanma [N] */
free(buf);
buf[0] = 0;   /* YANLIŞ — use-after-free */
```

### Static Pool Allocator [N §6.3]

```c
/* NULL dönemez garanti gerektiğinde: sabit boyutlu pool */
#define POOL_COUNT   8U
#define POOL_BUF_SZ  256U

typedef struct {
    uint8_t  mem[POOL_BUF_SZ];
    bool     used;
} pool_slot_t;

static pool_slot_t pool[POOL_COUNT];

uint8_t *pool_alloc(void) {
    for (size_t i = 0U; i < POOL_COUNT; ++i) {
        if (!pool[i].used) {
            pool[i].used = true;
            return pool[i].mem;
        }
    }
    return NULL;    /* pool doldu — caller handle eder */
}

void pool_free(uint8_t *ptr) {
    if (ptr == NULL) { return; }
    for (size_t i = 0U; i < POOL_COUNT; ++i) {
        if (pool[i].mem == ptr) {
            pool[i].used = false;
            return;
        }
    }
    /* ptr pool'a ait değil — hata loga yaz */
}
```

### Özyineleme Yasağı [N Q]

```c
/* Stack derinliği belirsiz — özyineleme yasak [N safety-critical] */
/* İteratif form her zaman kullan */

/* YANLIŞ */
uint32_t crc32_rec(const uint8_t *data, size_t len, uint32_t crc) {
    if (len == 0U) { return crc; }
    return crc32_rec(data + 1U, len - 1U, update_crc(crc, *data)); /* YANLIŞ */
}

/* DOĞRU — loop */
uint32_t crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFUL;
    for (size_t i = 0U; i < len; ++i) {
        crc = update_crc(crc, data[i]);
    }
    return crc ^ 0xFFFFFFFFUL;
}
```

---

## VIII. Kontrol Akışı [M B N E]

### Bounded Loop Zorunluluğu [N B E]

```c
/* Her döngünün açık iteration limiti olmalı [N §6.4 E MISRA-C Rule 14.2] */

/* YANLIŞ — sınırsız loop */
while (HAL_I2C_GetState(&hi2c1) == HAL_I2C_STATE_BUSY) {}

/* DOĞRU — timeout ile bounded [N E] */
uint32_t timeout = 1000U;
while (HAL_I2C_GetState(&hi2c1) == HAL_I2C_STATE_BUSY) {
    if (timeout-- == 0U) {
        return ERR_TIMEOUT;
    }
    HAL_Delay(1U);
}

/* For loop: maks iteration sabit olmalı [N] */
for (size_t i = 0U; i < MAX_RETRIES; ++i) {
    if (try_send() == OK) { break; }
}
```

### goto Politikası [N B E]

```c
/* NASA: goto yalnızca fonksiyon sonundaki tek cleanup label'a [N §6.5] */
/* BARR-C §8.x: goto YASAK [B] */
/* ESCR: goto YASAK [E MISRA-C Rule 15.1] */
/* MaJerle: goto kullanma */
/* OpenTitan: goto YASAK [O] */

/* Sonuç: goto YASAK. Alternatif: do-while(0) + break pattern */

/* DOĞRU — NASA cleanup goto (tek exit için) */
int32_t process(handle_t *h) {
    int32_t rc = ERR_NONE;
    if (open_resource(h) != OK) { rc = ERR_OPEN; goto cleanup; }
    if (lock_resource(h) != OK) { rc = ERR_LOCK; goto cleanup; }
    rc = do_work(h);
cleanup:
    close_resource(h);
    return rc;
}

/* DOĞRU — goto'suz alternatif: do-while(0) + break */
int32_t process2(handle_t *h) {
    int32_t rc = ERR_NONE;
    do {
        if (open_resource(h) != OK) { rc = ERR_OPEN;  break; }
        if (lock_resource(h) != OK) { rc = ERR_LOCK;  break; }
        rc = do_work(h);
    } while (0);
    close_resource(h);
    return rc;
}
```

### break ve continue [N B E]

```c
/* break: switch'te ZORUNLU (fallthrough belgelenmedikçe) [M B N] */
/* break: loop içinde minimal kullan [N] */
/* continue: kaçın [N]; BARR-C/ESCR yasak [B E] */

/* DOĞRU — break with structured exit */
for (size_t i = 0U; i < MAX; ++i) {
    if (found(i)) {
        result = i;
        break;    /* acceptable: early exit */
    }
}

/* DOĞRU — continue'suz yeniden yazım */
for (size_t i = 0U; i < MAX; ++i) {
    if (!should_skip(i)) {    /* inverted condition — no continue */
        process(i);
    }
}
```

### Switch [M B]

```c
switch (state) {
    case CAN_STATE_IDLE: {
        /* Lokal değişken için blok açılabilir [M] */
        uint32_t ts = HAL_GetTick();
        handle_idle(ts);
        break;
    }
    case CAN_STATE_TX:
        handle_tx();
        break;
    case CAN_STATE_ERROR:
        handle_error();
        /* FALLTHROUGH */    /* intentional: yorum zorunlu [B N] */
    case CAN_STATE_BUSOFF:
        reset_can();
        break;
    default:
        /* MUTLAKA default [M B N] */
        log_warn(WARN_UNEXPECTED_STATE);
        break;
}
```

---

## IX. Hata Yönetimi [M B O N]

```c
/* Hata kodu dönüş: int32_t tercih; enum ya da define [M B] */
typedef enum {
    ERR_NONE    =  0,
    ERR_PARAM   = -1,
    ERR_TIMEOUT = -2,
    ERR_BUSY    = -3,
} can_err_t;

/* Her fonksiyon dönüş değerini kontrol et [N O E] */
int32_t rc = can_tx(buf, len);
if (rc != ERR_NONE) {
    log_error(rc);
    return rc;   /* hatayı ilet — swallow etme */
}
/* (void)rc; — return değeri bilinçli görmezden geliniyorsa */

/* Assert: invariant / program logic hatası için [B O] */
/* Dış veri veya runtime hata için assert kullanma */
void can_tx_dma(const uint8_t *buf, size_t len) {
    assert(buf != NULL);           /* iç invariant — bu fonksiyon null almamalı */
    assert(len <= CAN_MAX_DLC);    /* caller garantisi */
    /* ... */
}

/* Dış veri: assert değil, return kod [B O] */
int32_t can_tx_api(const uint8_t *buf, size_t len) {
    if (buf == NULL || len == 0U) { return ERR_PARAM; }   /* DOĞRU */
    return ERR_NONE;
}

/* OpenTitan: HARDENED_CHECK_EQ / CHECK macro kullanımı [O] */
/* Embedded eşdeğeri: */
#define ASSERT_MSG(cond, msg)   \
    do { if (!(cond)) { log_fatal(msg); system_halt(); } } while(0)
```

---

## X. Dosya Organizasyonu [M B §4.3 N]

### Header Dosyası

```c
/* my_module.h */
#ifndef MY_MODULE_H        /* include guard [M B] */
#define MY_MODULE_H        /* ifndef/define/endif — #pragma once değil [B] */

#ifdef __cplusplus         /* C++ uyumluluk [M] */
extern "C" {
#endif

/* BARR-C §4.3 Header sırası: [B §4.3] */
/* 1. System includes */
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>   /* veya projede typedef bool */

/* 2. Local includes */
#include "platform.h"

/* 3. Public macros */
#define MY_MODULE_VERSION  1U

/* 4. Public types */
typedef struct {
    uint32_t baud;
    uint8_t  mode;
} my_module_cfg_t;

/* 5. Public function prototypes — hizalı [M] */
int32_t  my_module_init(const my_module_cfg_t *cfg);
void     my_module_process(void);
uint32_t my_module_get_status(void);

#ifdef __cplusplus
}
#endif

#endif /* MY_MODULE_H */
```

### Source Dosyası

```c
/* my_module.c */

/* BARR-C §4.3 Source sırası: [B §4.3] */
/* 1. File prolog (NASA formatında) */
/* 2. Kendi header'ı ÖNCE — include sırası self-contained test [M B] */
#include "my_module.h"

/* 3. System includes */
#include <string.h>

/* 4. Local includes */
#include "can.h"

/* 5. Private macros */
#define PRV_TIMEOUT_MS  100U

/* 6. Private types */
typedef struct { uint32_t ts; bool active; } prv_state_t;

/* 7. Private variables */
static prv_state_t prv_state;
static uint32_t    g_error_count;

/* 8. Private function declarations */
static void     prv_reset(void);
static int32_t  prv_validate(const my_module_cfg_t *cfg);

/* 9. Public function implementations */
int32_t
my_module_init(const my_module_cfg_t *cfg) {
    if (prv_validate(cfg) != 0) { return -1; }
    prv_reset();
    return 0;
}

/* 10. Private function implementations */
static void
prv_reset(void) {
    prv_state.active = false;
    prv_state.ts     = 0U;
}

static int32_t
prv_validate(const my_module_cfg_t *cfg) {
    if (cfg == NULL) { return -1; }
    if (cfg->baud == 0U) { return -2; }
    return 0;
}
```

---

## XI. Yorumlar [M B §2.2 N]

### BARR-C İşaretçileri [B §2.2]

```c
/* WARNING: buradaki sıra önemli — GPIO'dan önce clock aktif olmalı */
/* NOTE: bu register H7 Rev V'de değişti, eski silicon'da farklı davranır */
/* TODO: DMA mode ekle, şu an polling */
/* FIXME: bus-off recovery eksik */
```

### Doxygen Kuralları [B §2.2 M]

```c
/**
 * @brief Kısa açıklama (tek satır).
 *
 * Gerekirse uzun açıklama. WHY açıkla, WHAT değil.
 *
 * @param[in]  cfg    Yapılandırma (NULL değil)
 * @param[out] status Durum çıktısı (NULL geçilebilir)
 * @return     ERR_NONE başarı; negatif: hata kodu
 *
 * @note Bu fonksiyon task bağlamında çağrılmalı, ISR'dan değil.
 */
int32_t can_init(const can_cfg_t *cfg, uint32_t *status);
```

### NASA Prolog Şablonu [N §5.1]

```c
/******************************************************************************
 * FILE: can_driver.c
 *
 * DESCRIPTION:
 *   FDCAN driver for STM32H7. ISO 11898 compliant, MISRA-C 2012 aware.
 *   Handles TX/RX via interrupt; bus-off recovery is application-controlled.
 *
 * AUTHOR:    <name>
 * CREATED:   YYYY-MM-DD
 * MODIFIED:  YYYY-MM-DD — <change description>
 *
 * COPYRIGHT: (c) <year> <organization>. All rights reserved.
 ******************************************************************************/
```

### NASA Yorum Tipleri [N §5.2]

```c
/*********************/ /* §5.2.1: boxed — dosya/fonksiyon başlığı */
/* normal yorum */     /* §5.2.2: block — section ayırıcı */
/* kısa açıklama */    /* §5.2.3: short — tek satır açıklama */
x = a + b; /* inline*/ /* §5.2.4: inline — satır sonu */
```

---

## XII. Taşınabilirlik [N B E]

```c
/* Tip boyutuna bağımlı olmayan kod [N §8.1] */
/* YANLIŞ */
int   flags;      /* 16-bit veya 32-bit? */
long  timestamp;  /* belirsiz */

/* DOĞRU */
uint32_t flags;
uint32_t timestamp_ms;

/* Endian güvenliği [N B E] */
/* YANLIŞ: doğrudan cast */
uint32_t val = *(uint32_t*)&buf[0];   /* alignment UB + endian varsayımı */

/* DOĞRU: byte shift ile endian-safe okuma */
static inline uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24U)
         | ((uint32_t)p[1] << 16U)
         | ((uint32_t)p[2] <<  8U)
         |  (uint32_t)p[3];
}
static inline uint32_t read_le32(const uint8_t *p) {
    return  (uint32_t)p[0]
         | ((uint32_t)p[1] <<  8U)
         | ((uint32_t)p[2] << 16U)
         | ((uint32_t)p[3] << 24U);
}

/* Arithmetic shift: imzalı tipe >> YANLIŞ [N B E] */
int32_t x = -8;
int32_t y = x >> 2;    /* YANLIŞ — implementation-defined */
int32_t y2 = x / 4;   /* DOĞRU — C standardıyla tanımlı */

/* sizeof: tip değil, değişken üzerinde [B O] */
memcpy(dst, src, sizeof(*dst));    /* DOĞRU — tip değişse bile doğru */
memcpy(dst, src, sizeof(my_t));    /* YANLIŞ — tip değişince güncellemeyi unutursun */
```

---

## XIII. Kaynak Uzlaştırma

| Konu | MaJerle (M) | BARR-C (B) | NASA (N) | QuantumLeaps (Q) | ESCR (E) | OpenTitan (O) | **Karar** |
|------|-------------|------------|----------|-----------------|----------|---------------|-----------|
| Süslü parantez | Aynı satır | Yeni satır | Belirtmez | Aynı satır | Belirtmez | Aynı satır | **Proje stili seç — sabit kal** |
| `bool` tipi | uint8_t tercih | stdbool.h zorunlu | uint8_t | uint8_t | — | stdbool.h | **Proje başında tek stil seç** |
| `goto` | Kullanma | Yasak | Cleanup label | Yasak | Yasak | Yasak | **YASAK (cleanup → do-while break)** |
| Dinamik bellek | Kaçın | Başlatmada OK | Yasak | Yasak | — | Kontrollü | **Kontrollü kullanım (Politika B)** |
| `break/continue` | OK | Continue yasak | Sınırlı | Continue yasak | Yasak | — | **continue yasak; break minimize** |
| Return tipi satırı | Ayrı satır | Ayrı satır | — | Ayrı satır | — | Ayrı satır | **Ayrı satır** |
| Fonksiyon boyutu | Küçük tut | ≤60 satır | ≤60 satır | ≤100 satır | ≤60 satır | — | **≤60 satır** |
| Makro vs inline | Makro OK | inline tercih | — | inline tercih | — | inline tercih | **inline tercih** |
| Döngü sınırı | — | Bounded | Bounded zorunlu | Bounded | Bounded zorunlu | — | **Her döngüde açık limit** |
| İsim prefix | Modül prefix | Modül prefix | — | Module_Method | Modül prefix | — | **Modül prefix zorunlu** |
| Karmaşıklık | — | — | ≤10 | ≤10 | ≤10 | — | **≤10** |

---

## XIV. Master Kontrol Listesi

### Biçimlendirme
```
□ 4 boşluk girintileme, tab yok [M B]
□ Satır sonu: LF (CR-LF değil) [B §3.6]
□ Satır uzunluğu ≤ 100 karakter [M O]
□ Açan parantez stili proje içinde tutarlı [M B]
□ Her if/for/while gövdesi süslü parantezli [M B]
□ Operatörler etrafında boşluk [M B]
```

### Tipler ve Değişkenler
```
□ stdint.h tipleri kullanıldı; int/short/long yok [M B §5.2 N]
□ İşaretsiz sabitlere u/U suffix [B §5.3]
□ float equality testi yok; epsilon kullanıldı [B §5.4]
□ ISR/thread shared değişkenlerde volatile [B §1.8]
□ DMA buffer: volatile değil, aligned(32) + cache ops [M ref-compiler-hardening]
□ MMIO pointer: __IO (CMSIS) veya volatile [B §1.8]
□ VLA yok; sabit boyutlu array [M B O N]
□ Signed+unsigned karışımı yok; cast ile çözüm [B §5.3 E]
□ Bitwise op: signed type üzerinde yok [B §5.3]
```

### İsimlendirme
```
□ Public semboller modül prefix ile başlıyor [M B Q]
□ Private static: prv_ prefix veya module prefix [M B]
□ Makrolar BÜYÜK_HARF [M B]
□ Typedef _t suffix, function pointer _fn suffix [M B]
□ İsim uzunluğu ≤ 31 karakter [B §6.1]
□ Global değişkenler g_ prefix ile [B Q]
```

### Fonksiyonlar
```
□ Fonksiyon ≤ 60 satır [B N]; karmaşıklık ≤ 10 [N Q E]
□ inline, makro yerine kullanıldı [B §6.3]
□ Void parametre: açık (void) yazıldı [M B]
□ Her fonksiyon dönüş değeri kontrol edildi [N O E]
□ Fonksiyon parametrelerinde NULL kontrolü [M B O]
□ assert: iç invariant için; return kod: dış veri için [B O]
```

### Bellek
```
□ Dinamik bellek: NULL kontrolü HER alloc sonrası [N O]
□ free sonrası ptr = NULL [N]
□ Runtime alloc politikası belirlendi (A veya B) [N Q]
□ Özyineleme yok — iteratif form [N Q]
□ Pool allocator: pool_free doğru çağrıldı [N]
```

### Kontrol Akışı
```
□ Her döngünün açık iteration limiti var [N B E]
□ goto yok — do-while(0)+break veya fonksiyon böl [M B N E O]
□ continue yok [B E]
□ switch: her case'de break veya /* FALLTHROUGH */ yorumu [M B N]
□ switch: default case var [M B N]
```

### Yapılar
```
□ _Static_assert ile struct boyut kontrolü [B §5.5 O]
□ Packed struct alanları memcpy ile okunuyor [B N]
□ C99 designated initializer kullanıldı [M B]
□ Struct üyeleri büyükten küçüğe sıralı (padding min) [B §5.5]
```

### Dosya / Yorumlar
```
□ Header guard: #ifndef / #define / #endif [M B]
□ Kendi header'ı en önce include edildi [M B]
□ Public API Doxygen yorumlu [B §2.2]
□ WARNING/NOTE/TODO marker'ları kullanıldı [B §2.2]
□ Magic number yok — macro ile tanımlı [M B N]
□ Fonksiyon karmaşıklığı comment'te belgelenmiş (≥8 ise) [N Q]
```

### Taşınabilirlik
```
□ Endian: pointer cast yok — byte shift read_be32/read_le32 [N B E]
□ sizeof değişken üzerinde (tip üzerinde değil) [B O]
□ Arithmetic shift: imzalı tip üzerinde >> yok [N B E]
□ Platform-specific kod #ifdef ile izole edilmiş [N]
```
