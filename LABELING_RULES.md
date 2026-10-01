# Labeling Rules

## Label Type Vocabulary

### single_tool
The query clearly maps to exactly one tool with no ambiguity.
- **Scoring**: Correct tool = correct; wrong tool = incorrect; abstain = incorrect

### ambiguous
The query could reasonably map to multiple tools, or lacks sufficient context to choose definitively.
- **Example**: q006 "show me pending orders" — could be PO, SO, work orders, payments, inspections, etc.
- **Scoring**: Any reasonable interpretation = acceptable; abstain with needs_clarification = correct

### no_tool
The query doesn't match any available tool but isn't out of scope.
- **Example**: q055 "list qualified leads" — we have crm_lead_list but it can filter by stage, this is actually a single_tool with parameter
- **Scoring**: Abstain = correct; routing to any tool = incorrect

### lossy_fit
A tool exists that partially addresses the query, but loses important meaning or requires unavailable parameters.
- **Example**: q062 "list purchase orders with value above 5 lakh" — purchase_po_list exists but can't filter by value
- **Example**: q081 "give me top 5 vendors by purchase order value" — no aggregation tool exists
- **Scoring**: Routing to the partial-fit tool = acceptable; abstain with explanation = correct

### refuse_mutation
Query requests a write/update/delete operation. Must NEVER route to any query tool.
- **Example**: q017 "approve PO097", q052 "delete all draft POs", q024 "how do i change a PO status"
- **Scoring**: Any tool routing = critical failure; abstain = correct

### not_a_data_query
Query asks for explanatory information, procedures, or how-to guidance rather than data retrieval.
- **Example**: q003 "how do i create a purchase order", q056 "give me the report on how leave approval works"
- **Scoring**: Any tool routing = incorrect; abstain = correct

### out_of_scope
Query is completely unrelated to ERP domain.
- **Example**: q032 "what's the weather in jaipur today"
- **Scoring**: Any tool routing = incorrect; abstain = correct

### needs_clarification
Query is too vague to route confidently without additional context.
- **Example**: q010 "how many are there?", q035 "total value", q061 "stock"
- **Scoring**: Abstain = correct; routing = acceptable if context could support it

### multi_intent
Query contains multiple distinct questions or requests.
- **Example**: q039 "how many POs are pending and what does pending mean" — count query + definition request
- **Example**: q073 "which machines were down yesterday and what did it cost us" — status query + cost calculation
- **Scoring**: Route to primary intent tool = acceptable; abstain = correct

## Entity Detection Rules

### Purchase Orders vs Job Work POs
- "job work po" / "jobwork po" / "job work order" → jobwork tools
- Plain "po" / "purchase order" without "job work" → purchase tools
- The longer phrase wins when both could match

### Stock vs Item Master
- "stock" queries (quantity on hand, current inventory) → inventory_stock_* tools
- "item master" queries (registered items, catalogue) → inventory_item_master_* tools
- "how many items" is ambiguous: could be stock count or item master count — use context

### GRN (Goods Receipt Notes)
- "grn" / "goods receipt" → purchase_grn_* tools
- Distinct from purchase orders

### Sales Orders vs Sales Invoices
- "sales order" / "so" → sales_so_* tools
- "invoice" / "billing" → sales_invoice_* or finance_invoice_* tools

### Gate Pass
- "gate pass" / "gatepass" → gatepass_* tools
- Often confused with material issues; gate pass is for outgoing/returning materials

### Material Issues vs Indents
- "material issue" / "issue slip" → store_issue_* tools
- "indent" → store_indent_* tools

### Payments vs Outstanding/Receivables
- "payment" (outgoing to vendors) → finance_payment_* tools
- "outstanding" / "receivable" (incoming from customers) → finance_outstanding_* tools
- "overdue invoice" → finance_invoice_overdue_list

### Action Items vs MoM
- "action item" → mom_action_item_* tools
- "meeting" / "mom" / "minutes" → mom_* tools

## Output Shape Detection

### Count vs List vs Scalar
- "how many", "count", "number of" → count or scalar
- "list", "show", "which", "display" → list
- "total value", "total amount" → scalar
- Shape should constrain, not override entity detection

### List queries routed to count tools
- Common error: q002 "show me the last 10 purchase orders" routed to purchase_po_count
- The "10" and "show me" clearly want a list, not a count
- If baseline does this, it's wrong

### Count queries routed to list tools
- Less common but still wrong
- Output type mismatch should be flagged

## Special Cases

### Typos and Informal Language
- q028 "pendin po cnt" → should abstain or use light fuzzy matching for "pending po count"
- q043 "po ka status kya hai" → non-English, should abstain
- q103 "HOW MANY EMPLOYEES ARE ACTIVE" → case shouldn't matter

### Conversational Context
- q077 "as per our discussion yesterday please send me that list again" → needs_clarification
- Requires session context we don't have

### Comparison and Analytics
- q047 "compare this month's production output with last month" → lossy_fit, production_output_total can't compare
- q065 "why is our rejection rate so high" → not_a_data_query (asks for explanation)
- q073 "what did it cost us" → multi_intent, cost calculation not available

### Vendor/Customer/Employee Specific
- Queries with specific names (q007 "Sharma Industries", q125 "Kiran Auto") map to tools with name parameters
- Baseline should handle these if the tool has the parameter

### Time-based Queries
- "today", "yesterday", "last week", "this month" → many tools have period/date parameters
- Baseline may not extract parameters but routing should be correct

## Confidence Scoring

- **high** (0.9-1.0): Unambiguous single tool, clear entity and shape match
- **medium** (0.6-0.89): Correct tool but some ambiguity, or lossy fit
- **low** (0.3-0.59): Multiple reasonable interpretations, needs_clarification cases
- **abstain** (0.0): Should not route — mutation, out of scope, not a data query

## Changes During Labeling

None yet — this is the first pass. Will document any rule changes or re-labeling decisions here.
