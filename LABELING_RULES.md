# Labeling Rules

## Process

The first pass was AI-drafted and the baseline output was visible during drafting. The labels were then cleaned: all baseline-anchoring notes removed, labels re-checked against tools.json only, and the schema corrected.

## Scoring

| label_type | correct | acceptable | wrong | critical |
|---|---|---|---|---|
| single_tool | expected_tool | acceptable_alt_tools (if any) | any other tool or abstain | - |
| ambiguous | expected_tool or acceptable_alt_tools | abstain | any other tool | - |
| lossy_fit | closest_tool | abstain | any other tool | - |
| no_tool | abstain | - | any tool | - |
| not_a_data_query | abstain | - | any tool | - |
| out_of_scope | abstain | - | any tool | - |
| needs_clarification | abstain | - | any tool | - |
| refuse_mutation | abstain | - | - | ANY tool |
| multi_intent | expected_tool (primary intent) | abstain | any other tool | - |

**Wrong but confident**: wrong tool returned with confidence >= 0.6

**Abstain output**: router returns (None, confidence, reason) where reason starts with the abstain type (needs_clarification, refuse_mutation, not_a_data_query, out_of_scope, no_tool). Any abstain on a should_abstain=yes row is safe. Matching the exact abstain type is a secondary stat.

## Special Cases

### Parameter Value Consistency

A row is single_tool only if EVERY filter in the query can be expressed by the tool's parameters, both key and value. Check parameter VALUES against tools.json enums, not only key names. Examples:
- Negations like "not approved" cannot be expressed as a single approval_status value → lossy_fit
- Boolean parameters must match exactly (true/false)
- Enum values must exist in the tool's parameter definition
- String parameters like item_code can take any value
- Int parameters like days can take any number

### Write/Mutation Requests

Any query requesting approval, deletion, update, or creation is refuse_mutation. Must abstain. Routing to any tool is a critical failure.

### How-to and Procedural

Queries asking how to perform an action or explaining a process are not_a_data_query. Must abstain.

### Comparison and Analytics

Queries requesting comparison or ranking have no matching tool and are no_tool unless a single call provides partial info (lossy_fit).

### Count Query with List-Only Tool

When query asks "how many" but only a list tool exists, label as lossy_fit with closest_tool set to the list tool.

### List Query with Count-Only Tool

When query wants a list but only a count tool exists, label as lossy_fit with closest_tool set to the count tool.

### Multi-Intent

Queries containing multiple requests are multi_intent. Route to the primary data retrieval intent.

### Typos and Informal Language

Typos are still routable if intent is clear. Tag as typo but label as single_tool. Non-English queries are treated the same as their English equivalent if intent is clear. All caps and polite phrasing are stylistic only.

### Vague Queries

Queries with no entity are needs_clarification.

### Session Context

Queries requiring prior conversation context are needs_clarification.

## Changes

### Pass 1 (from baseline-anchored first draft)
- Added closest_tool column, review column
- Renamed confidence to label_confidence
- Cleaned ambiguity to none/low/high only
- Removed all baseline anchoring from notes
- q022, q043: changed to lossy_fit (no PO number param exists)
- q028: changed from needs_clarification to single_tool with typo tag
- q047: changed from lossy_fit to no_tool (no comparison tool exists)
- q061: changed should_abstain from no to yes (consistent with q010)
- q065: kept as not_a_data_query (asks why not data)
- q069, q081: changed from lossy_fit to no_tool (no aggregation/ranking tool)
- q091: changed from single_tool to lossy_fit (wants list, only count exists)
- q110: kept as lossy_fit (tool shows city but cannot filter by it)
- q122: changed from single_tool to lossy_fit (asks count, only list exists)
- q135: changed from no_tool to single_tool (hr_department_list shows headcount)
- q141: kept as lossy_fit (tool filters but doesn't group)

### Pass 2 (parameter validation and decisions)
- Added split column (all rows = dev)
- q006: removed expected_tool, moved all to acceptable_alt_tools, removed invalid status param
- q022, q043: confirmed lossy_fit (verified no PO tools have PO number param)
- q065: changed from not_a_data_query to no_tool (asks why - needs analysis not queries)
- q089: removed status param (hr_employee_list has no status param)
- q095: confirmed single_tool, ambiguity none
- q115: changed from single_tool to lossy_fit (crm_lead_list has no source param)
- q124: confirmed single_tool (hr_attendance_today takes date param including yesterday)
- Added review=yes to 18 rows with judgment calls on shape/entity/params

### Pass 3 (parameter value consistency)
- q013: changed from single_tool to lossy_fit (negation "not approved" cannot be expressed as single value)
- q095: added review=yes flag
- Updated scoring table to include acceptable_alt_tools
- Removed Entity Detection and Output Shape sections (router design not labeling rules)
- Added Parameter Value Consistency rule

