Please review the current `snappy_putty` codebase and give me a candid engineering assessment.

Focus on:

1. Architectural strengths
2. Architectural weaknesses
3. Code smells
4. Lifecycle/state-management risks
5. Areas of duplication or unnecessary complexity
6. Testing gaps
7. Where the codebase is strong enough for future milestones
8. What could become a problem for:
   - M4 Workflow Memory + Continuation
   - M5 Active Mode
   - M6 Workflow Skills

Important constraints:
- Be direct and critical where needed
- Do not give vague praise
- Distinguish between:
  - immediate risks
  - medium-term technical debt
  - acceptable tradeoffs
- Call out anything that feels brittle, over-coupled, under-tested, or architecturally inconsistent
- If something is fine, say so plainly
- If something is weak, explain why

Output format:

## Strengths
- ...

## Weaknesses
- ...

## Improvement Areas
- ...

## Risks for Next Milestones
- ...

## Recommended Actions Before M4
- Must do now
- Should do soon
- Can defer

Do not redesign the whole system. Assess the codebase as it exists now.

Save the results to SWOT_ANALYSIS_OUTPUT.md

