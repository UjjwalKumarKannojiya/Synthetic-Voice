from pathlib import Path

import yaml


def test_config_has_required_contract() -> None:
    config_path = Path(__file__).parents[1] / "configs" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["seed"] == 42
    assert config["audio"]["sample_rate"] == 16000
    assert config["model"]["score_definition"] == "probability_of_fake"
    assert config["model"]["threshold_source"] == "validation"