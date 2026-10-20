# Build, lint and test entry points. `make help` lists them.

VENV   ?= .venv
# Test knobs given on the make command line are passed to pytest:
#   CORE=single|pipe (default: both), SEEDS, SEED_START, SEED, WAVES
export CORE SEEDS SEED_START SEED WAVES
# Use the project venv if it exists (local dev), otherwise python3 on PATH (Docker, CI).
PYTHON ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
IMAGE  ?= rv32i-core-verif

# Verilator lint units: each top-level module with the files it needs (packages first).
COMMON_SRCS      := rtl/rv32i_pkg.sv rtl/alu.sv rtl/regfile.sv rtl/decoder.sv \
                    rtl/branch_unit.sv rtl/lsu.sv
LINT_alu         := rtl/rv32i_pkg.sv rtl/alu.sv
LINT_regfile     := rtl/regfile.sv
LINT_core_single := $(COMMON_SRCS) rtl/core_single.sv
LINT_core_pipe   := $(COMMON_SRCS) rtl/core_pipe.sv
LINT_tb_top      := $(COMMON_SRCS) rtl/core_single.sv rtl/core_pipe.sv tb/tb_top.sv
LINT_TOPS        := alu regfile core_single core_pipe tb_top

.PHONY: help venv lint lint-py lint-rtl format test test-model test-rtl test-random coverage cpi \
        mutation docker-test clean

help:
	@echo "make venv         create .venv and install pinned Python deps"
	@echo "make lint         ruff (Python) + verilator --lint-only -Wall (RTL)"
	@echo "make format       auto-format Python with ruff"
	@echo "make test         golden-model tests + RTL tests"
	@echo "make test-model   pytest on the Python golden model"
	@echo "make test-rtl     cocotb + Verilator tests (SEED=<n>, WAVES=1)"
	@echo "make test-random  random programs only (SEEDS=<count> SEED_START=<first seed>)"
	@echo "make coverage     functional coverage report from the last test run"
	@echo "make cpi          CPI of the C programs on both cores, from the last test run"
	@echo "make mutation     inject 7 pipeline bugs one at a time, count failing tests (~5 min)"
	@echo "make docker-test  build the Docker image and run lint + tests in it"
	@echo "make clean        remove build output"

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

lint: lint-py lint-rtl

lint-py:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

# `make lint-rtl` runs `lint-rtl-alu`, `lint-rtl-regfile`, ... ($* is the top name).
# tb_top is linted a second time with the pipelined core selected.
lint-rtl: $(addprefix lint-rtl-,$(LINT_TOPS))
	verilator --lint-only -Wall -DPIPELINED --top-module tb_top $(LINT_tb_top)

lint-rtl-%:
	verilator --lint-only -Wall --top-module $* $(LINT_$*)

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

test: test-model test-rtl

test-model:
	$(PYTHON) -m pytest tests/model

test-rtl:
	$(PYTHON) -m pytest tests/rtl

# SEEDS / SEED_START are read from the environment by tests/rtl/test_core_random.py.
test-random:
	$(PYTHON) -m pytest tests/rtl/test_core_random.py

coverage:
	$(PYTHON) -m tb.coverage_report

cpi:
	$(PYTHON) -m tb.cpi_report

# Not part of `make test` (takes minutes): proves the tests catch injected pipeline bugs.
mutation:
	$(PYTHON) tools/mutation_analysis.py

docker-test:
	docker build -t $(IMAGE) .
	docker run --rm $(IMAGE)

clean:
	rm -rf sim_build build .pytest_cache
