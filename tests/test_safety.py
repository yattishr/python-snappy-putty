from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snappy_putty.models import SuggestedCommand
from snappy_putty.safety import attach_risk_tags, score_risk


def test_score_risk_high_pattern() -> None:
    assert score_risk("rm -rf /") == "high"


def test_attach_risk_tags_escalates_level() -> None:
    commands = [SuggestedCommand(cmd="terraform apply", explain="apply infra", risk="low")]
    tagged = attach_risk_tags(commands)
    assert tagged[0].risk == "high"
