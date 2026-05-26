# Anki cloze card rules

Each chapter gets 15-30 cloze-deletion cards. The goal is durable retention of the chapter's technical core, not exhaustive note-taking.

## What to clozify

These convert well to cloze cards because they have a clear, short answer that's worth memorising.

- **Definitions**: "{{c1::TGT}} is the ticket issued by the KDC after initial Kerberos authentication."
- **Command syntax**: "To enumerate users with rpcclient: `rpcclient -U \"\" -N {{c1::target_ip}}` then `{{c2::enumdomusers}}`."
- **Default values**: "The default port for {{c1::Kerberos}} is {{c2::88}}."
- **Function/method signatures**: "In Python's socket module, you create a TCP client socket with `socket.socket({{c1::AF_INET}}, {{c2::SOCK_STREAM}})`."
- **Specific facts and numbers**: "Sysmon Event ID {{c1::1}} records {{c2::process creation}}."
- **Cause-effect pairs**: "If a Windows authentication fails with status code {{c1::0xC000006E}}, the cause is {{c2::account restrictions, e.g. logon hours or workstation restrictions}}."
- **Abbreviations and what they stand for**: "{{c1::SPN}} stands for {{c2::Service Principal Name}}."
- **Configuration keys**: "The Sysmon config rule for `lsass.exe` access lives under {{c1::ProcessAccess}}, filtered by `TargetImage` containing {{c2::lsass.exe}}."

## What NOT to clozify

These make bad cards. Cloze deletion works for short, precise answers; long prose makes the answer fuzzy and the card unreviewable.

- Long explanatory prose: "Active Directory is a complex distributed system that manages..." (no clean cloze possible)
- Conceptual paragraphs without a discrete fact at the centre
- Anything subjective ("the best way to...")
- Sequences of more than three items (use multiple separate cards instead)
- Whole code blocks (clozify a key parameter inside a code block instead)

## Card construction tips

### Use multiple cloze numbers per note when they share context

```
"Sysmon Event ID {{c1::3}} captures {{c2::network connections}}, including the source PID, source IP, destination IP, and destination port."
```

This generates two cards from one note: one tests the ID, the other tests what it captures. Both share the surrounding context, so the user gets reinforcement.

### Add hints when the answer is ambiguous

```
"In Kerberoasting, the attacker requests a {{c1::TGS::ticket type}} for an account with an SPN, then cracks it offline."
```

The `::ticket type` hint disambiguates, since "TGT" and "TGS" are easily confused.

### Use the `extra` field for context the user shouldn't memorise but might want when reviewing

```json
{
  "text": "Default LDAP port is {{c1::389}} (cleartext) or {{c1::636}} (TLS).",
  "extra": "LDAPS over 636 wraps LDAP in TLS. Active Directory also exposes Global Catalog on 3268 (cleartext) and 3269 (TLS)."
}
```

The extra appears on the back of the card after they've answered. It gives more context without being part of what they have to memorise.

### Keep cloze content short

A good cloze answer is a few words at most. If your cloze is hiding half a sentence, restructure into multiple shorter cards.

Bad: "TCP three-way handshake is {{c1::client sends SYN, server replies SYN-ACK, client replies ACK}}."

Better:
- "In the TCP three-way handshake, the client first sends a {{c1::SYN}} packet."
- "After receiving a SYN, the server replies with {{c1::SYN-ACK}}."
- "The handshake completes when the client sends a final {{c1::ACK}}."

### Code in cards

Wrap inline code in backticks; multi-line code in triple-backtick blocks. The Anki card CSS in the script renders monospace and adds a dark background.

```
"To list all event logs in PowerShell: `Get-WinEvent -ListLog {{c1::*}}`"
```

## Volume guidance

| Chapter type | Target cards |
|---|---|
| Light, short conceptual chapter | 15 cards |
| Standard chapter with mixed content | 20 cards |
| Dense chapter with lots of facts (commands, IDs, defaults) | 25-30 cards |
| Reference / appendix-style chapter | up to 30 |

Don't pad for volume. If a chapter only has 12 things worth memorising, generate 12 cards.

## Card review

Before saving the cards JSON, sanity check:

1. Every card has at least one `{{c1::}}` cloze.
2. No card contains long prose where the cloze is unclear.
3. No two cards are duplicates (same text, same cloze).
4. The set covers the chapter's main subsections roughly proportionally; don't have 25 cards on subsection 1 and 0 on subsections 2-5.
5. No card exceeds about 250 characters in the visible text. Longer cards are unreviewable on mobile.

## Example cards JSON

```json
[
  {
    "text": "TCP is a {{c1::connection-oriented}} protocol; UDP is {{c2::connectionless}}.",
    "extra": "TCP guarantees in-order delivery and retransmission; UDP does not."
  },
  {
    "text": "In Python's socket module, you create a TCP socket with `socket.socket({{c1::AF_INET}}, {{c2::SOCK_STREAM}})`.",
    "extra": ""
  },
  {
    "text": "Sysmon Event ID {{c1::3}} captures {{c2::network connections}}.",
    "extra": "Other useful Sysmon events: 1 (process creation), 7 (image load), 10 (process access), 11 (file create)."
  }
]
```
