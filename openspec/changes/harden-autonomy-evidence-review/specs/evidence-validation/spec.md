## ADDED Requirements

### Requirement: Cited repository evidence exists
The reply check SHALL resolve repository paths cited anywhere in a tool-using turn's final reply outside code fences, and SHALL ask once for a correction of each cited file that does not exist in the working tree or HEAD and each cited line range outside the file. Absolute, home, URL and other-checkout paths are not checked.

#### Scenario: Missing file
- **WHEN** a reply cites `hooks/missing.py:10`
- **THEN** the check asks once for a correction, naming that citation

#### Scenario: Valid citation
- **WHEN** a reply cites an existing file and an in-range line
- **THEN** the check raises nothing for that citation
