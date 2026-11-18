## ADDED Requirements

### Requirement: Cited repository evidence exists
The reply check SHALL resolve repository paths cited in a reply's evidence sections, and SHALL report each cited file that does not exist and each cited line range outside the file.

#### Scenario: Missing file
- **WHEN** a reply cites `hooks/missing.py:10`
- **THEN** the check asks once for a correction, naming that citation

#### Scenario: Valid citation
- **WHEN** a reply cites an existing file and an in-range line
- **THEN** the check raises nothing for that citation
