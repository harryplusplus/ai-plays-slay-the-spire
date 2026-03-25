#!/usr/bin/env bash

set -euo pipefail

bridge_url="${STS_BRIDGE_URL:-http://localhost:8000}"

curl -fsS \
  -X POST \
  "${bridge_url}/execute" \
  -H 'content-type: application/json' \
  -d '{"command":"STATE"}' |
  jq '
    def short_uuid:
      if . == null then null else split("-")[0] end;

    def power_summary:
      map(
        if (.amount? != null and .amount >= 0) then
          "\(.name) \(.amount)"
        else
          .name
        end
      );

    . as $root
    | ($root.game_state // {}) as $gs
    | ($gs.combat_state // {}) as $cs
    | ($cs.player // {}) as $player
    | {
        command_id: $root.command_id,
        ready_for_command: $root.ready_for_command,
        available_commands: ($root.available_commands // []),
        error: $root.error,
        screen: {
          type: $gs.screen_type,
          name: $gs.screen_name,
          room_phase: $gs.room_phase,
          room_type: $gs.room_type,
          act: $gs.act,
          floor: $gs.floor,
          current_action: $gs.current_action
        },
        run: {
          class: $gs.class,
          hp: (if $gs.current_hp != null and $gs.max_hp != null then "\($gs.current_hp)/\($gs.max_hp)" else null end),
          gold: $gs.gold,
          keys: ($gs.keys // null),
          relic_count: (($gs.relics // []) | length)
        },
        combat: (if ($gs.room_phase == "COMBAT" and $cs != {}) then {
          turn: $cs.turn,
          player: {
            hp: (if $player.current_hp != null and $player.max_hp != null then "\($player.current_hp)/\($player.max_hp)" else null end),
            block: $player.block,
            energy: $player.energy,
            powers: (($player.powers // []) | power_summary),
            orbs: (
              ($player.orbs // [])
              | map(
                  if .id == "Empty" then
                    "Empty"
                  else
                    "\(.name)(p:\(.passive_amount)/e:\(.evoke_amount))"
                  end
                )
            )
          },
          monsters: (
            ($cs.monsters // [])
            | map({
                name,
                hp: "\(.current_hp)/\(.max_hp)",
                block,
                intent: (
                  if (.move_adjusted_damage? != null and .move_adjusted_damage >= 0) then
                    "\(.intent) \(.move_adjusted_damage)x\(.move_hits // 1)"
                  else
                    .intent
                  end
                ),
                powers: ((.powers // []) | power_summary)
              })
          ),
          hand: (
            ($cs.hand // [])
            | to_entries
            | map({
                card_index: (.key + 1),
                name: .value.name,
                cost: .value.cost,
                playable: .value.is_playable,
                has_target: .value.has_target,
                uuid: (.value.uuid | short_uuid)
              })
          )
        } else null end),
        potions: (
          ($gs.potions // [])
          | to_entries
          | map({
              slot: .key,
              name: .value.name,
              can_use: .value.can_use,
              can_discard: .value.can_discard,
              requires_target: .value.requires_target
            })
        ),
        choices: (
          if ($gs.screen_state.options? != null) then
            (
              $gs.screen_state.options
              | map({
                  choice_index,
                  label,
                  text,
                  disabled
                })
            )
          elif ($gs.choice_list? != null) then
            (
              $gs.choice_list
              | to_entries
              | map({
                  inferred_choice_index: .key,
                  label: .value
                })
            )
          else
            null
          end
        ),
        grid_cards: (
          if $gs.screen_type == "GRID" then
            (
              ($gs.screen_state.cards // [])
              | to_entries
              | map({
                  inferred_choice_index: .key,
                  name: .value.name,
                  cost: .value.cost,
                  playable: .value.is_playable,
                  uuid: (.value.uuid | short_uuid)
                })
            )
          else
            null
          end
        )
      }
  '
