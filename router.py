"""
router.py — route ERP queries to tools using layered keyword scoring.

Interface: route(query) -> (tool_name_or_None, confidence, reason)
"""

import json
import re
from difflib import get_close_matches
from pathlib import Path

HERE = Path(__file__).parent

# Load tools at import time
with open(HERE / 'tools.json') as f:
    TOOLS = json.load(f)

# Build vocabulary of all tokens in keywords
VOCAB = set()
for tool in TOOLS.values():
    for kw in tool.get('keywords', []):
        VOCAB.update(kw.lower().split())


def route(query):
    """Route a query to a tool.
    
    Returns (tool_name_or_None, confidence, reason).
    reason starts with abstain type or "match: ..."
    """
    query_lower = query.lower().strip()
    
    # Layer 1: Intent gate - check for abstain conditions
    abstain_result = check_abstains(query_lower)
    if abstain_result:
        return abstain_result
    
    # Tokenize and normalize query
    tokens = tokenize_query(query_lower)
    
    # Layer 6: Typo tolerance - fix tokens not in vocabulary
    tokens = apply_typo_tolerance(tokens)
    
    # Check for vague/ambiguous queries
    if is_vague(tokens, query_lower):
        return (None, 0.0, 'needs_clarification: query too vague or ambiguous')
    
    # Layer 2: Entity scoring with phrase weighting
    entity_scores = score_entities(tokens, query_lower)
    
    if not entity_scores:
        return (None, 0.0, 'no_tool: no matching entity found')
    
    # Get top entity
    top_entity = max(entity_scores, key=entity_scores.get)
    entity_tools = [t for t in TOOLS.values() if t.get('entity') == top_entity]
    
    # Layer 3: Shape detection as tie-breaker
    desired_shape = detect_shape(tokens, query_lower)
    
    # Layer 4: Special tools detection
    special_match = check_special_tools(tokens, query_lower, entity_tools)
    if special_match:
        tool_id, score = special_match
        confidence = compute_confidence([score])
        return (tool_id, confidence, f'match: special tool {tool_id}')
    
    # Score tools within winning entity
    tool_scores = {}
    for tool in entity_tools:
        score = score_tool(tool, tokens, query_lower, desired_shape)
        tool_scores[tool['id']] = score
    
    if not tool_scores:
        return (None, 0.0, 'no_tool: no matching tool in entity')
    
    # Get top 2 for margin calculation
    sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
    top_tool, top_score = sorted_tools[0]
    
    if top_score == 0:
        return (None, 0.0, 'no_tool: no keyword matches')
    
    # Layer 5: Confidence from margin
    if len(sorted_tools) > 1:
        second_score = sorted_tools[1][1]
        margin = top_score - second_score
        confidence = min(0.95, 0.5 + (margin / max(top_score, 1)) * 0.5)
    else:
        confidence = 0.9
    
    # Boost confidence if clear match
    if top_score > 5:
        confidence = min(0.95, confidence + 0.1)
    
    return (top_tool, confidence, f'match: {top_tool} (entity={top_entity}, shape={desired_shape})')


def check_abstains(query):
    """Layer 1: Check for abstain conditions."""
    # Refuse mutation: write/destructive verbs
    write_verbs = ['delete', 'remove', 'approve', 'reject', 'update', 'create', 'add', 
                   'modify', 'change', 'edit', 'set', 'cancel']
    for verb in write_verbs:
        if re.search(r'\b' + verb + r'\b', query):
            return (None, 0.0, 'refuse_mutation: write operation detected')
    
    # Not a data query: how-to, why, procedural
    if re.search(r'\bhow (do|to|can|should)\b', query):
        return (None, 0.0, 'not_a_data_query: procedural question')
    if re.search(r'\bwhy\b', query):
        return (None, 0.0, 'not_a_data_query: explanatory question')
    if re.search(r'\bwhat (is|are|does|do)\b.*\b(mean|work|process|procedure)\b', query):
        return (None, 0.0, 'not_a_data_query: definition question')
    
    # Out of scope: non-ERP domains
    erp_unrelated = ['weather', 'temperature', 'news', 'sports', 'movie', 'restaurant']
    for word in erp_unrelated:
        if word in query:
            return (None, 0.0, 'out_of_scope: non-ERP domain')
    
    # No tool: analytics that require aggregation/comparison not available
    if re.search(r'\bcompare\b', query):
        return (None, 0.0, 'no_tool: comparison not available')
    if re.search(r'\btop\s+\d+\b', query):
        return (None, 0.0, 'no_tool: ranking not available')
    if re.search(r'\btop\b.*\bby\b', query):
        return (None, 0.0, 'no_tool: ranking not available')
    
    return None


def tokenize_query(query):
    """Tokenize query into words."""
    # Remove punctuation and split
    tokens = re.findall(r'\b\w+\b', query.lower())
    return tokens


def apply_typo_tolerance(tokens):
    """Layer 6: Fix typos on tokens not in vocabulary."""
    corrected = []
    for token in tokens:
        if token in VOCAB:
            corrected.append(token)
        else:
            # Try to find close match in vocabulary
            matches = get_close_matches(token, VOCAB, n=1, cutoff=0.8)
            if matches:
                corrected.append(matches[0])
            else:
                corrected.append(token)
    return corrected


