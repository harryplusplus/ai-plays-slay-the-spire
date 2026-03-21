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

    {
        available_commands,
        screen_type: .game_state.screen_type,
        screen_name: .game_state.screen_name,
        room_phase: .game_state.room_phase,
        floor: .game_state.floor,
        act: .game_state.act,
        hp: "\(.game_state.current_hp)/\(.game_state.max_hp)",
        gold: .game_state.gold,
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
