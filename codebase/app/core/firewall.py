"""Validation and Hallucination Firewall for Phase 1.

Acts as the perimeter gatekeeper for all generated troubleshooting outputs.
Enforces:
1. Zero URL leaks (Gate G5).
2. Strict schema typing and structure (Gate G4).
3. Formatting constraints: Goal regex, 2-3 word title, 5-7 word description starting with 'It will' (Block A1).
4. Deeplink catalog integrity: URIs must exist in deeplinks.json or equal bixby://dummy_positive (Block A2).
5. Auto action deeplink requirement: Every auto action must have a non-null actionableDeeplink (Block A2).
6. Action sequencing: Non-invasive auto -> manual -> critical last.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from app.core.rewrite_controller import (
    count_words,
    format_goal,
    rewrite_action_description,
    rewrite_title,
    validate_description_format,
    validate_goal_format,
    validate_title_format,
)
from app.core.sanitizer import find_url_leaks, is_bixby_uri, sanitize_text
from app.core.schema import (
    Action,
    ContextDeeplinkResponse,
    Goal,
    StepGroup,
    actionCategory,
)

logger = logging.getLogger(__name__)

# Category precedence order for sorting
CATEGORY_PRIORITY = {
    actionCategory.auto: 0,
    actionCategory.manual: 1,
    actionCategory.critical: 2,
}


class FirewallViolationError(ValueError):
    """Raised when an unrecoverable validation or hallucination violation occurs."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class ValidationFirewall:
    """Perimeter firewall verifying all schema, formatting, and catalog invariants."""

    def __init__(
        self,
        catalog_path: Optional[Union[str, Path]] = None,
        actionable_uris: Optional[Set[str]] = None,
        validation_uris: Optional[Set[str]] = None,
    ):
        self.actionable_uris: Set[str] = actionable_uris or set()
        self.validation_uris: Set[str] = validation_uris or set()

        if not self.actionable_uris and catalog_path:
            self.load_catalog(catalog_path)
        elif not self.actionable_uris:
            # Default lookup in workspace root
            default_catalog = Path(__file__).resolve().parent.parent.parent / "deeplinks.json"
            if default_catalog.exists():
                self.load_catalog(default_catalog)

    def load_catalog(self, catalog_path: Union[str, Path]) -> None:
        """Load authoritative URIs from deeplinks.json."""
        path = Path(catalog_path)
        if not path.exists():
            logger.warning(f"Deeplink catalog not found at {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        deeplinks = data.get("deeplinks", [])
        self.actionable_uris = {dl["deeplink"] for dl in deeplinks if "deeplink" in dl}
        # Always allow generic placeholder
        self.actionable_uris.add("bixby://dummy_positive")

        self.validation_uris = {
            dl["validation"]["deeplink"]
            for dl in deeplinks
            if dl.get("validation") and "deeplink" in dl["validation"]
        }

    def validate_action(
        self,
        action: Action,
        allow_repair: bool = False,
    ) -> Tuple[Action, List[str]]:
        """Validate an Action object, checking description, category, and stepGroups."""
        errors: List[str] = []

        # 1. Action Name
        if not action.actionName or not action.actionName.strip():
            errors.append("Action actionName must not be empty")

        leaks = find_url_leaks(action.actionName)
        if leaks:
            errors.append(f"URL leak in actionName: {[m[1] for m in leaks]}")

        # 2. Description format (5-7 words, starts with 'It will')
        clean_desc = action.description
        if allow_repair and find_url_leaks(clean_desc):
            clean_desc = sanitize_text(clean_desc)
        elif find_url_leaks(clean_desc):
            errors.append(f"URL leak in action description: {clean_desc}")

        if not validate_description_format(clean_desc):
            if allow_repair:
                clean_desc = rewrite_action_description(clean_desc, action.actionName)
                if not validate_description_format(clean_desc):
                    errors.append(f"Failed to rewrite description to 5-7 words with 'It will': {clean_desc}")
            else:
                errors.append(
                    f"Action description must be 5-7 words and start with 'It will' (got '{clean_desc}', words: {count_words(clean_desc)})"
                )

        # 3. Category & StepGroups
        if not action.stepGroups:
            errors.append(f"Action '{action.actionName}' must have at least one StepGroup")

        validated_groups: List[StepGroup] = []
        for g_idx, group in enumerate(action.stepGroups):
            # Validate steps
            if not group.steps:
                errors.append(f"StepGroup {g_idx} in '{action.actionName}' has empty steps list")

            cleaned_steps = []
            for s_idx, step in enumerate(group.steps):
                if not step or not step.strip():
                    errors.append(f"Empty step at index {s_idx} in StepGroup {g_idx}")
                    continue

                step_leaks = find_url_leaks(step)
                if step_leaks:
                    if allow_repair:
                        step = sanitize_text(step)
                    else:
                        errors.append(f"URL leak in step text: {[m[1] for m in step_leaks]}")
                cleaned_steps.append(step)

            # Auto action deeplink requirement
            if action.category == actionCategory.auto:
                if not group.actionableDeeplink:
                    errors.append(
                        f"Action '{action.actionName}' is category 'auto' but StepGroup {g_idx} has no actionableDeeplink"
                    )

            # Catalog Integrity for actionableDeeplink
            if group.actionableDeeplink:
                uri = group.actionableDeeplink.deeplink
                if not is_bixby_uri(uri):
                    errors.append(f"Actionable deeplink URI must start with 'bixby://', got '{uri}'")
                elif self.actionable_uris and uri not in self.actionable_uris:
                    errors.append(f"Actionable deeplink URI '{uri}' is not in authoritative deeplinks catalog")

            # Catalog Integrity for validationDeeplink
            if group.validationDeeplink:
                val_uri = group.validationDeeplink.deeplink
                if not is_bixby_uri(val_uri):
                    errors.append(f"Validation deeplink URI must start with 'bixby://', got '{val_uri}'")
                elif self.validation_uris and val_uri not in self.validation_uris:
                    errors.append(f"Validation deeplink URI '{val_uri}' is not in authoritative catalog validation URIs")

            validated_groups.append(
                StepGroup(
                    steps=cleaned_steps,
                    actionableDeeplink=group.actionableDeeplink,
                    validationDeeplink=group.validationDeeplink,
                )
            )

        new_action = Action(
            actionName=action.actionName.strip(),
            description=clean_desc,
            stepGroups=validated_groups,
            category=action.category,
        )
        return new_action, errors

    def validate_goal(
        self,
        goal: Goal,
        allow_repair: bool = False,
    ) -> Tuple[Goal, List[str]]:
        """Validate a complete Goal object against all schema, formatting, and catalog rules."""
        errors: List[str] = []

        # 1. Goal format check
        goal_text = goal.goal
        if allow_repair and find_url_leaks(goal_text):
            goal_text = sanitize_text(goal_text)
        elif find_url_leaks(goal_text):
            errors.append(f"URL leak in goal string: {goal_text}")

        if not validate_goal_format(goal_text):
            if allow_repair:
                goal_text = format_goal(goal_text)
                if not validate_goal_format(goal_text):
                    errors.append(f"Failed to repair goal string into official syntax: {goal_text}")
            else:
                errors.append(
                    f"Goal string does not match regex ^Follow these steps to perform this .+ (Troubleshooting|Configuration)\\.?$: '{goal_text}'"
                )

        # 2. Title format check (2-3 words, sentence case)
        title_text = goal.title
        if allow_repair and find_url_leaks(title_text):
            title_text = sanitize_text(title_text)
        elif find_url_leaks(title_text):
            errors.append(f"URL leak in title string: {title_text}")

        if not validate_title_format(title_text):
            if allow_repair:
                title_text = rewrite_title(title_text)
                if not validate_title_format(title_text):
                    errors.append(f"Failed to rewrite title to 2-3 words: {title_text}")
            else:
                errors.append(
                    f"Title must be exactly 2-3 words (got '{title_text}', count: {count_words(title_text)})"
                )

        # 3. Score bounds check (0.0 to 1.0)
        if not (0.0 <= goal.score <= 1.0):
            errors.append(f"Score must be between 0.0 and 1.0, got {goal.score}")

        # 4. Actions list check
        if not goal.actions:
            errors.append("Goal actions list must not be empty")

        # Validate each action
        validated_actions: List[Action] = []
        for idx, act in enumerate(goal.actions):
            v_act, act_errors = self.validate_action(act, allow_repair=allow_repair)
            validated_actions.append(v_act)
            for err in act_errors:
                errors.append(f"Action[{idx}] '{act.actionName}': {err}")

        # 5. Check action sequence ordering: auto -> manual -> critical
        current_priority = -1
        is_sorted = True
        for act in validated_actions:
            cat = act.category or actionCategory.manual
            p = CATEGORY_PRIORITY.get(cat, 1)
            if p < current_priority:
                is_sorted = False
                break
            current_priority = p

        if not is_sorted:
            if allow_repair:
                # Deterministically sort actions: auto (0) -> manual (1) -> critical (2)
                validated_actions.sort(
                    key=lambda a: CATEGORY_PRIORITY.get(a.category or actionCategory.manual, 1)
                )
            else:
                errors.append(
                    "Actions not ordered correctly: must be sorted auto (non-invasive) -> manual -> critical"
                )

        new_goal = Goal(
            goal=goal_text,
            title=title_text,
            actions=validated_actions,
            score=round(goal.score, 4),
        )
        return new_goal, errors

    def validate_response(
        self,
        response: ContextDeeplinkResponse,
        allow_repair: bool = False,
    ) -> Tuple[ContextDeeplinkResponse, List[str]]:
        """Validate an entire ContextDeeplinkResponse."""
        errors: List[str] = []
        validated_goals: List[Goal] = []

        if not response.contexts:
            errors.append("ContextDeeplinkResponse contexts list must not be empty")

        for idx, g in enumerate(response.contexts):
            v_goal, g_errors = self.validate_goal(g, allow_repair=allow_repair)
            validated_goals.append(v_goal)
            for err in g_errors:
                errors.append(f"Context[{idx}]: {err}")

        return ContextDeeplinkResponse(contexts=validated_goals), errors
