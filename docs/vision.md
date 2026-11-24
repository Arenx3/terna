# Product vision

Terna takes a recruiting team from hundreds of applications to a shortlist of three finalists. Every decision along the way is backed by evidence anyone on the team can check.

## The problem

- **Screening doesn't scale.** A single opening can draw hundreds of résumés. Reading them all carefully is impossible, so good candidates get skimmed past.
- **AI scores can't be trusted.** Tools that rank candidates give a number without a reason. A recruiter can neither verify it nor explain it to a hiring manager.
- **Bias creeps in early.** Names, photos, schools and accents shape first impressions before skills are even considered.
- **Video screening drives people away.** Many candidates are uncomfortable being recorded. When video is the only option, those people drop out or have a worse experience.
- **Candidates are ghosted.** Applicants wait weeks without news, and most rejections never arrive.

## Principles

1. **Evidence over scores.** Every assessment points to the passage, answer or moment that supports it.
2. **The AI suggests, people decide.** Recruiters can override any assessment, and every override is recorded.
3. **The candidate chooses how to answer.** Text, voice or video carry equal weight.
4. **Content, not appearance.** Terna never analyzes faces, voices or expressions. Only what the candidate said or wrote is assessed.
5. **Private by default.** Terna collects only what hiring needs, keeps it only as long as the company's policy allows, and lets candidates export or delete their data.
6. **Runs anywhere for free.** One command starts everything, with no accounts or API keys.

## Users and roles

| Role | Does | Cannot |
|---|---|---|
| **Company admin** | Sets up the company, team, pipeline stages, templates and data retention | — |
| **Recruiter** | Creates jobs, screens candidates, moves the pipeline, sends screening questions, builds the shortlist | Change company settings |
| **Hiring manager** | Owns a job; reviews the shortlist, scorecards and clips; makes the decision | See other teams' jobs |
| **Interviewer** | Scores the candidates assigned to them | See other interviewers' scores before submitting their own |
| **Candidate** | Applies, answers screening questions, schedules interviews, follows their status, requests their data. No account needed: access is by magic link | See internal notes or scores |

## The hiring journey

1. **Open a job.** Ana, a recruiter at Acme, creates *Senior Backend Engineer*. She lists must-have and nice-to-have requirements, writes the screening questions and adjusts the pipeline stages.
2. **Publish.** The job appears on Acme's public careers page in English and Spanish. It carries `JobPosting` structured data so search engines can index it.
3. **Apply.** A candidate uploads a résumé and accepts the privacy notice. The consent is stored with its version and date, and the candidate gets a link to their portal.
4. **Screen.** Background workers extract the résumé text, redact personal data and match it against each requirement.
5. **Review.** Ana opens the kanban board. Each candidate shows a breakdown such as "4 of 5 must-haves, 2 of 4 nice-to-haves", with the evidence behind each one. In blind mode she sees "Candidate #A7F3" instead of a name.
6. **Ask.** Ana moves 20 candidates to async screening. Each receives the job's questions and answers in text, voice or video.
7. **Listen.** Voice and video answers are transcribed. Ana reads the transcripts first, searches all answers for "Kubernetes", jumps to the exact moment and shares a clip with the hiring manager.
8. **Interview.** Finalists pick a time slot and receive a calendar invite. Each interviewer fills in a scorecard without seeing the others.
9. **Calibrate.** Terna shows that one interviewer scores, on average, a full point below the panel's consensus.
10. **Shortlist.** Ana builds the terna: three finalists side by side, with evidence, scorecards and clips. The hiring manager decides.
11. **Close.** Everyone not selected receives a respectful message. Analytics update. When the retention period ends, their data is purged automatically.

## Features in depth

### Explainable screening

- Each requirement gets a verdict, **meets**, **partial** or **no evidence**, together with the exact résumé passage, highlighted in place.
- Matching combines three signals:
  - Keywords with known aliases: "k8s" counts as Kubernetes.
  - Semantic similarity across languages.
  - Rules such as years of experience, computed from job dates.
- The overall result is a visible weighted sum, never an opaque score.
- Name, age, gender, photo and address are removed before analysis, so the matching cannot use them.
- Matching quality is measured against a labeled set of synthetic résumés on every change.

### Async screening

**For the candidate:**
1. A camera and microphone check, plus one practice question that is not scored.
2. Each question shows a prep countdown and a time limit. Retakes are allowed if the recruiter permits them.
3. The candidate answers in text, voice or video.
4. Each answer uploads as soon as it is submitted. A dropped connection never loses work: the candidate resumes where they left off.
5. Works on a phone.

**For the recruiter, per job:**
- Questions written for the job or taken from the company's question bank.
- Per question: the allowed formats, prep time, maximum length and number of retakes.
- Whether questions are revealed on the spot or shown in advance.
- An optional short video of the recruiter asking each question, so the candidate faces a person rather than plain text.
- A deadline, with automatic reminders.

### Transcript-first and blind review

Reviewers see the transcript before any video. In blind mode the transcript is the whole review: a candidate can reach the interview stage without anyone seeing their face or hearing their voice. A video can be revealed only after it has been scored.

### Search and clips

Full-text and semantic search runs across every answer of a job or of the whole company. Results jump to the exact second. A clip is a time range shared through a signed link that expires.

### Scorecards and calibration

- Competencies are scored from 1 to 4, and each score needs a written justification.
- Interviewers can't see other scores until they submit their own.
- Calibration compares each interviewer with the panel's consensus on the same candidates. It appears only after enough scorecards exist to be meaningful.

### The Terna view

A side-by-side comparison of the finalists: requirement evidence, scorecards, key clips and notes. It can be shared with the hiring manager in one click.

### Candidate portal

- Live status of each application.
- Self-scheduling from the interviewers' availability, with a calendar invite.
- A respectful closing message when the process ends.
- Data export and deletion requests.

### Analytics

Time to hire, time in each stage, conversion between stages, results by source, and completion rate by answer format. Alerts flag candidates waiting too long for a response.

### Privacy

- Consent records with versioned privacy notices.
- Retention policies per company, with automatic purging of résumés, recordings and transcripts.
- Data subject requests (ARCO rights under Mexico's LFPDPPP, and GDPR rights), tracked until resolved.

Terna's privacy features follow these regulations' principles. They are not legal advice.

## Out of scope

- Payroll, onboarding and e-signatures
- Job board integrations that require paid accounts
- Native mobile apps (the web app is responsive)
- OCR of scanned résumés: these are flagged for manual review
- Collection of demographic data

## Known limits

- **Transcription runs on the CPU.** It takes minutes, not seconds, per answer. The model size is configurable.
- **Safari and iOS record in a different format.** Their recording support needs dedicated testing.
- **Résumé parsing depends on layout.** Unusual layouts can split passages imperfectly.

## How we will know it works

- Screening precision and recall, measured on labeled data and reported on every change
- Async screening completion rate by answer format
- Time from application to first response
- Zero cross-tenant data access in the isolation test suite
