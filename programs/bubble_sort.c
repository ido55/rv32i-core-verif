// Bubble sort of 32 pseudo-random words: nested loops, data-dependent branches, LW/SW.
// Returns a checksum of the sorted array, or 0xFFFFFFFF if the result is not sorted.
// The expected checksum is computed by a Python copy of this code (tb/programs.py).

#define N 32

static unsigned data[N];

// xorshift32 PRNG: shifts and XORs only (RV32I has no multiply).
static unsigned next_random(unsigned x) {
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return x;
}

int main(void) {
    unsigned x = 2463534242u;
    for (int i = 0; i < N; i++) {
        x = next_random(x);
        data[i] = x;
    }

    for (int i = 0; i < N - 1; i++) {
        for (int j = 0; j < N - 1 - i; j++) {
            if (data[j] > data[j + 1]) {
                unsigned tmp = data[j];
                data[j] = data[j + 1];
                data[j + 1] = tmp;
            }
        }
    }

    unsigned checksum = 0;
    for (int i = 0; i < N; i++) {
        if (i > 0 && data[i - 1] > data[i]) {
            return (int)0xFFFFFFFFu;
        }
        checksum = (checksum << 1 | checksum >> 31) ^ data[i];  // rotate-left, then XOR
    }
    return (int)checksum;
}
