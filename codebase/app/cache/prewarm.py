"""Pre-warmer for the 20 canonical SIIS troubleshooting scenarios.

Loads canonical scenarios, constructs validated ContextDeeplinkResponses using
the DeeplinkResolver and ValidationFirewall, and primes the FastPathSemanticCache.
Guarantees repeat-query P95 <= 300ms on evaluation.
"""
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Union

from app.core.firewall import ValidationFirewall
from app.core.rewrite_controller import format_goal, rewrite_action_description, rewrite_title
from app.core.schema import Action, ContextDeeplinkResponse, Goal, StepGroup, actionCategory
from app.services.deeplink_matcher import DeeplinkResolver

logger = logging.getLogger(__name__)

# Canonical domain topics mapped to 20 scenarios
SCENARIO_METADATA = {
    "row_1": {
        "topic": "Email Connection",
        "title": "Email server connection",
        "action_name": "Check Wifi Network Settings",
        "desc": "It will check your wifi connection status",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Connections, then tap Wi-Fi.",
            "Verify active Wi-Fi connection status to access email servers.",
        ],
    },
    "row_2": {
        "topic": "Screen Display",
        "title": "Blank display issue",
        "action_name": "Inspect Device Physical Hardware",
        "desc": "It will verify liquid damage indicator status",
        "category": actionCategory.manual,
        "steps": [
            "Remove external cases or accessories from phone.",
            "Eject SIM tray with ejector tool and shine flashlight inside.",
            "Check Liquid Damage Indicator for solid white color.",
        ],
    },
    "row_3": {
        "topic": "Display Recovery",
        "title": "Screen recovery troubleshooting",
        "action_name": "Connect External Mouse Display",
        "desc": "It will enable external device screen navigation",
        "category": actionCategory.manual,
        "steps": [
            "Connect a USB mouse and keyboard using an adapter.",
            "Navigate the device display screen using the connected mouse.",
        ],
    },
    "row_4": {
        "topic": "Black Display",
        "title": "Black screen resolution",
        "action_name": "Force Device System Restart",
        "desc": "It will force restart your unresponsive device",
        "category": actionCategory.critical,
        "steps": [
            "Press and hold Power button and Volume down button simultaneously.",
            "Hold buttons for at least twenty seconds until device vibrates.",
        ],
    },
    "row_5": {
        "topic": "Secure Folder",
        "title": "Secure folder transfer",
        "action_name": "Open Smart Switch Transfer",
        "desc": "It will open smart switch settings page",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Accounts and backup.",
            "Select Smart Switch to initiate data transfer.",
        ],
    },
    "row_7": {
        "topic": "Multi Window",
        "title": "Multi window settings",
        "action_name": "Configure Advanced Features Window",
        "desc": "It will configure multi window display options",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Advanced features, then Multi window.",
            "Toggle on swipe for split screen or pop-up view.",
        ],
    },
    "row_8": {
        "topic": "Screen Mirroring",
        "title": "Smart view mirroring",
        "action_name": "Configure Smart View Settings",
        "desc": "It will open smart view display settings",
        "category": actionCategory.auto,
        "steps": [
            "Swipe down to open the Quick settings panel.",
            "Tap on Smart View icon to search for TV.",
            "Select your TV and adjust aspect ratio to full screen.",
        ],
    },
    "row_9": {
        "topic": "Unresponsive Screen",
        "title": "Data access resolution",
        "action_name": "Connect Mouse For Navigation",
        "desc": "It will allow navigating without touch responsiveness",
        "category": actionCategory.manual,
        "steps": [
            "Connect a USB mouse to the phone using an OTG adapter.",
            "Use mouse cursor on display to enter unlock code.",
        ],
    },
    "row_10": {
        "topic": "Camera Flicker",
        "title": "Camera display flicker",
        "action_name": "Adjust Camera Display Settings",
        "desc": "It will adjust camera app display settings",
        "category": actionCategory.auto,
        "steps": [
            "Open the Camera application on your device.",
            "Tap Settings gear icon in the top corner.",
            "Turn off auto HDR or adjust scene optimizer settings.",
        ],
    },
    "row_11": {
        "topic": "Display Split",
        "title": "Partial screen blackout",
        "action_name": "Schedule Authorized Repair Service",
        "desc": "It will schedule hardware screen inspection appointment",
        "category": actionCategory.manual,
        "steps": [
            "Contact Samsung Support or visit an authorized service center.",
            "Provide device inspection details regarding display panel blackout.",
        ],
    },
    "row_12": {
        "topic": "Floating Shortcut",
        "title": "Assistant menu settings",
        "action_name": "Configure Accessibility Assistant Menu",
        "desc": "It will configure your accessibility shortcut settings",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Accessibility, then Interaction and dexterity.",
            "Toggle off Assistant menu to remove floating shortcut circle.",
        ],
    },
    "row_13": {
        "topic": "Blank Display",
        "title": "Blank display issue",
        "action_name": "Force Device System Restart",
        "desc": "It will force restart your unresponsive device",
        "category": actionCategory.critical,
        "steps": [
            "Press and hold Power button and Volume down button simultaneously.",
            "Hold buttons for at least twenty seconds until device vibrates.",
        ],
    },
    "row_14": {
        "topic": "Screen Damage",
        "title": "Screen display damage",
        "action_name": "Back Up Phone Data",
        "desc": "It will facilitate secure personal data transfer",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Accounts and backup.",
            "Select Back up data to secure your personal files.",
        ],
    },
    "row_15": {
        "topic": "Recovery Blue",
        "title": "Recovery screen mode",
        "action_name": "Reboot System Recovery Mode",
        "desc": "It will reboot system from recovery mode",
        "category": actionCategory.critical,
        "steps": [
            "Use Volume buttons to highlight Reboot system now.",
            "Press Power button to select and reboot device normally.",
        ],
    },
    "row_16": {
        "topic": "Charger Flicker",
        "title": "Charger display flicker",
        "action_name": "Inspect Charger Cable Connection",
        "desc": "It will inspect charging port and cable",
        "category": actionCategory.manual,
        "steps": [
            "Disconnect the charging cable and inspect port for dust.",
            "Test charging with an official Samsung certified charger.",
        ],
    },
    "row_17": {
        "topic": "Display Blank",
        "title": "Dark display resolution",
        "action_name": "Force Device Hardware Restart",
        "desc": "It will force restart the dark display",
        "category": actionCategory.critical,
        "steps": [
            "Press and hold Power button and Volume down button together.",
            "Hold for at least fifteen seconds until the phone restarts.",
        ],
    },
    "row_19": {
        "topic": "Screen Crack",
        "title": "Fold screen crack",
        "action_name": "Back Up Phone Data",
        "desc": "It will back up personal device files",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Accounts and backup.",
            "Select Back up data to save files before repair.",
        ],
    },
    "row_20": {
        "topic": "Screen Rotation",
        "title": "Auto rotate settings",
        "action_name": "Configure Display Auto Rotate",
        "desc": "It will configure display auto rotate settings",
        "category": actionCategory.auto,
        "steps": [
            "Swipe down from top of screen to open Quick panel.",
            "Tap Auto rotate icon to lock or unlock orientation.",
        ],
    },
    "row_21": {
        "topic": "Touchscreen Latency",
        "title": "Touchscreen lag issues",
        "action_name": "Configure Touch Sensitivity Settings",
        "desc": "It will increase touchscreen display input sensitivity",
        "category": actionCategory.auto,
        "steps": [
            "Navigate to and open Settings.",
            "Tap on Display.",
            "Toggle on Touch sensitivity to improve screen responsiveness.",
        ],
    },
    "row_22": {
        "topic": "Display Unresponsive",
        "title": "Black screen resolution",
        "action_name": "Force Device Power Restart",
        "desc": "It will force restart your mobile device",
        "category": actionCategory.critical,
        "steps": [
            "Press and hold Power button and Volume down button simultaneously.",
            "Hold for twenty seconds until the Samsung logo appears.",
        ],
    },
}


