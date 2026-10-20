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
        mutation synth waveform plots test-report results docker-test clean

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
	@echo "make synth        Yosys resource counts of both cores (needs sv2v: tools/install_sv2v.sh)"
	@echo "make waveform     docs/img/failing_waveform.png: a failing test on an injected bug"
	@echo "make plots        docs/img/*.png CPI and coverage plots, from the last test run"
	@echo "make test-report  pass counts of the last test run"
	@echo "make results      regenerate every number and plot in the README (~10 min)"
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
	$(PYTHON) -m pytest tests/model $(PYTEST_ARGS)

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
	$(PYTHON) -m tools.mutation_analysis

synth:
	$(PYTHON) -m tools.synth_report

waveform:
	$(PYTHON) -m tools.failing_waveform

plots:
	$(PYTHON) -m tools.plot_results

test-report:
	$(PYTHON) -m tools.test_report

# Every number and plot in the README, from a clean tree. The bug-injecting steps run
# first, so the test results that follow (and test-report) come from the unmodified RTL.
results:
	$(MAKE) clean
	$(MAKE) synth
	$(MAKE) mutation
	$(MAKE) waveform
	$(MAKE) test-model PYTEST_ARGS=--junitxml=build/results/model_tests.xml
	$(MAKE) test-rtl
	$(MAKE) test-report
	$(MAKE) coverage
	$(MAKE) cpi
	$(MAKE) plots

docker-test:
	docker build -t $(IMAGE) .
	docker run --rm $(IMAGE)

clean:
	rm -rf sim_build build .pytest_cache
