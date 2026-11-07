# Data dictionary

All identifiers are immutable text primary keys unless a bridge table uses a composite key. Timestamps are UTC ISO-8601 (`Z`). Empty string means optional value absent. Dates use ISO `YYYY-MM-DD`; minutes are integer minutes.

| Entity/table | Primary key | Fields (type; required unless `?`) | Validation / relationship |
|---|---|---|---|
| Plant | `plant_id` | `plant_name` text, `site_code` text, `country` text, `timezone` text, `lifecycle_state` enum, `effective_from` date, `effective_to` date? | `site_code` unique; lifecycle ACTIVE/INACTIVE; effective_to >= effective_from |
| Machine | `machine_id` | `plant_id` FK, `machine_name` text, `machine_type` enum-like text, `criticality` A/B/C, `lifecycle_state` ACTIVE/INACTIVE, `commissioned_on` date, `retired_on` date? | Plant 1:N Machine; machine belongs to one plant |
| SafetyZone | `safety_zone_id` | `plant_id` FK, `zone_name` text, `risk_level` LOW/MEDIUM/HIGH, `effective_from` date, `effective_to` date? | Plant 1:N zone; SAFE-<plant-id>-NNN |
| Interlock | `interlock_id` | `plant_id` FK, `interlock_name` text, `required_state` ENGAGED, `permitted_machine_states` pipe-delimited text, `lifecycle_state` ACTIVE/INACTIVE | Plant 1:N interlock; machine assignment via bridge |
| AlarmDefinition | `alarm_definition_id` | `machine_id` FK, `alarm_code` text, `alarm_name` text, `severity` INFO/LOW/MEDIUM/HIGH/CRITICAL, `ack_required` Y/N, `ack_sla_minutes` integer, `nuisance_candidate` Y/N, `active_from` date, `active_to` date? | Machine 1:N definitions; SLA > 0; HIGH/CRITICAL require ack |
| AlarmEvent | `alarm_event_id` | `machine_id` FK, `alarm_definition_id` FK, `event_ts` UTC datetime, `severity` enum, `event_type` text, `machine_state` STOPPED/IDLE/RUNNING/MAINTENANCE/FAULT, `interlock_state` ENGAGED/DISENGAGED/BYPASSED, `operator_shift_id` FK?, `source_event_id` text?, `replay_flag` Y/N, `nuisance_flag` Y/N, `issue_type` text?,  | ALM-<machine-id>-NNNNNN; ordered by event_ts; replay source identifies original |
| OperatorShift | `shift_id` | `plant_id` FK, `machine_id` FK, `operator_id` text, `shift_name` DAY/EVENING/NIGHT, `start_time` time, `end_time` time, `effective_from` date, `effective_to` date | Machine 1:N shifts; plant must match machine's plant |
| Acknowledgement | `acknowledgement_id` | `alarm_event_id` FK, `operator_id` text, `ack_ts` UTC datetime, `ack_status` ACKNOWLEDGED/AUTO_ESCALATED/PENDING, `response_minutes` integer, `issue_type` text?,  | AlarmEvent 1:N ack; ACK-<alarm-id>-NN; ack_ts >= event_ts except labelled negative case |
| Incident | `incident_id` | `machine_id` FK, `alarm_event_id` FK?, `opened_ts` UTC datetime, `incident_type` text, `severity` enum, `incident_status` OPEN/INVESTIGATING/RESOLVED/CLOSED, `trigger_context` text?, `resolved_ts` datetime? | Machine 1:N incidents; INC-2026-NNNNNN; trigger required except labelled exception |
| CorrectiveAction | `corrective_action_id` | `incident_id` FK, `action_description` text, `owner_role` text, `created_ts` datetime, `completed_ts` datetime?, `action_status` OPEN/IN_PROGRESS/COMPLETED/CLOSED, `verification_status` VERIFIED/NOT_VERIFIED, `verified_ts` datetime?, `issue_type` text?,  | Incident 1:N actions; ACT-<incident-id>-NN; CLOSED requires verified timestamp except labelled case |
| MachineStateEvent | `state_event_id` | `machine_id` FK, `event_ts` datetime, `from_state` text, `to_state` text, `interlock_id` FK, `interlock_state` enum, `source_alarm_event_id` FK?, `issue_type` text?,  | Machine 1:N state history; RUNNING requires ENGAGED interlock |
| MachineZone (bridge) | `(machine_id,safety_zone_id)` | both FKs | Machine N:M SafetyZone; effective period represented by zone's effective dates |
| MachineInterlock (bridge) | `(machine_id,interlock_id,valid_from)` | both FKs, `valid_from` date, `valid_to` date? | Machine N:M Interlock; validity windows must not overlap for same assignment |

## Units, uniqueness and allowed values

