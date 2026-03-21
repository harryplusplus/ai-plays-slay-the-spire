#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
limit="${1:-20}"

state_json="$("$script_dir/sts-state-latest.sh" "$limit")"

printf '%s\n' "$state_json" | jq -r '
    def power_lines:
        [ .[]? | "\(.name) \(.amount)" ];

    def orb_lines:
        [ .[]? | if .name == "Orb Slot" then "Empty" else "\(.name) p\(.passive_amount)/e\(.evoke_amount)" end ];

    def hand_lines:
        [ range(0; length) as $i
          | .[$i]
          | {
                slot: ($i + 1),
                name,
                cost,
                playable: .is_playable,
                target: .has_target
            }
        ];

    def monster_lines:
        [ range(0; length) as $i
          | .[$i]
          | {
                index: $i,
                name,
                hp: .current_hp,
                max_hp,
                block,
                intent,
                damage: (
                    if (.move_adjusted_damage // -1) < 0 then null
                    elif (.move_hits // 1) > 1 then "\(.move_adjusted_damage) x \(.move_hits)"
                    else "\(.move_adjusted_damage)"
                    end
                ),
                powers: ([ .powers[]? | "\(.name) \(.amount)" ])
            }
        ];

    def map_node_lines:
        [ .[]? | { x, y, symbol, has_emerald_key } ];

    def option_lines:
        [ .[]? | { choice_index, label, disabled } ];

    {
        available_commands,
        screen_type: .game_state.screen_type,
        screen_name: .game_state.screen_name,
        room_phase: .game_state.room_phase,
        floor: .game_state.floor,
        act: .game_state.act,
        hp: "\(.game_state.current_hp)/\(.game_state.max_hp)",
        gold: .game_state.gold,
        keys: (.game_state.keys // null),
        choice_list: (.game_state.choice_list // null),
        screen: (
            if (.game_state.combat_state | type) == "object" then null
            else {
                event_id: (.game_state.screen_state.event_id // null),
                event_name: (.game_state.screen_state.event_name // null),
                options: (.game_state.screen_state.options | option_lines),
                current_node: (
                    .game_state.screen_state.current_node
                    | if . == null then null else { x, y, symbol, has_emerald_key } end
                ),
                next_nodes: (.game_state.screen_state.next_nodes | map_node_lines),
                grid: (
                    if .game_state.screen_type != "GRID" then null
                    else {
                        num_cards: (.game_state.screen_state.num_cards // null),
                        selected_cards: [ .game_state.screen_state.selected_cards[]? | .name ],
                        confirm_up: (.game_state.screen_state.confirm_up // false),
                        for_purge: (.game_state.screen_state.for_purge // false),
                        for_upgrade: (.game_state.screen_state.for_upgrade // false),
                        for_transform: (.game_state.screen_state.for_transform // false),
                        any_number: (.game_state.screen_state.any_number // false)
                    }
                    end
                )
            }
            end
        ),
        combat: (
            if (.game_state.combat_state | type) != "object" then null
            else {
                turn: .game_state.combat_state.turn,
                energy: .game_state.combat_state.player.energy,
                block: .game_state.combat_state.player.block,
                hand: (.game_state.combat_state.hand | hand_lines),
                monsters: (.game_state.combat_state.monsters | monster_lines),
                orbs: (.game_state.combat_state.player.orbs | orb_lines),
                powers: (.game_state.combat_state.player.powers | power_lines),
                discard_zero_cost: [
                    .game_state.combat_state.discard_pile[]?
                    | select(.cost == 0)
                    | .name
                ]
            }
            end
        )
    }
'
