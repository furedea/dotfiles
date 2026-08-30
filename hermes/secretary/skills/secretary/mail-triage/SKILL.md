---
name: mail-triage
description: Prioritize and clean mail across every configured account.
version: 0.5.0
author: furedea
license: MIT
platforms: [macos]
metadata:
    hermes:
        tags: [email, triage, cleanup]
        related_skills: [apple-mail, morning-briefing]
---

# Mail Triage

Turn all Apple Mail inboxes into one bounded queue of decisions. Load
`apple-mail` for local provider operations.

## When to Use

- The user asks what mail needs attention.
- The user asks to clean or organize inboxes.
- A morning briefing needs important mail from every configured account.
- The user asks to preview a supported mailbox change.

## Procedure

1. Establish the mailbox scope, time window, maximum message count, and allowed
   actions. A morning briefing is read-only.
2. Load `apple-mail`, enumerate the configured accounts, and report any
   coverage failure.
3. Request the minimum mail facts needed through `apple-mail`. That connector
   owns data disclosure, untrusted-content handling, authorization, and
   provider verification; do not bypass its policy. If the permitted facts are
   insufficient, mark the message for manual review.
4. Classify each message as urgent reply, reply, action without reply, waiting,
   reference, or noise. Give a short evidence-based reason.
5. Send proposed supported mutations to `apple-mail`; the connector owns their
   preview, approval, execution, and verification lifecycle.

## Output Shape

1. Needs attention now
2. Replies or decisions needed
3. Actions without replies
4. Waiting on others
5. Reference and proposed cleanup
6. Coverage and failures

## Pitfalls

- Treating unread as synonymous with important.
- Claiming complete coverage when account enumeration or a query failed.
- Inferring a disposition that the observed mail facts do not support.

## Verification

- Every configured account was covered or named as a failure.
- Every surfaced disposition has a reason traceable to observed mail data.
- Every provider operation completed under the `apple-mail` policy.
