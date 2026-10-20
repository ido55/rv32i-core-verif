# Reproducible build/test environment: same OS and tool versions as CI.
#   docker build -t rv32i-core-verif .
#   docker run --rm rv32i-core-verif          # runs: make lint test synth
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# verilator 5.020 (simulator), g++/make (build the Verilator model),
# python3-dev (libpython for cocotb's embedded interpreter),
# gcc-riscv64-unknown-elf (riscv-tests, C programs, encoder cross-check against GNU as),
# yosys 0.33 (synthesis), curl + ca-certificates (download sv2v below).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        python3 python3-venv python3-dev \
        verilator \
        gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf \
        yosys \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# sv2v: SystemVerilog -> Verilog for Yosys (pinned release, checksum-verified).
COPY tools/install_sv2v.sh /tmp/install_sv2v.sh
RUN bash /tmp/install_sv2v.sh /usr/local/bin

# Install pinned Python deps first so this layer is cached across code changes.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /work
COPY . .

CMD ["make", "lint", "test", "synth"]
