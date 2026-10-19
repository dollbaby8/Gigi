# email_trace — is the insurer really not getting your email?

Email to a carrier like Nationwide passes four checkpoints. The tool tests each one:

| Checkpoint | Command | What a failure looks like |
|---|---|---|
| 1. Your domain is authenticated (SPF/DKIM/DMARC) | `python email_trace.py sender yourdomain.com` | FAIL lines; gateway marks you as spoofed |
| 2. Which security gateway the insurer uses | `python email_trace.py recipient adjuster@nationwide.com` | Shows Proofpoint / Mimecast / Microsoft, etc. |
| 3. The mailbox exists and accepts mail | `python email_trace.py probe adjuster@nationwide.com` | 550 = bad address or blocked |
| 4. What actually happened to a specific message | `python email_trace.py eml message.eml` | Bounce codes, auth results, Message-ID |

Setup: `pip install dnspython` (Python 3.8+). Run it on your own computer, since it needs internet.
The `probe` command needs outbound port 25, which most ISPs block. If it can't connect, use checkpoint 4 instead.

## Getting the .eml out of Gmail
Open the sent message (or the bounce) → ⋮ → **Download message**. Pass that file to `eml`.

## The best proof you have: the delivery log
- **Google Workspace (your own domain):** Admin console → Reporting → **Email Log Search**. Search by recipient.
  It shows the insurer's server answer, for example `250 2.0.0 OK queued as ...`, with a timestamp. That means
  their server accepted the message. Anything after that (quarantine, junk, deletion) happened on their side.
- **Personal @gmail.com:** there is no delivery log. No bounce within ~48 hours means the receiving server accepted it.

## What code cannot see
Once the insurer's server accepts the message, nobody outside can see whether it went to quarantine, junk, or an
ignored inbox. Read-receipt pixels don't work here, because Proofpoint and Mimecast strip or pre-fetch them.
