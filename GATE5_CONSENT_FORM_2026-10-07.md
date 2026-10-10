# Gate 5 — participant consent and data terms

**Version:** 2026-10-07 · **Study:** Screenplay Studio formative writer study (Gate 5)
**Facilitator:** ______________________ · **Participant ID:** `W___` (no names in the write-up)

Please read this before importing your script. Ask anything you want clarified — that is not a
disruption, it is part of the study.

---

## 1. What this study is testing

**The tool, not your writing.** You are being asked to judge whether notes the software produces about
your script are true. A note you mark "wrong" is a result about the software. There is no version of
this session in which your pages are being assessed.

## 2. What happens in the session

You import your own script into a local project, run the analysis, and read the notes cold. You then
mark each note as **Correct**, **Partial**, or **Wrong** using the truth row, and work through the fix
loop for the ones you marked Correct. The analysis takes roughly **30 minutes** on a feature-length
script and runs **twice**, so the session is around **2 hours** and can be split into two sittings.

No one will explain what a note means or which ones to trust before you have judged them. If you are
confused, that is useful data — please say so out loud rather than asking for the answer.

## 3. Where your data lives, and what is collected

**Everything in this study runs locally, on this machine — conditional on the check immediately below,
which the facilitator completes before you sign.** There is no account, no cloud component, and nothing
about your script or your judgements is stored by any third party **once that check passes**.

**The check below is what makes the paragraph above true, so it is verified rather than asserted.** The
analysis sends your script text to a language model. If that model runs on this machine, the text never
leaves it — which is how this study is run. If the tool were pointed at a model somewhere else, your text
*would* be transmitted to that endpoint: the product supports both, and you have no way to check it
yourself. So the facilitator confirms the endpoint **before you sign**:

| check, before consent | result |
|---|---|
| configured model endpoint | ______________________ |
| host is this machine (`127.0.0.1` / `localhost` / loopback) | [ ] verified |
| model served locally | ______________________ |

**If any row cannot be confirmed, do not proceed.** The "stays on this machine" promise would then not
be true, and you would be consenting to something we cannot stand behind.

Collected, in the project directory at: ______________________________________

| item | what it is |
|---|---|
| your script | the file you imported |
| `report.findings.json` | the analysis output |
| `finding_verdicts.json` | your Correct / Partial / Wrong judgements |
| `feedback_ledger.json` | the record of which notes appeared in which run |
| facilitator notes | your verbatim reactions, kept by the facilitator |

*(The endpoint check above is what makes the previous paragraph true; its result is recorded there, not
here.)*

## 4. Retention, deletion, and withdrawal

- **Retention period:** the project directory is kept until ______________ (default: 30 days).
- **Deletion date:** on or before ______________ it is deleted, including all copies.
- **Withdrawal:** you may withdraw at any point, during or after the session, without giving a reason.
  On request, the project directory and the facilitator's notes are deleted within **7 days**, and any
  material already drafted is removed from the write-up.
- **Exports:** ask before anything is copied off this machine. Nothing is exported by default.

## 5. Quoting

Your verbatim reactions are much more useful than a summary of them. Please choose:

- [ ] **Yes** — you may quote my reactions, **anonymised** (as `W___`, no name, no script title).
- [ ] **Yes** — you may quote my reactions, **attributed** as ______________________.
- [ ] **No** — you may record my reactions but must not quote them.

Quotes about specific pages can identify a script, so the default is anonymised.

## 6. What you will and will not get

You will get: your own analysis report, and a summary of the study's findings when it is written.
You will not get: any claim that the tool is accurate because you took part. Five writers is formative
evidence, and the write-up is required to say so.

---

**Agreed:**

Participant: ______________________  Date: __________

Facilitator: ______________________  Date: __________

**Facilitator, on the day:** confirm §3's path is real and writable, and that the model is the local one.
Record in the notes whether a **merge disclosure** and a **run caveat** were ever on screen — if they
were not, those surfaces were **not tested** and the write-up must say "not exercised", never "passed".