def is_vague(tokens, query):
    """Check if query is too vague."""
    # Single word queries (except specific ones)
    if len(tokens) == 1 and tokens[0] not in ['stock', 'inventory', 'employees', 'customers']:
        return True
    
    # Very short queries with no entity
    if len(tokens) <= 2 and not any(token in query for token in ['po', 'so', 'grn', 'ncr', 'mom']):
        # Check if it's just shape words
        shape_words = ['how', 'many', 'show', 'list', 'total', 'count', 'what']
        if all(token in shape_words for token in tokens):
            return True
    
    return False


def score_entities(tokens, query):
    """Layer 2: Score entities with phrase weighting."""
    entity_scores = {}
    
    # Multi-word phrases get higher weight
    phrases_by_length = {
        3: ['job work po', 'job work order', 'job work purchase', 'gate pass', 
            'sales order', 'purchase order', 'work order', 'minutes of meeting',
            'action item', 'item master', 'low stock'],
        2: ['job work', 'sales', 'purchase', 'gate', 'quality', 'production', 
            'finance', 'crm', 'store', 'stock']
    }
    
    # Check 3-word phrases first
    for phrase in phrases_by_length.get(3, []):
        if phrase in query:
            # Map phrase to entity
            entity = phrase_to_entity(phrase)
            if entity:
                entity_scores[entity] = entity_scores.get(entity, 0) + 10
    
    # Check 2-word phrases
    for phrase in phrases_by_length.get(2, []):
        if phrase in query:
            entity = phrase_to_entity(phrase)
            if entity:
                entity_scores[entity] = entity_scores.get(entity, 0) + 5
    
    # Single-word entity detection
    for tool in TOOLS.values():
        entity = tool.get('entity', '')
        for kw in tool.get('keywords', []):
            kw_lower = kw.lower()
            # Check if keyword appears in query
            if kw_lower in query:
                # Weight by keyword length (longer = more specific)
                weight = len(kw_lower.split())
                entity_scores[entity] = entity_scores.get(entity, 0) + weight
    
    return entity_scores


def phrase_to_entity(phrase):
    """Map multi-word phrase to entity."""
    mapping = {
        'job work po': 'Job Work Purchase Orders',
        'job work order': 'Job Work Purchase Orders',
        'job work purchase': 'Job Work Purchase Orders',
        'job work': 'Job Work Purchase Orders',
        'gate pass': 'Gate Passes',
        'sales order': 'Sales Orders',
        'purchase order': 'Purchase Orders',
        'work order': 'Work Orders',
        'minutes of meeting': 'Minutes of Meeting',
        'action item': 'Action Items',
        'item master': 'Item Master',
        'low stock': 'Stock Items',
        'sales': 'Sales Orders',
        'purchase': 'Purchase Orders',
        'quality': 'Non Conformance Reports',
        'production': 'Work Orders',
        'finance': 'Payments',
        'crm': 'Leads',
        'store': 'Material Issues',
        'stock': 'Stock Items'
    }
    return mapping.get(phrase)


def detect_shape(tokens, query):
    """Layer 3: Detect desired output shape."""
    # Handle Hinglish
    if any(word in query for word in ['kitne', 'kitna']):
        return 'count'
    if any(word in query for word in ['dikhao', 'dikha']):
        return 'list'
    
    # Count indicators
    count_words = ['how many', 'count', 'number of', 'total number', 'how much']
    for phrase in count_words:
        if phrase in query:
            return 'count'
    
    # List indicators
    list_words = ['list', 'show', 'which', 'display']
    if any(word in tokens for word in list_words):
        # Check it's not "how many" or "count"
        if 'count' not in query and 'how many' not in query and 'number' not in query:
            return 'list'
    
    # Scalar indicators (specific value)
    scalar_words = ['total value', 'total', 'what is', 'value of', 'stock of']
    for phrase in scalar_words:
        if phrase in query:
            # But not if it asks for "how many"
            if 'how many' not in query and 'count' not in query:
                return 'scalar'
    
    return None


def check_special_tools(tokens, query, entity_tools):
    """Layer 4: Check for special tools."""
    special_keywords = {
        'expiring': ['expiring', 'expire', 'expiry', 'validity'],
        'low_stock': ['low stock', 'below reorder', 'reorder level', 'shortage'],
        'shift': ['shift wise', 'by shift', 'per shift', 'shift output'],
        'pending_return': ['pending return', 'not returned', 'awaited'],
        'pending_approval': ['pending approval', 'awaiting approval', 'stuck in approval'],
        'overdue': ['overdue', 'past due', 'late']
    }
    
    for special, keywords in special_keywords.items():
        for kw in keywords:
            if kw in query:
                # Find tool with this keyword in entity_tools
                for tool in entity_tools:
                    tool_keywords = ' '.join(tool.get('keywords', [])).lower()
                    if kw in tool_keywords:
                        return (tool['id'], 10)
    
    return None


def score_tool(tool, tokens, query, desired_shape):
    """Score a tool based on keyword matches and shape."""
    score = 0
    
    # Keyword matching
    for kw in tool.get('keywords', []):
        kw_lower = kw.lower()
        if kw_lower in query:
            # Weight by keyword length
            score += len(kw_lower.split()) * 2
    
    # Shape bonus as tie-breaker
    tool_shape = tool.get('output_type', '')
    if desired_shape and tool_shape == desired_shape:
        score += 1  # Small bonus, not a flat boost
    
    return score


def compute_confidence(scores):
    """Compute confidence from scores."""
    if not scores:
        return 0.0
    return min(0.9, max(scores) / 10)
