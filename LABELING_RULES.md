# Labeling Rules

## Process

The first pass was AI-drafted and the baseline output was visible during drafting. The labels were then cleaned: all baseline-anchoring notes removed, labels re-checked against tools.json only, and the schema corrected.

## Scoring

| label_type | correct | acceptable | wrong | critical |
|---|---|---|---|---|
| single_tool | expected_tool | - | any other tool or abstain | - |
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

## Entity Detection

### Purchase Orders vs Job Work POs
- "job work po" / "jobwork po" → jobwork_po_count or jobwork_po_list
- Plain "po" / "purchase order" → purchase_po_count or purchase_po_list
- Longer phrase wins

### GRN vs PO
- "grn" / "goods receipt" → purchase_grn_count or purchase_grn_list

### Stock vs Item Master
- "stock" (quantity on hand) → inventory_stock_* tools
- "item master" / "catalogue" → inventory_item_master_* tools

### Sales Orders vs Sales Invoices
- "sales order" / "so" → sales_so_* tools
- "invoice" → sales_invoice_count or finance_invoice_overdue_list

### Payments vs Receivables
- "payment" (outgoing) → finance_payment_* tools
- "outstanding" / "receivable" (incoming) → finance_outstanding_total

### Gate Pass
- "gate pass" → gatepass_* tools

### Material Issues vs Indents
- "material issue" / "issue slip" → store_issue_* tools
- "indent" → store_indent_pending_count

### Action Items vs MoM
- "action item" → mom_action_item_* tools
- "meeting" / "mom" → mom_* or mom_list

## Output Shape

- "how many", "count", "number of" → count or scalar output_type
- "list", "show", "which", "display" → list output_type
- "total value", "total amount" → scalar output_type
- Shape constrains choices within entity, does not override entity

## Special Cases

### Write/Mutation Requests
Any query requesting approval, deletion, update, or creation is refuse_mutation. Must abstain. Routing to any tool is a critical failure.

### How-to and Procedural
Queries asking how to perform an action or explaining a process are not_a_data_query. Must abstain.

### Comparison and Analytics
Queries requesting comparison (e.g., "compare this month with last month") or ranking (e.g., "top 5 vendors") have no matching tool and are no_tool unless a single call provides partial info (lossy_fit).

### Count Query with List-Only Tool
When query asks "how many" but only a list tool exists (e.g., q122 jobwork_vendor_list), label as lossy_fit with closest_tool set to the list tool.

### List Query with Count-Only Tool
When query wants a list (e.g., "which") but only a count tool exists (e.g., q091 gatepass_pending_return_count), label as lossy_fit with closest_tool set to the count tool.

### Multi-Intent
Queries containing multiple requests (e.g., "how many and what does that mean") are multi_intent. Route to the primary data retrieval intent.

### Typos and Informal Language
Typos (q028 "pendin po cnt") are still routable if intent is clear. Tag as typo but label as single_tool.

Non-English queries (q043 Hindi) are treated the same as their English equivalent if the intent is clear. Tag as hinglish.

All caps (q103) is stylistic only, does not affect routing.

Polite phrasing (q101 "Could you tell me") is stylistic only.

### Vague Queries
Queries with no entity (q010 "how many are there?", q035 "total value", q061 "stock") are needs_clarification.

### Session Context
Queries requiring prior conversation context (q077 "send me that list again") are needs_clarification.

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
