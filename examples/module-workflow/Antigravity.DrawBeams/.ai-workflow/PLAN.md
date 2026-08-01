# Implementation Plan

## Identity

- Task ID: drawbeams-fix-corridor
- Module: antigravity-drawbeams
- Base commit: 1111111111111111111111111111111111111111
- Work branch: task/drawbeams-fix-corridor

## Goal

Add input validation to CreateBeamCommand before element consumption to prevent null reference exceptions in corridor layout calculation.

## Verified context

Inspected src/Antigravity.DrawBeams/CreateBeamCommand.cs lines 20-35. Verified selection logic consumes element prior to null guard.

## Proposed changes

- Add explicit null and category validation check in CreateBeamCommand.cs before corridor selection processing.
- Throw InvalidOperationException if selection is unsupported.

## Files expected to change

- src/Antigravity.DrawBeams/CreateBeamCommand.cs

## Files explicitly excluded

- src/Antigravity.DrawBeams/Antigravity.DrawBeams.csproj
- .github/**

## Test plan

- Run unit tests: `dotnet test tests/Antigravity.DrawBeams.Tests/Antigravity.DrawBeams.Tests.csproj`

## Acceptance criteria

- Validation throws InvalidOperationException when input is null or unsupported.

## Risks and rollback

- Low risk. Rollback by reverting CreateBeamCommand.cs edit.

## Open questions

- None.
