"""Gigi: an S.D. Tex. litigation assistant.

Modules:
    holidays     -- federal legal holidays (FRCP 6(a)(6))
    deadlines    -- FRCP 6 time computation, S.D. Tex. LR 7.3 submission days,
                    post-judgment and appeal deadlines
    docket       -- load, classify, and analyze docket sheets
    courtlistener-- CourtListener REST client for judge-specific opinion/order search
    playbook     -- curated, citation-verified authority bank keyed to docket targets
    brief        -- render brief-ready Markdown inserts from a playbook
    ics          -- iCalendar export of deadlines
    dashboard    -- self-contained HTML case dashboard
"""

__version__ = "0.1.0"
