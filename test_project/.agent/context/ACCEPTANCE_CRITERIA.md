# ACCEPTANCE_CRITERIA.md - generic_task

## AC-01 - Scope

All changed files must be allowed by `.agent/context/TASK_SCOPE.json`.

## AC-02 - Build/Test

Project `verify` command must pass according to `.agent/project_profile.json`.

## AC-03 - Feature Behavior

The implemented behavior must satisfy:

Generic feature for any project

## AC-04 - Codex Review

Codex review must return `PASS` for the exact run id, snapshot hash, and reviewed file list.

## AC-05 - Release Gate

Release gate must return `ALLOW_RELEASE`.
