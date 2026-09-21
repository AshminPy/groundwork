# RESEARCH playbook

## Goal
Answer a question about current state, technology, or fact with evidence the user can check, and say what remains unknown.

## Workflow
1. State the exact question and what would count as an answer.
2. Check the strongest sources first in `evidence-policy.md` §1 order: the repository or configuration in front of you, runtime output, official vendor documentation for the version in use, standards, upstream source, release notes, then established practice. Community sources last and labelled.
3. Read what you cite. A page you did not read is not evidence.
4. Separate VERIFIED findings from INFERENCE and ASSUMPTION; date-sensitive facts carry the date or version they apply to.
5. Stop when the question is answered or when further searching cannot change the answer.

## Evidence
- At least one authoritative source per material claim, with the real URL or file path.
- "No authoritative source found" is a valid, required statement when true.

## Ask Before Acting When
- The question's scope is genuinely ambiguous and the two readings lead to different answers (which product, which version, which environment).
- Otherwise pick the reading the context supports, state it in one line, and answer.

## Completion Criteria
- The answer is stated directly, each material claim has a source, and unknowns are named rather than glossed.

## Output Format
```
Answer: <direct answer first>
Evidence:
- <only the important sources, with URL/path and version/date where it matters>
Unknowns:
- <only material uncertainty; omit the section if none>
Recommendation: <only when appropriate or requested>
```
