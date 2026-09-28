"""Executable tests for frozen Theme 2 API/response contract."""
import pytest
from pydantic import ValidationError

from app.api.schemas import SIISResponseInput, TroubleshootRequest
from app.core.schema import (
    Action,
    ContextDeeplinkResponse,
    Goal,
    StepGroup,
    actionCategory,
)


def test_goal_title_length_validation():
    """Check that goal titles strictly between 2-3 words are accepted."""
    from app.core.firewall import ValidationFirewall
    firewall = ValidationFirewall()

    # Valid: 2 words
    goal_2 = Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Two Words", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)
    v_goal, errors = firewall.validate_goal(goal_2, allow_repair=False)
    assert not any("Title must be exactly 2-3 words" in e for e in errors)

    # Valid: 3 words
    goal_3 = Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Three Words Here", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)
    v_goal, errors = firewall.validate_goal(goal_3, allow_repair=False)
    assert not any("Title must be exactly 2-3 words" in e for e in errors)

    # Invalid: 1 word
    goal_1 = Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="One", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)
    v_goal, errors = firewall.validate_goal(goal_1, allow_repair=False)
    assert any("Title must be exactly 2-3 words" in e for e in errors)

    # Invalid: 4 words
    goal_4 = Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Four Words Are Here", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=1.0)
    v_goal, errors = firewall.validate_goal(goal_4, allow_repair=False)
    assert any("Title must be exactly 2-3 words" in e for e in errors)


def test_goal_score_range_validation():
    """Check that scores must be between 0 and 1."""
    from app.core.firewall import ValidationFirewall
    firewall = ValidationFirewall()

    def create_goal(score: float) -> Goal:
        return Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Valid Title", actions=[Action(actionName="A", description="It will do a thing", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual)], score=score)

    # Valid
    for s in [0.0, 1.0, 0.5]:
        v_goal, errors = firewall.validate_goal(create_goal(s), allow_repair=False)
        assert not any("Score must be between 0.0 and 1.0" in e for e in errors)

    # Invalid
    for s in [-0.1, 1.1]:
        v_goal, errors = firewall.validate_goal(create_goal(s), allow_repair=False)
        assert any("Score must be between 0.0 and 1.0" in e for e in errors)


def test_action_description_constraint():
    """Verify action description starts with 'It will' and length constraints (5-7 words)."""
    from app.core.firewall import ValidationFirewall
    from app.core.schema import Deeplink
    firewall = ValidationFirewall()

    def create_action(desc: str) -> Action:
        return Action(
            actionName="Fix",
            description=desc,
            stepGroups=[StepGroup(steps=["S"], actionableDeeplink=Deeplink(deeplink="bixby://valid", description=""))],
            category=actionCategory.auto
        )

    # Valid
    for d in [
        "It will fix the display today", # 6 words
        "It will fix the broken display", # 6 words
        "It will perform a full reset", # 6 words
    ]:
        # The regex firewall checks exact format
        act, errors = firewall.validate_action(create_action(d), allow_repair=False)
        assert not any("Action description must be 5-7 words" in e for e in errors)

    # Invalid length
    for d in [
        "It will fix", # 3 words
        "It will fix the broken display screen now", # 8 words
        "Fix the display screen now", # 5 words but doesn't start with It will
    ]:
        act, errors = firewall.validate_action(create_action(d), allow_repair=False)
        assert any("Action description must be 5-7 words and start with 'It will'" in e for e in errors)


def test_action_category_enum():
    """Verify category is only 'auto', 'manual', or 'critical'."""
    assert actionCategory.auto == "auto"
    assert actionCategory.manual == "manual"
    assert actionCategory.critical == "critical"

    with pytest.raises(ValidationError):
        Action(
            actionName="Test",
            description="It will do a thing",
            stepGroups=[],
            category="invalid_category" # type: ignore
        )


def test_action_ordering():
    """Verify categories are ordered 'auto' -> 'manual' -> 'critical'."""
    from app.core.firewall import ValidationFirewall
    from app.core.schema import Deeplink
    firewall = ValidationFirewall()

    # Create actions in unordered sequence: critical -> auto -> manual
    actions = [
        Action(actionName="A1", description="It will perform a critical task", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.critical),
        Action(actionName="A2", description="It will perform an auto task", stepGroups=[StepGroup(steps=["S"], actionableDeeplink=Deeplink(deeplink="bixby://valid", description=""))], category=actionCategory.auto),
        Action(actionName="A3", description="It will perform a manual task", stepGroups=[StepGroup(steps=["S"])], category=actionCategory.manual),
    ]
    goal = Goal(goal="Follow these steps to perform this Valid Troubleshooting.", title="Valid Title", actions=actions, score=1.0)

    # When allow_repair=False, it should raise an error
    v_goal_err, errors = firewall.validate_goal(goal, allow_repair=False)
    assert any("must be sorted auto (non-invasive) -> manual -> critical" in e for e in errors)

    # When allow_repair=True, it should successfully reorder them
    v_goal_rep, rep_errors = firewall.validate_goal(goal, allow_repair=True)
    # Filter out the structural errors to just check if it repaired the ordering (it might still complain about some strings if validation fails, but it will sort them).
    # Since we set up valid strings above, rep_errors might be empty for order if it fixed it.

    categories = [a.category for a in v_goal_rep.actions]
    assert categories == [actionCategory.auto, actionCategory.manual, actionCategory.critical]


def test_siis_response_input():
    """Verify SIIS response input rejects empty fields."""
    with pytest.raises(ValidationError):
        SIISResponseInput(title="", content="valid")

    with pytest.raises(ValidationError):
        SIISResponseInput(title="valid", content="")

    valid = SIISResponseInput(title="Valid", content="Valid content")
    assert valid.title == "Valid"
