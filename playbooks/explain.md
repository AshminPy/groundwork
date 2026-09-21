# EXPLAIN playbook

## Goal
Make the user understand something well enough to act on it or reason about it themselves, at the depth they asked for.

## Workflow
1. Identify what the user already knows from the request and match the depth: "high level" → the model and why it matters; "low level" → mechanics, edge cases, exact behaviour. Depth is a modifier, not a different task.
2. Lead with the mental model in one or two sentences, then the mechanism, then a concrete example drawn from the user's own context when available (their repo, stack, or environment).
3. Prefer the official documentation's terms and, for version-dependent behaviour, name the version.
4. If the explanation depends on something not verified (an assumption about their setup), say so in one line.
5. Keep it as short as understanding allows; simple English, one idea per sentence.

## Evidence
- Official documentation or the user's own code/config for any claim about how a specific tool behaves; label the rest as general practice.

## Ask Before Acting When
- The subject is genuinely ambiguous between two different things (same name, different technologies) and context does not resolve it. Otherwise answer for the most likely reading and say so.

## Completion Criteria
- The user can restate the idea and knows the next thing to try or read.

## Output Format
```
Answer: <the model / the mechanism, at the requested depth>
Why it matters: <one or two lines: the consequence for their situation>
Example: <concrete, ideally from their context>
Next: <one thing to try, check, or read next>
```
