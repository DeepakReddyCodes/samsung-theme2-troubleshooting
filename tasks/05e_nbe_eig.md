# W05E — Next-Best-Evidence / EIG

## Objective

Implement the project's Next-Best-Evidence decision layer.

NBE/EIG is a project innovation, not a Samsung requirement.

## Principle

Determine whether available evidence is sufficient before committing to a troubleshooting resolution.

If sufficient:
    proceed to resolution.

If insufficient:
    identify the most informative missing evidence.

## Required concepts

- hypothesis representation
- candidate evidence
- uncertainty
- Expected Information Gain
- evidence acquisition cost
- evidence availability
- evidence selection
- targeted question generation
- evidence reintegration
- reassessment

## Important

Do not use an LLM as the sole decision-maker for NBE.

The decision layer should be deterministic/probabilistic where practical.

The LLM may phrase the selected question.

## Do not claim completion

NBE must not be described as implemented until:
- implementation exists;
- tests exist;
- an end-to-end evidence acquisition loop works;
- evaluation is performed.
