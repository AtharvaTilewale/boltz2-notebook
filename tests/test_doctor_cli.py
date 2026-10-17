"""``python -m boltz2nb.doctor``: help, missing paths and empty directories are reported, not swallowed."""
from boltz2nb import doctor


def test_help_and_missing_path(capsys, tmp_path):
    assert doctor.main(["--help"]) == 0 and "Inspect a Boltz output directory" in capsys.readouterr().out
    assert doctor.main([]) == 2
    assert doctor.main([str(tmp_path / "nope")]) == 2 and "No such file" in capsys.readouterr().err


def test_directory_without_predictions(capsys, tmp_path):
    assert doctor.main([str(tmp_path)]) == 1
    out = capsys.readouterr()
    assert '"predictions_dir": null' in out.out and "No Boltz prediction files" in out.err


def test_real_predictions(capsys, example_pred_dir):
    assert doctor.main([str(example_pred_dir)]) == 0
    out = capsys.readouterr().out
    assert '"match"' in out and '"affinity_files"' in out
