# ruff: noqa: S101

from __future__ import annotations

from helpers.sts import (
    ChoiceOption,
    JsonObject,
    MonsterOption,
    collect_cards,
    collect_choices,
    latest_command_id,
    message_responses,
    normalize_text,
    render_upgraded_name,
    resolve_choice,
    resolve_monster,
)

LAST_COMMAND_ID = 12


def test_normalize_collapses_spacing_and_symbols() -> None:
    assert (
        normalize_text(" Lose all Gold: Remove 2 Cards! ")
        == "lose all gold remove 2 cards"
    )


def test_render_upgraded_name_appends_suffix() -> None:
    assert render_upgraded_name("Zap", 1) == "Zap+"
    assert render_upgraded_name("Buffer", 2) == "Buffer+2"


def test_collect_choices_prefers_option_label_and_choice_list_alias() -> None:
    state: JsonObject = {
        "game_state": {
            "choice_list": ["max hp +7"],
            "screen_state": {
                "options": [
                    {
                        "choice_index": 3,
                        "label": "Max HP +7",
                        "text": "[Blessing] Increase your max HP.",
                    }
                ]
            },
        }
    }

    assert collect_choices(state) == [
        ChoiceOption(
            index=3,
            display="Max HP +7",
            aliases=(
                "Max HP +7",
                "[Blessing] Increase your max HP.",
                "max hp +7",
            ),
        )
    ]


def test_resolve_choice_accepts_partial_name() -> None:
    state: JsonObject = {
        "game_state": {
            "choice_list": ["Obtain a random rare Card", "Max HP +7"],
            "screen_state": {},
        }
    }

    assert resolve_choice(state, "rare") == 0


def test_collect_cards_renders_upgrades() -> None:
    state: JsonObject = {
        "game_state": {
            "combat_state": {
                "hand": [
                    {
                        "name": "Zap",
                        "upgrades": 1,
                        "has_target": False,
                        "is_playable": True,
                    }
                ]
            }
        }
    }

    cards = collect_cards(state)

    assert cards[0].display == "Zap+"
    assert cards[0].aliases == ("Zap", "Zap+")


def test_resolve_monster_rejects_untargetable_entries() -> None:
    state: JsonObject = {
        "game_state": {
            "combat_state": {
                "monsters": [
                    {
                        "name": "Cultist",
                        "current_hp": 44,
                        "is_gone": False,
                        "half_dead": False,
                    },
                    {
                        "name": "Darkling",
                        "current_hp": 0,
                        "is_gone": False,
                        "half_dead": True,
                    },
                ]
            }
        }
    }

    assert resolve_monster(state, "Cultist") == MonsterOption(
        index=0,
        display="Cultist",
        aliases=("Cultist",),
        is_targetable=True,
    )


def test_message_responses_extracts_valid_message_payloads() -> None:
    events: list[JsonObject] = [
        {"kind": "message", "data": '{"command_id":"7","ready_for_command":true}'},
        {"kind": "status", "data": '{"ignored":true}'},
        {"kind": "message", "data": "not-json"},
    ]

    assert message_responses(events) == [
        {"command_id": "7", "ready_for_command": True},
    ]


def test_latest_command_id_returns_last_valid_message_command() -> None:
    events: list[JsonObject] = [
        {"kind": "message", "data": '{"command_id":"11"}'},
        {"kind": "message", "data": f'{{"command_id":"{LAST_COMMAND_ID}"}}'},
        {"kind": "message", "data": '{"command_id":"oops"}'},
    ]

    assert latest_command_id(events) == LAST_COMMAND_ID
