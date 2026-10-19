# Reproducible build/test environment: same OS and tool versions as CI.
#   docker build -t rv32i-core-verif .
#   docker run --rm rv32i-core-verif          # runs: make lint test
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# verilator 5.020 (simulator), g++/make (build the Verilator model),
# python3-dev (libpython for cocotb's embedded interpreter),
# gcc-riscv64-unknown-elf (cross-check the encoder against GNU as).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        python3 python3-venv python3-dev \
        verilator \
        gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Python deps first so this layer is cached across code changes.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /work
COPY . .

CMD ["make", "lint", "test"]