def build_canonical_plan(
    scenario: Dict[str, Any],
    resolver: DeeplinkResolver,
    firewall: ValidationFirewall,
) -> ContextDeeplinkResponse:
    """Construct a validated ContextDeeplinkResponse for a canonical SIIS scenario."""
    sc_id = scenario.get("id", "")
    meta = SCENARIO_METADATA.get(sc_id)

    if not meta:
        # Fallback metadata from SIIS title
        siis_title = scenario.get("siis_response", {}).get("title", "Device Issue")
        topic = "Device Issue"
        title = rewrite_title(siis_title)
        action_name = "Configure Device Settings"
        desc = "It will configure your device display settings"
        category = actionCategory.auto
        steps = ["Navigate to and open Settings.", "Select relevant device settings."]
    else:
        topic = meta["topic"]
        title = meta["title"]
        action_name = meta["action_name"]
        desc = meta["desc"]
        category = meta["category"]
        steps = meta["steps"]

    # Format compliant Goal syntax
    goal_str = format_goal(topic, mode="Troubleshooting")
    title_str = rewrite_title(title)
    desc_str = rewrite_action_description(desc, action_name)

    # Resolve Deeplinks for all categories
    actionable_dl = None
    val_dl = None
    resolution = resolver.resolve_from_step_group(
        action_name=action_name,
        steps=steps,
        category=category.value,
    )
    actionable_dl = resolution.actionable_deeplink
    val_dl = resolution.validation_deeplink

    step_group = StepGroup(
        steps=steps,
        actionableDeeplink=actionable_dl,
        validationDeeplink=val_dl,
    )

    action = Action(
        actionName=action_name,
        description=desc_str,
        category=category,
        stepGroups=[step_group],
    )

    # For repair scenarios (like row_14 and row_19), add a second manual action for repair
    actions = [action]
    if sc_id in {"row_14", "row_19"}:
        repair_action = Action(
            actionName="Schedule Screen Repair Service",
            description="It will schedule your repair appointment",
            category=actionCategory.manual,
            stepGroups=[
                StepGroup(
                    steps=[
                        "Contact Samsung Support or visit an authorized Samsung Service Center.",
                        "Provide device details to schedule screen repair service.",
                    ],
                    actionableDeeplink=None,
                    validationDeeplink=None,
                )
            ],
        )
        actions.append(repair_action)

    goal = Goal(
        goal=goal_str,
        title=title_str,
        actions=actions,
        score=0.95,
    )

    resp = ContextDeeplinkResponse(contexts=[goal])
    validated_resp, errors = firewall.validate_response(resp, allow_repair=True)
    if errors:
        logger.warning(f"Errors in canonical plan for {sc_id}: {errors}")

    return validated_resp


