# ADR-0014: Retire ical and xurl

- Status: Accepted
- Date: 2026-08-24
- Supersedes: ADR-0012, ADR-0013

In the context of maintaining a focused personal secretary, facing custom
`ical` and `xurl` packages that are no longer wanted, we decided for Google
Workspace as the calendar boundary and Himalaya as the mail boundary, and
against retaining the EventKit and X integrations, to reduce credentials and
custom package maintenance, accepting that the secretary no longer summarizes
X posts and Google Calendar requires separate OAuth setup.
