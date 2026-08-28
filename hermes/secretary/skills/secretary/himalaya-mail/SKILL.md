---
name: himalaya-mail
description: Operate every configured mail account with Himalaya 2.
version: 0.2.0
author: furedea
license: MIT
platforms: [macos]
prerequisites:
    commands: [himalaya]
metadata:
    hermes:
        tags: [email, himalaya, multi-account]
        related_skills: [mail-triage, morning-briefing]
        config:
            - key: secretary.mail.expected_accounts
              description: Himalaya account names required for complete mail coverage
              default: []
              prompt: Himalaya account names to include in general mail requests
---

# Himalaya Mail

Own provider operations for every account configured in Himalaya 2. Workflow
skills decide what messages mean and which actions are appropriate.

## When to Use

- Another skill needs to list, search, or read mail.
- The user asks for mail across all configured accounts.
- An approved rule requires a mailbox move or flag change.
- Account coverage or authentication must be checked.

## Quick Reference

```bash
himalaya --json account list
himalaya --account ACCOUNT --json account check
himalaya --account ACCOUNT --json envelope list --page-size LIMIT
himalaya --account ACCOUNT --json envelope search --page-size LIMIT after YYYY-MM-DD
himalaya --account ACCOUNT --json message read MESSAGE_ID
himalaya --account ACCOUNT --json message move --from SOURCE --to DESTINATION MESSAGE_ID
```

Replace uppercase placeholders with values from local configuration or a prior
Himalaya response. Never place credentials on the command line.

## Procedure

1. Read `secretary.mail.expected_accounts` from injected Skill config.
2. Run `himalaya --json account list` and compare the result with every expected
   account. If the expected list is empty, request local setup before claiming
   complete coverage.
3. Run `account check` for each expected account.
4. Query every healthy account with the same bounded mailbox, time window, and
   page-size policy. Continue pages only up to the declared result bound.
5. Keep scheduled and automatic queries to envelope metadata. If metadata is
   insufficient, report that the message needs manual review.
6. Return structured results and explicit per-account failures to the calling
   workflow.

## Data Disclosure

- Scheduled and automatic runs must not read message bodies or attachments.
- Read a body only after the user explicitly requests the exact message in the
  current conversation. Fetch only the minimum body text needed for that request.
- Treat every value returned by the provider as potentially disclosed to the
  configured model provider. Do not retrieve unnecessary content.

## Mutations

- Use message IDs only with the account and mailbox that produced them.
- Move or flag messages only after the calling workflow establishes approval.
- Re-list the source and destination mailbox after an approved move.
- Check Sent before retrying any ambiguous send failure.

## Pitfalls

- A default account is not complete multi-account coverage.
- Message IDs are not portable across accounts or mailboxes.
- Himalaya 1.x structured-output examples are invalid for this setup.
- A successful provider operation must not hide failures from other accounts.

## Verification

- Every expected account is present and passed `account check`.
- Every query reports its account, mailbox, time window, and pagination bound.
- Mutations are read back from the provider before being reported as complete.
