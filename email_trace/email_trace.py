#!/usr/bin/env python3
"""
email_trace.py - figure out where an email to an insurer is dying.

Run on your own computer (needs internet):
    pip install dnspython
    python email_trace.py sender  yourdomain.com      # is YOUR side authenticated?
    python email_trace.py recipient adjuster@nationwide.com   # who filters THEIR mail?
    python email_trace.py probe   adjuster@nationwide.com   # does their server accept the address?
    python email_trace.py eml     saved_message.eml     # read a sent copy or a bounce

What it can prove: whether your mail is authenticated, which security gateway the
insurer uses, whether the mailbox exists, and (from a bounce) the exact rejection
reason. What it cannot see: anything after the insurer's server accepts the
message (quarantine, junk folder, an adjuster ignoring it). For that, use the
delivery log described in README.md.
"""
import email
import re
import smtplib
import socket
import sys
from email import policy

try:
    import dns.resolver
except ImportError:
    sys.exit("Install dnspython first:  pip install dnspython")

# Known MX patterns -> the filtering vendor sitting in front of the inbox.
GATEWAYS = {
    "pphosted.com": "Proofpoint (heavy quarantine; attachments/links often held)",
    "ppe-hosted.com": "Proofpoint Essentials",
    "mimecast.com": "Mimecast (holds mail from unknown senders for review)",
    "protection.outlook.com": "Microsoft 365 / Exchange Online Protection",
    "iphmx.com": "Cisco Secure Email (IronPort)",
    "barracudanetworks.com": "Barracuda",
    "google.com": "Google Workspace",
    "googlemail.com": "Google Workspace",
    "messagelabs.com": "Broadcom/Symantec MessageLabs",
    "fireeyecloud.com": "Trellix/FireEye",
}

DKIM_SELECTORS = ["google", "selector1", "selector2", "default", "k1", "s1", "s2"]


def txt(name):
    try:
        return [b"".join(r.strings).decode() for r in dns.resolver.resolve(name, "TXT")]
    except Exception:
        return []


def mx(domain):
    try:
        recs = dns.resolver.resolve(domain, "MX")
        return sorted((r.preference, str(r.exchange).rstrip(".")) for r in recs)
    except Exception as e:
        return [(None, f"MX lookup failed: {e}")]


def ok(flag, msg):
    print(f"  [{'PASS' if flag else 'FAIL'}] {msg}")


def check_sender(domain):
    print(f"\nSender authentication for {domain}")
    if domain.lower() in ("gmail.com", "googlemail.com"):
        print("  Personal @gmail.com: Google manages SPF/DKIM/DMARC; nothing to fix here.")
        print("  Note: many insurer gateways score free-mail senders lower than a firm domain.")
        return
    spf = [t for t in txt(domain) if t.lower().startswith("v=spf1")]
    ok(len(spf) == 1, f"SPF: {spf or 'MISSING'}")
    if spf and "_spf.google.com" not in spf[0]:
        print("        -> SPF does not include _spf.google.com; Gmail-sent mail will fail SPF.")
    dmarc = [t for t in txt(f"_dmarc.{domain}") if t.lower().startswith("v=dmarc1")]
    ok(bool(dmarc), f"DMARC: {dmarc or 'MISSING (insurer gateways penalize this)'}")
    found = [s for s in DKIM_SELECTORS if any("p=" in t for t in txt(f"{s}._domainkey.{domain}"))]
    ok(bool(found), f"DKIM selectors found: {found or 'none of the common ones'}")
    if not found:
        print("        -> In Google Admin: Apps > Gmail > Authenticate email > Generate DKIM.")


def check_recipient(addr):
    domain = addr.split("@")[-1]
    print(f"\nInbound mail path for {domain}")
    for pref, host in mx(domain):
        vendor = next((v for k, v in GATEWAYS.items() if host.lower().endswith(k)), "unrecognized")
        print(f"  MX {pref}: {host}  ->  {vendor}")
    return domain


def probe(addr, mail_from="probe@example.com"):
    """SMTP conversation up to RCPT TO only. No message is sent."""
    domain = check_recipient(addr)
    hosts = [h for p, h in mx(domain) if p is not None]
    if not hosts:
        return
    host = hosts[0]
    print(f"\nProbing {host}:25 (no message is delivered)")
    try:
        with smtplib.SMTP(host, 25, timeout=20) as s:
            s.ehlo(socket.getfqdn())
            code, resp = s.mail(mail_from)
            print(f"  MAIL FROM -> {code} {resp.decode(errors='ignore')}")
            code, resp = s.rcpt(addr)
            print(f"  RCPT TO   -> {code} {resp.decode(errors='ignore')}")
            if code in (250, 251):
                print("  Address accepted. If mail 'vanishes', it is being quarantined or ignored "
                      "AFTER acceptance, not bounced.")
            elif 500 <= code < 600:
                print("  Rejected. Either the address is wrong or the gateway blocks it.")
    except (socket.timeout, OSError) as e:
        print(f"  Could not connect ({e}). Most home/office ISPs block outbound port 25;")
        print("  run this from a cloud server, or rely on the bounce / delivery log instead.")


BOUNCE_HINTS = {
    "5.1.1": "Mailbox does not exist - wrong address.",
    "5.7.1": "Policy rejection - gateway refused you (reputation, content, or blocklist).",
    "5.7.26": "Failed DMARC/authentication.",
    "5.7.509": "Microsoft: DMARC failure.",
    "5.7.606": "Microsoft: sending IP blocked.",
    "5.4.1": "Recipient domain refused relay/access denied.",
    "4.7.": "Temporary deferral (greylisting/throttling) - retry pending.",
    "5.2.2": "Mailbox full.",
    "5.3.4": "Message too large - shrink attachments.",
}


def read_eml(path):
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    print(f"\nMessage: {msg['Subject']!r}  From: {msg['From']}  To: {msg['To']}  Date: {msg['Date']}")
    print(f"Message-ID: {msg['Message-ID']}   <- quote this when demanding they search their logs")

    for ar in msg.get_all("Authentication-Results", []):
        for mech in ("spf", "dkim", "dmarc"):
            m = re.search(rf"\b{mech}=(\w+)", ar)
            if m:
                ok(m.group(1).lower() == "pass", f"{mech.upper()} = {m.group(1)}")

    print("\nHops (oldest first):")
    for r in reversed(msg.get_all("Received", [])):
        print("  " + " ".join(r.split())[:160])

    body = msg.get_body(preferencelist=("plain", "html"))
    text = (body.get_content() if body else "") + str(msg)
    codes = set(re.findall(r"\b([45]\.\d{1,3}\.\d{1,3})\b", text))
    if codes:
        print("\nBounce status codes found:")
        for c in sorted(codes):
            hint = next((v for k, v in BOUNCE_HINTS.items() if c.startswith(k)), "see full bounce text")
            print(f"  {c}: {hint}")
    seen = set()
    for line in text.splitlines():
        if line.strip() not in seen and re.search(r"(remote server|diagnostic-code|said:|550|554|553)", line, re.I):
            seen.add(line.strip())
            print("  > " + line.strip()[:200])


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("sender", "recipient", "probe", "eml"):
        sys.exit(__doc__)
    cmd, arg = sys.argv[1], sys.argv[2]
    {"sender": check_sender, "recipient": check_recipient, "probe": probe, "eml": read_eml}[cmd](arg)


if __name__ == "__main__":
    main()
