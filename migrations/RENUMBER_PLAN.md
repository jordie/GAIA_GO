# Migration Renumbering Plan

## Problem
Multiple migration files share the same version numbers, causing conflicts in the migration manager.

## Current Duplicates

| Version | Files |
|---------|-------|
| 005 | documentation_table.sql, session_entity_tracking.sql |
| 008 | multi_region.py, test_runs_categories.sql |
| 012 | task_assignment_alerts.sql, task_timeouts.sql |
| 013 | api_keys.sql, llm_metrics.sql, task_archive.sql |
| 014 | integrations.sql, worker_skills.sql |
| 018 | custom_reports.sql, task_attachments.sql |
| 019 | app_settings.sql, project_templates_custom_reports.sql, status_history.sql |
| 020 | project_dependencies.sql, task_due_dates.sql |
| 025 | task_conversions.sql, task_hierarchy.sql |
| 026 | dashboard_layouts.sql, sprints.sql |
| 030 | claude_auto_approval.sql, llm_failover.sql |
| 031 | secure_vault.sql, system_health.sql |

## Renumbering Strategy

Keep the first file at each version number, renumber the rest sequentially starting from 034.

### Files to Rename

| Old Name | New Name |
|----------|----------|
| 005_session_entity_tracking.sql | 034_session_entity_tracking.sql |
| 008_test_runs_categories.sql | 035_test_runs_categories.sql |
| 012_task_timeouts.sql | 036_task_timeouts.sql |
| 013_llm_metrics.sql | 037_llm_metrics.sql |
| 013_task_archive.sql | 038_task_archive.sql |
| 014_worker_skills.sql | 039_worker_skills.sql |
| 018_task_attachments.sql | 040_task_attachments.sql |
| 019_project_templates_custom_reports.sql | 041_project_templates_custom_reports.sql |
| 019_status_history.sql | 042_status_history.sql |
| 020_task_due_dates.sql | 043_task_due_dates.sql |
| 025_task_hierarchy.sql | 044_task_hierarchy.sql |
| 026_sprints.sql | 045_sprints.sql |
| 030_llm_failover.sql | 046_llm_failover.sql |
| 031_system_health.sql | 047_system_health.sql |

### Files to Keep

| Version | File |
|---------|------|
| 001 | baseline.py |
| 002 | add_testing.py |
| 003 | autopilot_orchestration.sql |
| 004 | fix_milestones_schema.sql |
| 005 | documentation_table.sql |
| 006 | claude_interactions.sql |
| 007 | bugs_extended_fields.sql |
| 008 | multi_region.py |
| 009 | notifications.sql |
| 010 | user_preferences.sql |
| 011 | scheduled_tasks.sql |
| 012 | task_assignment_alerts.sql |
| 013 | api_keys.sql |
| 014 | integrations.sql |
| 015 | task_watchers.sql |
| 016 | tmux_project_groups.sql |
| 017 | task_webhooks.sql |
| 018 | custom_reports.sql |
| 019 | app_settings.sql |
| 020 | project_dependencies.sql |
| 021 | task_batches.sql |
| 022 | task_worklog.sql |
| 023 | project_costs.sql |
| 024 | notification_rules.sql |
| 025 | task_conversions.sql |
| 026 | dashboard_layouts.sql |
| 027 | task_effort_rollup.sql |
| 028 | sprints.sql |
| 029 | kudos.sql |
| 030 | claude_auto_approval.sql |
| 031 | secure_vault.sql |
| 032 | llm_provider_tests.sql |
| 033 | add_task_risk.py |
