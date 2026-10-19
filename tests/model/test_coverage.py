"""The coverage collector must count the right bins (checked on small ISS runs)."""

from model.encoder import encode as e
from model.iss import Iss, Memory
from tb.coverage import COVERPOINTS, Coverage


def covered(program: list[int], data: dict[int, int] | None = None) -> Coverage:
    mem = Memory(0x4000)
    mem.load_words(program + [e("ecall")], 0)
    for addr, word in (data or {}).items():
        mem.store(addr, word, 4)
    cov = Coverage()
    for retire in Iss(mem).run():
        cov.sample(retire)
    return cov


def hits(cov: Coverage) -> set[str]:
    return {f"{p}.{n}" for p, bins in cov.bins.items() for n, c in bins.items() if c}


def test_bin_counts():
    assert sum(len(bins) for bins in COVERPOINTS.values()) == 90


def test_branch_taken_and_not_taken():
    # Loop runs twice: bne is taken once, then falls through once.
    cov = covered([e("addi", rd=1, imm=2), e("addi", rd=1, rs1=1, imm=-1), e("bne", rs1=1, imm=-4)])
    assert cov.bins["branch"]["bne_taken"] == 1
    assert cov.bins["branch"]["bne_not_taken"] == 1


def test_raw_hazard_distances():
    cov = covered(
        [
            e("addi", rd=1, imm=1),
            e("add", rd=2, rs1=1, rs2=0),  # rs1 = x1 written 1 back; rs2 = x0 is no hazard
            e("addi", rd=3, imm=0),
            e("add", rd=4, rs1=0, rs2=1),  # rs2 = x1 written 3 back
        ]
    )
    assert {"raw_hazard.rs1_dist1", "raw_hazard.rs2_dist3"} <= hits(cov)
    assert cov.bins["raw_hazard"]["rs2_dist1"] == 0


def test_load_use_and_offsets():
    cov = covered(
        [e("lui", rd=1, imm=2), e("lbu", rd=2, rs1=1, imm=3), e("add", rd=3, rs1=2, rs2=2)],
        data={0x2000: 0x1234_5678},
    )
    assert {"load_offset.lbu@3", "raw_hazard.load_use"} <= hits(cov)


def test_x0_and_immediate_sign():
    cov = covered([e("addi", rd=0, rs1=0, imm=-5)])
    assert {"x0.rd_x0", "x0.rs1_x0", "imm_sign.I_neg"} <= hits(cov)


def test_merge_save_and_load(tmp_path):
    a = covered([e("add", rd=1, rs1=2, rs2=3)])
    path = tmp_path / "cov.json"
    a.save(path)
    b = Coverage.load(path)
    b.merge(a)
    assert b.bins["opcode"]["add"] == 2
    assert 0 < b.percent() < 100
