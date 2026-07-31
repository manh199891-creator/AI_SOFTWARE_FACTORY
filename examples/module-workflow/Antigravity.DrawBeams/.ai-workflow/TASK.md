# Task

## Identity

- Task ID: drawbeams-fix-corridor
- Module: antigravity-drawbeams
- Requested by: user

## Goal

Fix the corridor intersection bug in DrawBeams module.

## Current problem

The command does not validate the selected beam input before execution.

## Repository evidence

src/Antigravity.DrawBeams/CreateBeamCommand.cs line 20-35 uses input without validation.

## Requirements

Add input validation.

## Acceptance criteria

Validation throws InvalidOperationException if input is null.

## Test commands

dotnet test tests/Antigravity.DrawBeams.Tests/Antigravity.DrawBeams.Tests.csproj

## Commit message

fix(drawbeams): add input validation to CreateBeamCommand

## Restrictions

Do not modify other modules.
