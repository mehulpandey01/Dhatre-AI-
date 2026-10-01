"""
evaluate.py — compare baseline and router against labels.

Usage:
    python evaluate.py              # show metrics for both systems
    python evaluate.py --errors baseline    # list all wrong predictions for baseline
    python evaluate.py --errors router      # list all wrong predictions for router

Note: Baseline has no confidence or abstain mechanism. A returned tool counts
as confident (1.0), nothing returned counts as an abstain.

Note: expected_params is not scored.
"""

import csv
import sys
import time
from pathlib import Path
from collections import defaultdict, Counter

# Import baseline router
import baseline

HERE = Path(__file__).parent


def load_labels():
    """Load labels.csv and filter to dev split."""
    labels = []
    with open(HERE / 'labels.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['split'] == 'dev':
                labels.append(row)
    return labels


def evaluate_system(name, route_fn, labels):
    """Evaluate a routing system against labels.
    
    route_fn should return (tool_id_or_None, confidence, reason).
    For baseline, we adapt its (tool_id, score) output.
    """
    results = {
        'correct': [],
        'acceptable': [],
        'wrong': [],
        'critical': [],
        'false_abstain': [],
        'missed_abstain': [],
        'wrong_confident': [],
        'by_label_type': defaultdict(lambda: {'correct': 0, 'acceptable': 0, 'wrong': 0}),
        'latencies': [],
        'all_predictions': []  # Track all predictions for threshold analysis
    }
    
    for row in labels:
        qid = row['query_id']
        query = row['query']
        label_type = row['label_type']
        expected = row['expected_tool']
        alt_tools = [t.strip() for t in row['acceptable_alt_tools'].split(',') if t.strip()]
        closest = row['closest_tool']
        should_abstain = row['should_abstain'] == 'yes'
        
        # Route the query
        start = time.time()
        try:
            result = route_fn(query)
            if len(result) == 2:
                # Baseline format: (tool_id, score)
                tool_id, score = result
                # Baseline: tool returned = confident (1.0), None = abstain (0.0)
                confidence = 1.0 if tool_id else 0.0
                reason = '' if tool_id else 'no match'
            else:
                # Router format: (tool_id, confidence, reason)
                tool_id, confidence, reason = result
        except Exception as e:
            tool_id, confidence, reason = None, 0.0, f'error: {e}'
        
        latency = (time.time() - start) * 1000  # ms
        results['latencies'].append(latency)
        
        # Scoring logic
        is_correct = False
        is_acceptable = False
        is_critical = False
        
        # Check critical failures first (refuse_mutation routed to any tool)
        if label_type == 'refuse_mutation' and tool_id is not None:
            results['critical'].append((qid, query, expected, tool_id, confidence, reason))
            is_critical = True
        
        # Check abstain types
        abstain_types = ['refuse_mutation', 'not_a_data_query', 'out_of_scope', 
                        'needs_clarification', 'no_tool']
        
        if label_type in abstain_types:
            if tool_id is None:
                # Correct abstain
                is_correct = True
                results['correct'].append((qid, label_type))
            else:
                # Missed abstain
                results['missed_abstain'].append((qid, query, label_type, tool_id, confidence, reason))
                is_correct = False
        
        elif label_type == 'single_tool':
            if tool_id == expected:
                is_correct = True
                results['correct'].append((qid, label_type))
            elif tool_id in alt_tools:
                is_acceptable = True
                results['acceptable'].append((qid, label_type))
            elif tool_id is None:
                # False abstain
                results['false_abstain'].append((qid, query, expected, confidence, reason))
                is_correct = False
            else:
                results['wrong'].append((qid, query, expected, tool_id, confidence, reason))
                is_correct = False
        
        elif label_type == 'ambiguous':
            if tool_id == expected or tool_id in alt_tools:
                is_correct = True
                results['correct'].append((qid, label_type))
            elif tool_id is None:
                is_acceptable = True
                results['acceptable'].append((qid, label_type))
            else:
                results['wrong'].append((qid, query, expected, tool_id, confidence, reason))
                is_correct = False
        
        elif label_type == 'lossy_fit':
            if tool_id == closest:
                is_correct = True
                results['correct'].append((qid, label_type))
            elif tool_id is None:
                is_acceptable = True
                results['acceptable'].append((qid, label_type))
            else:
                results['wrong'].append((qid, query, closest, tool_id, confidence, reason))
                is_correct = False
        
        elif label_type == 'multi_intent':
            if tool_id == expected:
                is_correct = True
                results['correct'].append((qid, label_type))
            elif tool_id is None:
                is_acceptable = True
                results['acceptable'].append((qid, label_type))
            else:
                results['wrong'].append((qid, query, expected, tool_id, confidence, reason))
                is_correct = False
        
        # Track by label_type
        if is_correct:
            results['by_label_type'][label_type]['correct'] += 1
        elif is_acceptable:
            results['by_label_type'][label_type]['acceptable'] += 1
        else:
            results['by_label_type'][label_type]['wrong'] += 1
        
        # Wrong but confident (>=0.6) - single_tool and lossy_fit only, no missed abstains
        if label_type in ['single_tool', 'lossy_fit'] and not is_correct and not is_acceptable and confidence >= 0.6:
            results['wrong_confident'].append((qid, query, expected or closest, tool_id, confidence, reason))
        
        # Track for threshold analysis
        results['all_predictions'].append({
            'qid': qid,
            'label_type': label_type,
            'confidence': confidence,
            'is_correct': is_correct,
            'is_acceptable': is_acceptable,
            'tool_id': tool_id
        })
    
    return results


def print_metrics(name, results, total):
    """Print metrics for a system."""
    print(f"\n{'='*60}")
    print(f"{name} EVALUATION (dev split, {total} queries)")
    print('='*60)
    
    # Wrong but confident
    print(f"\nWRONG BUT CONFIDENT (confidence >= 0.6): {len(results['wrong_confident'])}")
    if results['wrong_confident']:
        for qid, query, expected, got, conf, reason in results['wrong_confident'][:10]:
            print(f"  {qid}: expected={expected}, got={got}, conf={conf:.2f}")
            print(f"    Query: {query[:70]}")
    
    # Critical failures
    print(f"\nCRITICAL FAILURES (write request routed to tool): {len(results['critical'])}")
    if results['critical']:
        for qid, query, expected, got, conf, reason in results['critical']:
            print(f"  {qid}: routed refuse_mutation to {got}")
            print(f"    Query: {query[:70]}")
    
    # False abstains
    print(f"\nFALSE ABSTAINS (should route but didn't): {len(results['false_abstain'])}")
    if results['false_abstain']:
        for qid, query, expected, conf, reason in results['false_abstain'][:10]:
            print(f"  {qid}: expected={expected}, got=None")
            print(f"    Query: {query[:70]}")
    
    # Missed abstains
    print(f"\nMISSED ABSTAINS (should abstain but routed): {len(results['missed_abstain'])}")
    if results['missed_abstain']:
        for qid, query, expected_label, got, conf, reason in results['missed_abstain'][:10]:
            print(f"  {qid}: expected={expected_label}, got={got}")
            print(f"    Query: {query[:70]}")
    
    # Per label_type
    print(f"\nPER LABEL_TYPE:")
    for label_type in sorted(results['by_label_type'].keys()):
        stats = results['by_label_type'][label_type]
        total_type = stats['correct'] + stats['acceptable'] + stats['wrong']
        print(f"  {label_type:20s} correct={stats['correct']:3d} acceptable={stats['acceptable']:3d} wrong={stats['wrong']:3d} (total={total_type})")
    
    # Lossy_fit and no_tool separate
    print(f"\nLOSSY_FIT AND NO_TOOL (never merged into accuracy):")
    for label_type in ['lossy_fit', 'no_tool']:
        if label_type in results['by_label_type']:
            stats = results['by_label_type'][label_type]
            total_type = stats['correct'] + stats['acceptable'] + stats['wrong']
            print(f"  {label_type:20s} correct={stats['correct']:3d} acceptable={stats['acceptable']:3d} wrong={stats['wrong']:3d}")
    
    # Coverage vs accuracy at thresholds
    print(f"\nCOVERAGE VS ACCURACY AT THRESHOLDS:")
    for threshold in [0.5, 0.6, 0.7, 0.8]:
        # Coverage: queries with confidence >= threshold and tool_id != None
        # Accuracy: of those, how many correct or acceptable
        routed = [p for p in results['all_predictions'] if p['confidence'] >= threshold and p['tool_id'] is not None]
        coverage = len(routed)
        if coverage > 0:
            correct_count = sum(1 for p in routed if p['is_correct'] or p['is_acceptable'])
            accuracy = correct_count / coverage
        else:
            accuracy = 0.0
        
        print(f"  threshold={threshold:.1f}: coverage={coverage:3d}, accuracy={accuracy:.3f} ({correct_count}/{coverage})")
    
    # Latency
    latencies = sorted(results['latencies'])
    median = latencies[len(latencies)//2] if latencies else 0
    p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
    print(f"\nLATENCY: median={median:.1f}ms, p95={p95:.1f}ms")


def print_errors(name, route_fn, labels):
    """Print all wrong predictions for a system."""
    print(f"\n{'='*60}")
    print(f"{name} ERRORS")
    print('='*60)
    
    for row in labels:
        qid = row['query_id']
        query = row['query']
        label_type = row['label_type']
        expected = row['expected_tool']
        alt_tools = [t.strip() for t in row['acceptable_alt_tools'].split(',') if t.strip()]
        closest = row['closest_tool']
        should_abstain = row['should_abstain'] == 'yes'
        
        result = route_fn(query)
        if len(result) == 2:
            tool_id, score = result
            confidence = 1.0 if tool_id else 0.0
            reason = '' if tool_id else 'no match'
        else:
            tool_id, confidence, reason = result
        
        # Determine if wrong
        is_wrong = False
        
        if label_type in ['refuse_mutation', 'not_a_data_query', 'out_of_scope', 'needs_clarification', 'no_tool']:
            if tool_id is not None:
                is_wrong = True
        elif label_type == 'single_tool':
            if tool_id != expected and tool_id not in alt_tools:
                is_wrong = True
        elif label_type == 'ambiguous':
            if tool_id != expected and tool_id not in alt_tools and tool_id is not None:
                is_wrong = True
        elif label_type == 'lossy_fit':
            if tool_id != closest and tool_id is not None:
                is_wrong = True
        elif label_type == 'multi_intent':
            if tool_id != expected and tool_id is not None:
                is_wrong = True
        
        if is_wrong:
            expected_or_closest = expected or closest or 'abstain'
            print(f"\n{qid}: {query}")
            print(f"  Expected: {expected_or_closest} ({label_type})")
            print(f"  Got: {tool_id or 'abstain'} (confidence={confidence:.2f})")
            print(f"  Reason: {reason}")


def main():
    labels = load_labels()
    total = len(labels)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--errors':
        system = sys.argv[2] if len(sys.argv) > 2 else 'baseline'
        if system == 'baseline':
            print_errors('BASELINE', baseline.route, labels)
        else:
            print(f"Error: router.py not implemented yet")
            sys.exit(1)
        return
    
    # Evaluate baseline
    print("\nEvaluating baseline...")
    baseline_results = evaluate_system('BASELINE', baseline.route, labels)
    print_metrics('BASELINE', baseline_results, total)
    
    # TODO: Evaluate router when router.py exists
    print(f"\n\nRouter evaluation not yet implemented (router.py doesn't exist)")


if __name__ == '__main__':
    main()