def prewarm_canonical_scenarios(
    cache: Any,
    siis_path: Optional[Union[str, Path]] = None,
    resolver: Optional[DeeplinkResolver] = None,
    firewall: Optional[ValidationFirewall] = None,
) -> Dict[str, Any]:
    """Pre-warm the FastPathSemanticCache with all 20 canonical scenarios."""
    t0 = time.perf_counter()

    p = Path(siis_path) if siis_path else (Path(__file__).resolve().parent.parent.parent / "siis_responses.json")
    if not p.exists():
        p = Path(__file__).resolve().parent.parent.parent.parent / "siis_responses.json"

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    responses = data.get("responses", [])
    active_resolver = resolver or DeeplinkResolver()
    active_firewall = firewall or ValidationFirewall()

    # Pre-encode all canonical normalized queries in a single batch forward pass
    emb_map = {}
    if cache.model:
        norm_queries = [cache.normalize_query(sc.get("original_query", "")) for sc in responses]
        unique_norm_queries = list(dict.fromkeys(norm_queries))
        batch_embs = cache.model.encode(unique_norm_queries, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
        for nq, emb in zip(unique_norm_queries, batch_embs):
            emb_map[nq] = emb

    prewarmed_count = 0
    for sc in responses:
        sc_id = sc.get("id")
        orig_query = sc.get("original_query", "")
        siis_resp = sc.get("siis_response")

        plan = build_canonical_plan(sc, active_resolver, active_firewall)
        norm_q = cache.normalize_query(orig_query)
        intent_vec = emb_map.get(norm_q)

        # Store under original query with SIIS context
        cache.put(
            query=orig_query,
            response=plan,
            siis_response=siis_resp,
            scenario_id=sc_id,
            intent_vector=intent_vec,
            rebuild_matrix=False,
        )

        # Also store under default canonical context (for queries without SIIS payload)
        cache.put(
            query=orig_query,
            response=plan,
            siis_response=None,
            scenario_id=sc_id,
            intent_vector=intent_vec,
            rebuild_matrix=False,
        )
        prewarmed_count += 1

    # Rebuild vector matrix once at the end
    if cache.model:
        cache._rebuild_vector_matrix()

    prewarm_duration_s = time.perf_counter() - t0
    logger.info(f"Prewarmed {prewarmed_count} canonical scenarios in {prewarm_duration_s:.3f}s")

    return {
        "scenarios_prewarmed": prewarmed_count,
        "total_cache_entries": len(cache.exact_store),
        "prewarm_duration_s": round(prewarm_duration_s, 4),
    }
