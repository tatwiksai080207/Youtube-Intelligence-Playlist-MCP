---
title: TF IDF and Cosine Similarity Metadata Scoring
type: reference
status: distilled
authors:
  - Molleti Tatwik Sai
created: 2026-11-09
updated: 2026-11-23
tags:
  - tfidf
  - algorithms
  - similarity
  - ranking
requirements:
  - FR-1
  - FR-1.2
  - FR-2
  - FR-2.2
  - NFR-1
issues:
  - "#1"
  - "#3"
prs:
  - "#10"
  - "#13"
sources:
  - "Final_SRS_Submission.pdf Section 4.1 and 4.2 (checked 2026-11-12)"
---

# TF IDF and Cosine Similarity Metadata Scoring

## Summary
To replace engagement based algorithms with transparent content matching, similarity between videos is computed locally using Term Frequency Inverse Document Frequency (TF IDF) vectorization and cosine similarity over sanitized text metadata.

## Mathematical Formulation
1. **Term Frequency (Sublinear)**:
   For term $t$ in document $d$:
   $$tf(t, d) = 1 + \ln(\text{count}(t, d)) \quad \text{if count} > 0, \text{ else } 0$$
2. **Inverse Document Frequency (Smoothed)**:
   For corpus size $N$ and document frequency $df(t)$:
   $$idf(t) = \ln\left(\frac{1 + N}{1 + df(t)}\right) + 1$$
3. **Cosine Similarity**:
   Given L2 normalized feature vectors $u$ and $v$:
   $$\text{cosine\_similarity}(u, v) = u \cdot v$$

## Multi Feature Weighted Score
The overall similarity score $S$ combines multiple dimensions:
- Title similarity (weight 0.30)
- Tags similarity (weight 0.25)
- Description similarity (weight 0.20)
- Category matching (weight 0.10)
- Topic categorization (weight 0.10)
- Duration ratio proximity (weight 0.05)

Missing seed metadata triggers dynamic redistribution of weights across available fields.

## Diversity and Clickbait Policy
- **Clickbait Reduction**: Early exploratory research evaluated heuristic penalties for sensationalized wording. This heuristic is not adopted in implementation, as SRS FR-1.2 strictly mandates similarity based on objective metadata only without editorial penalty heuristics.
- **Maximal Marginal Relevance (MMR)**: Re ranks candidates to balance topical relevance with creator diversity, enforcing a cap on videos from any single channel.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/resources/knapsack-constraint-solving|Knapsack Constraint Solving]]
- [[brain/resources/youtube-api-data-limits|YouTube API Data Limits]]
- [[brain/areas/second-brain|Second Brain Architecture]]
