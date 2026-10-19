# Build, lint and test entry points. `make help` lists them.

VENV   ?= .venv
# Use the project venv if it exists (local dev), otherwise python3 on PATH (Docker, CI).
PYTHON ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
IMAGE  ?= rv32i-core-verif

# Verilator lint units: each top-level module with the files it needs (packages first).
CORE_SINGLE_SRCS := rtl/rv32i_pkg.sv rtl/alu.sv rtl/regfile.sv rtl/decoder.sv \
                    rtl/branch_unit.sv rtl/lsu.sv rtl/core_single.sv
LINT_alu         := rtl/rv32i_pkg.sv rtl/alu.sv
LINT_regfile     := rtl/regfile.sv
LINT_core_single := $(CORE_SINGLE_SRCS)
LINT_tb_top      := $(CORE_SINGLE_SRCS) tb/tb_top.sv
LINT_TOPS        := alu regfile core_single tb_top

.PHONY: help venv lint lint-py lint-rtl format test test-model test-rtl docker-test clean

help:
	@echo "make venv         create .venv and install pinned Python deps"
	@echo "make lint         ruff (Python) + verilator --lint-only -Wall (RTL)"
	@echo "make format       auto-format Python with ruff"
	@echo "make test         golden-model tests + RTL tests"
	@echo "make test-model   pytest on the Python golden model"
	@echo "make test-rtl     cocotb + Verilator tests (SEED=<n>, WAVES=1)"
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
lint-rtl: $(addprefix lint-rtl-,$(LINT_TOPS))

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

docker-test:
	docker build -t $(IMAGE) .
	docker run --rm $(IMAGE)

clean:
	rm -rf sim_build build .pytest_cache
