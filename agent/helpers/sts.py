from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypeGuard
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Sequence

BASE_URL: Final = "http://localhost:8000"
EVENT_POLL_LIMIT: Final = 20
EVENT_POLL_INTERVAL_SECONDS: Final = 0.25
EVENT_POLL_TIMEOUT_SECONDS: Final = 20.0

JsonObject = dict[str, object]
JsonArray = list[object]


@dataclass(frozen=True)
class ChoiceOption:
    index: int
    display: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CardOption:
    index: int
    display: str
    aliases: tuple[str, ...]
    has_target: bool
    is_playable: bool


@dataclass(frozen=True)
class MonsterOption:
    index: int
    display: str
    aliases: tuple[str, ...]
    is_targetable: bool


def _post_json(path: str, payload: JsonObject) -> JsonObject:
    previous_command_id = latest_command_id(fetch_events(EVENT_POLL_LIMIT))
    data = json.dumps(payload).encode("utf-8")
    request = Request(  # noqa: S310
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return _expect_object(_read_json(request), context="response")
    except TimeoutError:
        if path != "/execute":
            raise SystemExit("Bridge request timed out") from None
        response = _poll_for_execute_response(previous_command_id)
        if response is None:
            raise SystemExit("Bridge request timed out") from None
        return response


def _get_json(path: str, params: dict[str, str] | None = None) -> object:
    suffix = ""
    if params:
        suffix = f"?{urlencode(params)}"
    request = Request(f"{BASE_URL}{path}{suffix}", method="GET")  # noqa: S310
    return _read_json(request)


def _read_json(request: Request) -> object:
    try:
        with urlopen(request, timeout=35) as response:  # noqa: S310
            return json.load(response)
    except TimeoutError as error:
        raise TimeoutError from error
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {error.code}: {body}") from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError | socket.timeout):
            raise TimeoutError from error
        raise SystemExit(f"Bridge request failed: {error.reason}") from error


def fetch_state() -> JsonObject:
    response = _post_json("/execute", {"command": "STATE"})
    _raise_if_error(response)
    return response


def run_command(command: str) -> JsonObject:
    response = _post_json("/execute", {"command": command})
    _raise_if_error(response)
    return response


def fetch_events(limit: int) -> list[JsonObject]:
    response = _get_json("/events", {"limit": str(limit)})
    items = _maybe_array(response)
    if items is None:
        raise SystemExit("Unexpected /events response")
    collected: list[JsonObject] = []
    for raw_item in items:
        item = _maybe_object(raw_item)
        if item is not None:
            collected.append(item)
    return collected


def _poll_for_execute_response(previous_command_id: int | None) -> JsonObject | None:
    deadline = time.monotonic() + EVENT_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        responses = message_responses(fetch_events(EVENT_POLL_LIMIT))
        for response in reversed(responses):
            command_id = _command_id(response)
            if command_id is None:
                continue
            if previous_command_id is None or command_id > previous_command_id:
                return response
        time.sleep(EVENT_POLL_INTERVAL_SECONDS)
    return None


def message_responses(events: Sequence[JsonObject]) -> list[JsonObject]:
    responses: list[JsonObject] = []
    for event in events:
        if _maybe_str(event.get("kind")) != "message":
            continue
        raw_data = _maybe_str(event.get("data"))
        if raw_data is None:
            continue
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            continue
        response = _maybe_object(payload)
        if response is not None:
            responses.append(response)
    return responses


def latest_command_id(events: Sequence[JsonObject]) -> int | None:
    latest: int | None = None
    for response in message_responses(events):
        command_id = _command_id(response)
        if command_id is None:
            continue
        latest = command_id
    return latest


def _command_id(response: JsonObject) -> int | None:
    raw_command_id = response.get("command_id")
    if isinstance(raw_command_id, int):
        return raw_command_id
    command_id = _maybe_str(raw_command_id)
    if command_id is None or not command_id.isdecimal():
        return None
    return int(command_id)


def _raise_if_error(response: JsonObject) -> None:
    error = _maybe_str(response.get("error"))
    if error:
        raise SystemExit(error)


def normalize_text(text: str) -> str:
    parts = [
        character.casefold() if character.isalnum() else " "
        for character in text.strip()
    ]
    return " ".join("".join(parts).split())


def render_upgraded_name(name: str, upgrades: int) -> str:
    if upgrades <= 0 or "+" in name:
        return name
    suffix = "+" if upgrades == 1 else f"+{upgrades}"
    return f"{name}{suffix}"


def _game_state(state: JsonObject) -> JsonObject:
    return _expect_object(state.get("game_state"), context="game_state")


def _combat_state(state: JsonObject) -> JsonObject | None:
    return _maybe_object(_game_state(state).get("combat_state"))


def collect_choices(state: JsonObject) -> list[ChoiceOption]:
    game_state = _game_state(state)
    choices = _maybe_array(game_state.get("choice_list")) or []
    screen_state = _maybe_object(game_state.get("screen_state"))
    options = None
    if screen_state is not None:
        options = _maybe_array(screen_state.get("options"))

    collected: list[ChoiceOption] = []
    if options is not None:
        for position, raw_option in enumerate(options):
            option = _maybe_object(raw_option)
            if option is None:
                continue
            raw_index = option.get("choice_index")
            choice_index = raw_index if isinstance(raw_index, int) else position
            names = _names_from_option(option)
            if position < len(choices):
                choice_name = _maybe_str(choices[position])
                if choice_name is not None:
                    names.append(choice_name)
            aliases = tuple(dict.fromkeys(name for name in names if name))
            display = aliases[0] if aliases else f"Choice {choice_index}"
            collected.append(
                ChoiceOption(
                    index=choice_index,
                    display=display,
                    aliases=aliases,
                )
            )
        if collected:
            return collected

    for position, raw_choice in enumerate(choices):
        choice = _maybe_str(raw_choice)
        if choice is None:
            continue
        collected.append(
            ChoiceOption(index=position, display=choice, aliases=(choice,))
        )
    return collected


def _names_from_option(option: JsonObject) -> list[str]:
    names: list[str] = []
    for key in ("label", "choice", "name", "text"):
        value = _maybe_str(option.get(key))
        if value is not None:
            names.append(value)
    return names


def resolve_choice(state: JsonObject, selector: str) -> int:
    if selector.isdecimal():
        return int(selector)
    choices = collect_choices(state)
    match_index = _resolve_named_position(
        selector=selector,
        displays=[choice.display for choice in choices],
        aliases=[choice.aliases for choice in choices],
        kind="choice",
    )
    return choices[match_index].index


def collect_cards(state: JsonObject) -> list[CardOption]:
    combat_state = _combat_state(state)
    if combat_state is None:
        return []
    hand = _maybe_array(combat_state.get("hand")) or []
    return _collect_cards_from_hand(hand)


def _collect_cards_from_hand(hand: JsonArray) -> list[CardOption]:
    cards: list[CardOption] = []
    for position, raw_card in enumerate(hand, start=1):
        card = _maybe_object(raw_card)
        if card is None:
            continue
        name = _maybe_str(card.get("name"))
        if name is None:
            continue
        upgrades = _int_or_default(card.get("upgrades"), 0)
        display = render_upgraded_name(name, upgrades)
        aliases = tuple(dict.fromkeys((name, display)))
        cards.append(
            CardOption(
                index=position,
                display=display,
                aliases=aliases,
                has_target=_is_true(card.get("has_target")),
                is_playable=_is_true(card.get("is_playable")),
            )
        )
    return cards


def resolve_card(state: JsonObject, selector: str) -> CardOption:
    cards = [card for card in collect_cards(state) if card.is_playable]
    if selector.isdecimal():
        card_index = int(selector)
        for card in cards:
            if card.index == card_index:
                return card
        raise SystemExit(f"Playable card index not found: {card_index}")
    match_index = _resolve_named_position(
        selector=selector,
        displays=[card.display for card in cards],
        aliases=[card.aliases for card in cards],
        kind="card",
    )
    return cards[match_index]


def collect_monsters(state: JsonObject) -> list[MonsterOption]:
    combat_state = _combat_state(state)
    if combat_state is None:
        return []
    monsters = _maybe_array(combat_state.get("monsters")) or []
    return _collect_monsters_from_list(monsters)


def _collect_monsters_from_list(monsters: JsonArray) -> list[MonsterOption]:
    collected: list[MonsterOption] = []
    for position, raw_monster in enumerate(monsters):
        monster = _maybe_object(raw_monster)
        if monster is None:
            continue
        name = _maybe_str(monster.get("name"))
        if name is None:
            continue
        current_hp = _int_or_default(monster.get("current_hp"), 0)
        is_targetable = (
            not _is_true(monster.get("is_gone"))
            and not _is_true(monster.get("half_dead"))
            and current_hp > 0
        )
        collected.append(
            MonsterOption(
                index=position,
                display=name,
                aliases=(name,),
                is_targetable=is_targetable,
            )
        )
    return collected


def resolve_monster(state: JsonObject, selector: str) -> MonsterOption:
    monsters = [monster for monster in collect_monsters(state) if monster.is_targetable]
    if selector.isdecimal():
        target_index = int(selector)
        for monster in monsters:
            if monster.index == target_index:
                return monster
        raise SystemExit(f"Targetable monster index not found: {target_index}")
    match_index = _resolve_named_position(
        selector=selector,
        displays=[monster.display for monster in monsters],
        aliases=[monster.aliases for monster in monsters],
        kind="monster",
    )
    return monsters[match_index]


def _resolve_named_position(
    *,
    selector: str,
    displays: Sequence[str],
    aliases: Sequence[tuple[str, ...]],
    kind: str,
) -> int:
    normalized_selector = normalize_text(selector)
    exact_matches = [
        index
        for index, option_aliases in enumerate(aliases)
        if normalized_selector in {normalize_text(alias) for alias in option_aliases}
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        exact_names = [displays[index] for index in exact_matches]
        raise SystemExit(_ambiguous_message(kind, selector, exact_names))

    partial_matches = [
        index
        for index, option_aliases in enumerate(aliases)
        if any(normalized_selector in normalize_text(alias) for alias in option_aliases)
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]
    if len(partial_matches) > 1:
        raise SystemExit(
            _ambiguous_message(
                kind,
                selector,
                [displays[index] for index in partial_matches],
            )
        )
    raise SystemExit(f"{kind.capitalize()} not found: {selector}")


def _ambiguous_message(
    kind: str,
    selector: str,
    matches: Sequence[str],
) -> str:
    return f"Ambiguous {kind} '{selector}': {', '.join(matches)}"


def render_summary(state: JsonObject) -> str:
    game_state = _game_state(state)
    lines = [
        f"available: {', '.join(_string_list(state.get('available_commands')))}",
        (
            f"class: {_display_value(game_state.get('class'))}  "
            f"act: {_display_value(game_state.get('act'))}  "
            f"floor: {_display_value(game_state.get('floor'))}"
        ),
        (
            f"screen: {_display_value(game_state.get('screen_type'))}  "
            f"room: {_display_value(game_state.get('room_phase'))}"
        ),
        _player_line(game_state),
        f"keys: {_keys_line(game_state.get('keys'))}",
        f"deck: {_deck_line(game_state.get('deck'))}",
        f"potions: {_potions_line(game_state.get('potions'))}",
    ]

    choices = collect_choices(state)
    if choices:
        lines.append("choices:")
        lines.extend(f"  [{choice.index}] {choice.display}" for choice in choices)

    combat_state = _combat_state(state)
    if combat_state is not None:
        lines.extend(_combat_lines(combat_state))

    return "\n".join(lines)


def _display_value(value: object) -> str:
    return str(value) if value is not None else "-"


def _string_list(value: object) -> list[str]:
    items = _maybe_array(value)
    if items is None:
        return []
    collected: list[str] = []
    for raw_item in items:
        item = _maybe_str(raw_item)
        if item is not None:
            collected.append(item)
    return collected


def _player_line(game_state: JsonObject) -> str:
    current_hp = _display_value(game_state.get("current_hp"))
    max_hp = _display_value(game_state.get("max_hp"))
    gold = _display_value(game_state.get("gold"))
    relics = _maybe_array(game_state.get("relics"))
    relic_count = len(relics) if relics is not None else 0
    return f"player: HP {current_hp}/{max_hp}  gold {gold}  relics {relic_count}"


def _keys_line(raw_keys: object) -> str:
    keys = _maybe_object(raw_keys)
    if keys is None:
        return "-"
    parts = [
        f"E={'Y' if _is_true(keys.get('emerald')) else 'N'}",
        f"R={'Y' if _is_true(keys.get('ruby')) else 'N'}",
        f"S={'Y' if _is_true(keys.get('sapphire')) else 'N'}",
    ]
    return " ".join(parts)


def _deck_line(raw_deck: object) -> str:
    deck = _maybe_array(raw_deck)
    if deck is None:
        return "-"
    names: list[str] = []
    for raw_card in deck:
        card = _maybe_object(raw_card)
        if card is None:
            continue
        name = _maybe_str(card.get("name"))
        if name is None:
            continue
        upgrades = _int_or_default(card.get("upgrades"), 0)
        names.append(render_upgraded_name(name, upgrades))
    counts = Counter(names)
    summary = ", ".join(
        f"{count}x {name}" if count > 1 else name
        for name, count in sorted(counts.items())
    )
    return f"{len(names)} cards [{summary}]"


def _potions_line(raw_potions: object) -> str:
    potions = _maybe_array(raw_potions)
    if potions is None:
        return "-"
    names: list[str] = []
    for raw_potion in potions:
        potion = _maybe_object(raw_potion)
        if potion is None:
            continue
        name = _maybe_str(potion.get("name"))
        if name is not None:
            names.append(name)
    return ", ".join(names) if names else "-"


def _combat_lines(combat_state: JsonObject) -> list[str]:
    lines: list[str] = []

    player = _maybe_object(combat_state.get("player"))
    if player is not None:
        energy = _display_value(player.get("energy"))
        block = _display_value(player.get("block"))
        orbs = _maybe_array(player.get("orbs")) or []
        orb_names: list[str] = []
        for raw_orb in orbs:
            orb = _maybe_object(raw_orb)
            if orb is None:
                continue
            name = _maybe_str(orb.get("name"))
            if name is not None:
                orb_names.append(name)
        lines.append(
            "combat: "
            f"turn {_display_value(combat_state.get('turn'))}  "
            f"energy {energy}  block {block}  "
            f"orbs {', '.join(orb_names) if orb_names else '-'}"
        )

    monsters = _collect_monsters_from_list(
        _maybe_array(combat_state.get("monsters")) or []
    )
    if monsters:
        lines.append("monsters:")
        for monster in monsters:
            raw_monster = _monster_at_index(combat_state, monster.index)
            damage = _int_or_none(raw_monster.get("move_adjusted_damage"))
            hits = _int_or_default(raw_monster.get("move_hits"), 1)
            damage_text = "?"
            if damage is not None and damage >= 0:
                damage_text = f"{damage}x{hits}"
            lines.append(
                "  "
                f"[{monster.index}] {monster.display} "
                f"HP {_display_value(raw_monster.get('current_hp'))}/"
                f"{_display_value(raw_monster.get('max_hp'))} "
                f"block {_display_value(raw_monster.get('block'))} "
                f"intent {_display_value(raw_monster.get('intent'))} {damage_text}"
            )

    cards = _collect_cards_from_hand(_maybe_array(combat_state.get("hand")) or [])
    if cards:
        lines.append("hand:")
        for card in cards:
            target_flag = " target" if card.has_target else ""
            playable_flag = "" if card.is_playable else " unplayable"
            lines.append(f"  [{card.index}] {card.display}{target_flag}{playable_flag}")

    return lines


def _monster_at_index(combat_state: JsonObject, index: int) -> JsonObject:
    monsters = _maybe_array(combat_state.get("monsters")) or []
    if index >= len(monsters):
        return {}
    monster = _maybe_object(monsters[index])
    return {} if monster is None else monster


def _expect_object(value: object, *, context: str) -> JsonObject:
    item = _maybe_object(value)
    if item is None:
        raise SystemExit(f"Expected {context} to be an object")
    return item


def _maybe_object(value: object) -> JsonObject | None:
    if _is_json_object(value):
        return value
    return None


def _maybe_array(value: object) -> JsonArray | None:
    if _is_json_array(value):
        return value
    return None


def _is_json_object(value: object) -> TypeGuard[JsonObject]:
    return isinstance(value, dict)


def _is_json_array(value: object) -> TypeGuard[JsonArray]:
    return isinstance(value, list)


def _maybe_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _int_or_default(value: object, default: int) -> int:
    result = _int_or_none(value)
    return default if result is None else result


def _is_true(value: object) -> bool:
    return value is True


def _print_json(value: object) -> None:
    sys.stdout.write(f"{json.dumps(value, indent=2, ensure_ascii=False)}\n")


def _state_command(_: argparse.Namespace) -> int:
    _print_json(fetch_state())
    return 0


def _summary_command(_: argparse.Namespace) -> int:
    sys.stdout.write(f"{render_summary(fetch_state())}\n")
    return 0


def _events_command(args: argparse.Namespace) -> int:
    _print_json(fetch_events(args.limit))
    return 0


def _raw_command(args: argparse.Namespace) -> int:
    response = run_command(" ".join(args.command))
    _print_json(response)
    return 0


def _choose_command(args: argparse.Namespace) -> int:
    state = fetch_state()
    choice_index = resolve_choice(state, args.selector)
    _print_json(run_command(f"CHOOSE {choice_index}"))
    return 0


def _play_command(args: argparse.Namespace) -> int:
    state = fetch_state()
    card = resolve_card(state, args.card)
    command = f"PLAY {card.index}"
    if card.has_target:
        if args.target is None:
            raise SystemExit("Target is required for this card")
        monster = resolve_monster(state, args.target)
        command = f"{command} {monster.index}"
    _print_json(run_command(command))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drive the local Slay the Spire bridge"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    state_parser = subparsers.add_parser("state", help="Print raw STATE response")
    state_parser.set_defaults(func=_state_command)

    summary_parser = subparsers.add_parser(
        "summary",
        help="Print a condensed state summary",
    )
    summary_parser.set_defaults(func=_summary_command)

    events_parser = subparsers.add_parser("events", help="Print recent bridge events")
    events_parser.add_argument("--limit", type=int, default=5)
    events_parser.set_defaults(func=_events_command)

    raw_parser = subparsers.add_parser("command", help="Send a raw command string")
    raw_parser.add_argument("command", nargs="+")
    raw_parser.set_defaults(func=_raw_command)

    choose_parser = subparsers.add_parser("choose", help="Choose by name or index")
    choose_parser.add_argument("selector")
    choose_parser.set_defaults(func=_choose_command)

    play_parser = subparsers.add_parser(
        "play",
        help="Play a card by name or hand index",
    )
    play_parser.add_argument("card")
    play_parser.add_argument("--target")
    play_parser.set_defaults(func=_play_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
