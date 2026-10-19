// Recursive Fibonacci: lots of calls, returns and stack traffic (JAL/JALR, LW/SW, branches).
// RV32I has no multiply, so the programs avoid '*', '/' and '%'.

#define N 15  // fib(15) = 610; the expected value is computed in tb/programs.py

static unsigned fib(unsigned n) {
    if (n < 2) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    return (int)fib(N);
}
