---
title: Knapsack Constraint Solving for Playlist Duration Optimization
type: reference
created: 2026-11-09
tags:
  - algorithms
  - knapsack
  - constraints
  - optimization
requirements:
  - FR-5
  - NFR-PERF-3
---

# Knapsack Constraint Solving for Playlist Duration Optimization

## Summary
Building a playlist under strict time constraints (such as a two hour total duration with no video exceeding twenty minutes) is mapped to a bounded 0/1 knapsack optimization problem with cardinality constraints.

## Mathematical Formulation
- **Candidate Pool**: Set of candidate videos $i = 1, \dots, n$, each with duration $d_i$ and similarity relevance weight $w_i$.
- **Hard Constraints**:
  - Target duration: $T_{\min} \le \sum_{i} x_i d_i \le T_{\max}$
  - Single video limit: $d_{\min} \le d_i \le d_{\max}$
  - Maximum count: $\sum_{i} x_i \le K$
  - Binary decision: $x_i \in \{0, 1\}$
- **Objective Function**:
  $$\text{Maximize } \sum_{i=1}^n x_i w_i - \text{penalty}(\text{channel count})$$

## Solving Strategies
1. **Dynamic Programming**:
   - Durations are discretized into 10 second buckets.
   - Exact dynamic programming runs efficiently for typical candidate pools of under 200 videos and target durations up to 10 hours.
2. **Heuristic Fallback**:
   - If the dynamic programming state matrix exceeds memory thresholds, the solver automatically switches to a greedy ratio sorting approach followed by one swap local search optimization.

## Edge Cases
- When candidate videos cannot satisfy the duration bounds, the solver reports `CONSTRAINTS_UNSATISFIABLE` along with suggested relaxation parameters (such as increasing allowable maximum video duration).

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/tfidf-cosine-similarity|TF IDF and Cosine Similarity]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]

