
import pytest

from boltz2nb.run_params import (
    DEFAULTS,
    apply_profile,
    load_run_params,
    parse_run_params_text,
    serialize_run_params,
    validate_run_params,
)
from boltz2nb.runner import build_boltz_cmd, capture_run_context, run_boltz, unique_output_dir

GUI_TEXT = '''job_name = "kinase_1"
use_potentials = false
override = true
recycling_steps = 3
sampling_steps = 200
diffusion_samples = 3
step_scale = 1.638
max_msa_seqs = 8192
subsample_msa = true
num_subsampled_msa = 1024
msa_pairing_strategy = "greedy"'''


def test_parse_gui_format():
    p = parse_run_params_text(GUI_TEXT)
    assert p["job_name"] == "kinase_1" and p["override"] is True and p["use_potentials"] is False
    assert p["diffusion_samples"] == 3 and p["step_scale"] == 1.638 and isinstance(p["recycling_steps"], int)


def test_roundtrip(tmp_path):
    f = tmp_path / "run_params.txt"
    f.write_text(serialize_run_params({"job_name": "x", "seed": None, "use_potentials": True, "step_scale": 1.5}))
    p = load_run_params(f)
    assert p["job_name"] == "x" and p["seed"] is None and p["use_potentials"] is True and p["step_scale"] == 1.5
    assert p["max_msa_seqs"] == DEFAULTS["max_msa_seqs"]


def test_profiles_and_validation():
    fast = apply_profile("fast")
    assert fast["sampling_steps"] == 50 and fast["max_msa_seqs"] == 256
    sci = apply_profile("scientific", {"job_name": "j", "diffusion_samples": 2})
    assert sci["diffusion_samples"] == 2 and sci["use_potentials"] is True and sci["job_name"] == "j"
    with pytest.raises(ValueError):
        apply_profile("turbo")
    bad = dict(DEFAULTS, job_name="a b", sampling_steps=5, msa_pairing_strategy="unpaired_paired")
    probs = validate_run_params(bad)
    assert any("spaces" in p for p in probs) and any("sampling_steps" in p for p in probs)
    assert any("msa_pairing_strategy" in p for p in probs)
    assert validate_run_params(dict(DEFAULTS, job_name="ok")) == []


def test_build_cmd(tmp_path):
    y = tmp_path / "j.yaml"
    y.write_text("version: 1\nsequences:\n  - protein:\n      id: [A]\n      sequence: MKT\n")
    cmd = build_boltz_cmd(y, tmp_path / "out", {"job_name": "j", "diffusion_samples": 2, "use_potentials": True, "seed": 7})
    assert cmd[:3] == ["boltz", "predict", str(y)]
    assert "--use_msa_server" in cmd and cmd[cmd.index("--msa_pairing_strategy") + 1] == "greedy"
    assert cmd[cmd.index("--diffusion_samples") + 1] == "2" and "--use_potentials" in cmd
    assert cmd[cmd.index("--seed") + 1] == "7" and "--write_full_pae" in cmd and "--override" not in cmd
    assert "--num_workers" not in cmd and "--accelerator" not in cmd
    c3 = build_boltz_cmd(y, tmp_path / "out", {"accelerator": "cpu"}); assert c3[c3.index("--accelerator") + 1] == "cpu"
    assert any("accelerator" in p for p in validate_run_params(dict(DEFAULTS, job_name="j", accelerator="quantum")))
    assert build_boltz_cmd(y, tmp_path / "out", {"num_workers": 0})[-2:] != ["--num_workers", "1"]
    c2 = build_boltz_cmd(y, tmp_path / "out", {"num_workers": 0}); assert c2[c2.index("--num_workers") + 1] == "0"
    assert cmd[cmd.index("--step_scale") + 1] == "1.638" and cmd[cmd.index("--max_msa_seqs") + 1] == "8192"
    y.write_text("version: 1\nsequences:\n  - protein:\n      id: [A]\n      sequence: MKT\n      msa: empty\n")
    cmd = build_boltz_cmd(y, tmp_path / "out", {})
    assert "--use_msa_server" not in cmd and "--msa_pairing_strategy" not in cmd
    cmd = build_boltz_cmd(y, tmp_path / "out", {"subsample_msa": False, "write_full_pae": False, "max_parallel_samples": None})
    assert "--subsample_msa" not in cmd and "--write_full_pae" not in cmd and "--max_parallel_samples" not in cmd


def test_unique_output_dir(tmp_path):
    d = tmp_path / "job"
    assert unique_output_dir(d) == d
    d.mkdir()
    u = unique_output_dir(d)
    assert u != d and u.name.startswith("job_") and not u.exists()


def test_run_boltz_streams_and_logs(tmp_path):
    seen = []
    res = run_boltz(["python3", "-c", "import sys;print('a');print('b', file=sys.stderr);sys.exit(3)"],
                    tmp_path / "log.txt", on_line=seen.append)
    assert res["return_code"] == 3 and set(seen) == {"a", "b"}
    assert "a" in (tmp_path / "log.txt").read_text()


def test_capture_run_context(tmp_path):
    y = tmp_path / "j.yaml"; y.write_text("version: 1\n")
    ctx = capture_run_context({"job_name": "j"}, ["boltz", "predict"], y)
    assert ctx["input_yaml_sha1"] and ctx["boltz2nb_version"] and "cuda_available" in ctx