- All IDs are unique within their entity and use the documented prefix/counter pattern; counters are zero-padded and never reused.
- `ack_sla_minutes` and `response_minutes` are minutes; event/action timestamps are UTC; machine criticality is A/B/C.
- Severity: INFO, LOW, MEDIUM, HIGH, CRITICAL. Machine states: STOPPED, IDLE, RUNNING, MAINTENANCE, FAULT. Interlock states: ENGAGED, DISENGAGED, BYPASSED.
- Y/N fields accept only Y or N. Lifecycle states accept ACTIVE/INACTIVE. Dates and timestamps must parse as ISO values.
- `issue_type` is populated only on deliberately injected edge cases. Expected labels and adjudication rules live only in the separate `ground_truth.csv/json` files; no ground-truth target column is present in operational input tables.

## Field-level catalogue (requiredness, domains, units and checks)

Notation: **R** = required, **O** = optional (empty string represents absent); `PK` = primary key; `FK` = foreign key. All IDs are immutable text. All timestamps are UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`); dates are `YYYY-MM-DD`; durations are integer minutes. No personal data is generated; operator identifiers are synthetic codes.

| Table | Field | Type / requiredness | Domain, unit, uniqueness and validation |
|---|---|---|---|
| Plant | plant_id | TEXT R PK | `PLT-NNN`; unique, immutable |
| Plant | plant_name | TEXT R | Non-empty display name |
| Plant | site_code | TEXT R | Unique `SITE-NNN` |
| Plant | country | TEXT R | ISO-like country code; generated `IN` |
| Plant | timezone | TEXT R | IANA-style timezone label; generated `UTC` |
| Plant | lifecycle_state | TEXT R | `ACTIVE` or `INACTIVE` |
| Plant | effective_from / effective_to | DATE R / O | End date must not precede start date |
| Machine | machine_id | TEXT R PK | `MCH-NNN`; unique, immutable |
| Machine | plant_id | TEXT R FK | Must reference Plant; machine's plant is authoritative |
| Machine | machine_name | TEXT R | Non-empty |
| Machine | machine_type | TEXT R | `PRESS`, `CONVEYOR`, `ROBOT`, `CUTTER`, `PACKER` |
| Machine | criticality | TEXT R | `A`, `B`, `C` |
| Machine | lifecycle_state | TEXT R | `ACTIVE` or `INACTIVE` |
| Machine | commissioned_on / retired_on | DATE R / O | Retired date cannot precede commissioning |
| SafetyZone | safety_zone_id | TEXT R PK | `SAFE-<plant-id>-NNN`; unique |
| SafetyZone | plant_id | TEXT R FK | Must reference Plant |
| SafetyZone | zone_name | TEXT R | Non-empty within plant |
| SafetyZone | risk_level | TEXT R | `LOW`, `MEDIUM`, `HIGH` |
| SafetyZone | effective_from / effective_to | DATE R / O | End date must not precede start date |
| Interlock | interlock_id | TEXT R PK | `INT-NNN`; unique |
| Interlock | plant_id | TEXT R FK | Must reference Plant |
| Interlock | interlock_name | TEXT R | Non-empty |
| Interlock | required_state | TEXT R | `ENGAGED` |
| Interlock | permitted_machine_states | TEXT R | Pipe-delimited machine-state enum values |
| Interlock | lifecycle_state | TEXT R | `ACTIVE` or `INACTIVE` |
| AlarmDefinition | alarm_definition_id | TEXT R PK | `ALD-NNNN`; unique |
| AlarmDefinition | machine_id | TEXT R FK | Must reference Machine |
| AlarmDefinition | alarm_code | TEXT R | Unique within machine; non-empty |
| AlarmDefinition | alarm_name | TEXT R | Non-empty |
| AlarmDefinition | severity | TEXT R | `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| AlarmDefinition | ack_required | TEXT R | `Y`/`N`; HIGH and CRITICAL must be `Y` |
| AlarmDefinition | ack_sla_minutes | INTEGER R | Minutes; strictly greater than zero |
| AlarmDefinition | nuisance_candidate | TEXT R | `Y`/`N` |
| AlarmDefinition | active_from / active_to | DATE R / O | End date must not precede start date |
| OperatorShift | shift_id | TEXT R PK | Unique `SHF-MCH-NNN-X` |
| OperatorShift | plant_id / machine_id | TEXT R FK | Both must exist; plant must equal machine's plant |
| OperatorShift | operator_id | TEXT R | Synthetic `OP-NNN` code |
| OperatorShift | shift_name | TEXT R | `DAY`, `EVENING`, `NIGHT` |
| OperatorShift | start_time / end_time | TIME R | `HH:MM`; valid clock times |
| OperatorShift | effective_from / effective_to | DATE R | Valid date range |
| MachineZone | machine_id / safety_zone_id | TEXT R composite PK + FK | Both parents must exist and belong to same plant; pair unique |
| MachineInterlock | machine_id / interlock_id / valid_from | TEXT/DATE R composite PK + FK | Both parents must exist and belong to same plant; assignment effective dates valid |
| MachineInterlock | valid_to | DATE O | Must be on/after valid_from |
| AlarmEvent | alarm_event_id | TEXT R PK | `ALM-<machine-id>-NNNNNN`; unique, immutable |
| AlarmEvent | machine_id / alarm_definition_id | TEXT R FK | Both exist; alarm definition must belong to same machine |
| AlarmEvent | event_ts | TIMESTAMP R | UTC; chronological stream ordering |
| AlarmEvent | severity | TEXT R | Severity enum; must match referenced definition |
| AlarmEvent | event_type | TEXT R | `ALARM_RAISED` or `ALARM_FLOOD` |
| AlarmEvent | machine_state / interlock_state | TEXT R | Machine/interlock enums; unsafe combinations require incident traceability |
| AlarmEvent | operator_shift_id | TEXT O FK | If present, shift must belong to same machine |
| AlarmEvent | source_event_id | TEXT O | Replay source event ID; must resolve for replay records |
| AlarmEvent | replay_flag / nuisance_flag | TEXT R | `Y`/`N`; replay excluded from unique-event metric |
| AlarmEvent | issue_type | TEXT O | Only documented anomaly labels; not a ground-truth target |
| MachineStateEvent | state_event_id | TEXT R PK | `STE-NNNNNN`; unique |
| MachineStateEvent | machine_id / interlock_id | TEXT R FK | Both parents must exist |
| MachineStateEvent | event_ts | TIMESTAMP R | UTC; history is append-only and ordered |
| MachineStateEvent | from_state / to_state | TEXT R | Machine-state enum |
| MachineStateEvent | interlock_state | TEXT R | `ENGAGED`, `DISENGAGED`, `BYPASSED`; unsafe state must be incident-linked or explicitly labelled |
| MachineStateEvent | source_alarm_event_id | TEXT O FK | If present, must reference AlarmEvent |
| MachineStateEvent | issue_type | TEXT O | Documented exception marker only |
| Acknowledgement | acknowledgement_id | TEXT R PK | `ACK-<alarm-event-id>-NN`; unique |
| Acknowledgement | alarm_event_id | TEXT R FK | Must reference AlarmEvent |
| Acknowledgement | operator_id | TEXT R | Synthetic operator code |
| Acknowledgement | ack_ts | TIMESTAMP R | UTC; must be at/after alarm time except labelled negative test |
| Acknowledgement | ack_status | TEXT R | `ACKNOWLEDGED`, `AUTO_ESCALATED`, `PENDING` |
| Acknowledgement | response_minutes | INTEGER R | Minutes; derived from event/ack timestamps; non-negative except labelled negative test |
| Acknowledgement | issue_type | TEXT O | Documented exception marker only |
| Incident | incident_id | TEXT R PK | `INC-2026-NNNNNN`; unique |
| Incident | machine_id | TEXT R FK | Must reference Machine |
| Incident | alarm_event_id | TEXT O FK | Triggering AlarmEvent; missing only for explicit negative test |
| Incident | opened_ts / resolved_ts | TIMESTAMP R / O | UTC; resolution cannot precede opening |
| Incident | incident_type | TEXT R | Non-empty business classification |
| Incident | severity | TEXT R | Severity enum |
| Incident | incident_status | TEXT R | `OPEN`, `INVESTIGATING`, `RESOLVED`, `CLOSED` |
| Incident | trigger_context | TEXT O | Required when no triggering alarm is linked |
| Incident | issue_type | TEXT O | Documented exception marker only |
| CorrectiveAction | corrective_action_id | TEXT R PK | `ACT-<incident-id>-NN`; unique |
| CorrectiveAction | incident_id | TEXT R FK | Must reference Incident |
| CorrectiveAction | action_description / owner_role | TEXT R | Non-empty action and responsible role |
| CorrectiveAction | created_ts / completed_ts / verified_ts | TIMESTAMP R / O / O | UTC; completion >= creation; verification >= completion |
| CorrectiveAction | action_status | TEXT R | `OPEN`, `IN_PROGRESS`, `COMPLETED`, `CLOSED` |
| CorrectiveAction | verification_status | TEXT R | `VERIFIED` or `NOT_VERIFIED`; CLOSED requires VERIFIED and verified_ts |
| CorrectiveAction | issue_type | TEXT O | Documented exception marker only |

## Cardinality and optionality summary

- Plant 1:N Machine, SafetyZone and Interlock.
- Machine 1:N AlarmDefinition, OperatorShift, AlarmEvent, MachineStateEvent and Incident.
- AlarmEvent 1:N Acknowledgement; AlarmEvent 0:N Incident (an incident can have one optional triggering alarm in this implementation).
- Incident 1:N CorrectiveAction.
- Machine N:M SafetyZone through `machine_zone`; Machine N:M Interlock through `machine_interlock`.
- AlarmEvent 0:1 OperatorShift reference per event; replay source is optional and populated only for replay rows.
- Effective dating is stored on Plant, SafetyZone, MachineInterlock, Machine and AlarmDefinition as applicable. History is retained as event rows rather than overwriting previous machine states.
