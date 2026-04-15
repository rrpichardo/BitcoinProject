# Team Charter — Real-Time Crypto Volatility Detection

## Team Members & Roles

| Member | Primary Role | Responsibilities |
|--------|-------------|-----------------|
| Rico Pichardo Abreu  | Model Lead & Improvements | Base model selection, feature engineering improvements, model retraining, handoff folder maintenance |
| Honey Streak | Infrastructure Lead | FastAPI service, Docker Compose setup, Kafka/MLflow containerization, GitHub repo structure |
| Swetaleena Guha | Replay Pipeline & Testing | Run 10-minute slice through the pipeline, validate /predict endpoint end-to-end, write test results |
| Irene John| Docs & Diagrams | team_charter.md, selection_rationale.md, system architecture diagram, model card updates |

---

## Project Goal

Build a real-time crypto volatility detection system that ingests live BTC-USD tick data from Coinbase, engineers windowed features, and serves predictions via a FastAPI endpoint — all orchestrated with Kafka, MLflow, and Docker Compose.

---

## Ways of Working

**Communication:** WhatsApp group for async coordination. Tag a teammate if you need a response within 24 hours.

**Code:** All work lives in the shared GitHub repo (`streakh/Real-Time-Crypto-ML`). Push to feature branches; merge to `main` only when the task is complete and tested.

**Decisions:** Majority agreement for significant changes (e.g. switching models, changing feature definitions). One person documents the rationale in `docs/`.

**Blockers:** If blocked for more than a few hours, post in WhatsApp immediately — don't wait until end of day.

---

## Definition of Done (Week 4)

- [ ] `docker compose up -d` brings up Kafka, MLflow, and the API cleanly
- [ ] All four endpoints (`/health`, `/predict`, `/version`, `/metrics`) return valid responses
- [ ] 10-minute raw slice replayed through `/predict` with predictions logged
- [ ] `team_charter.md` and `selection_rationale.md` committed to `docs/`
- [ ] Architecture diagram committed to `docs/`
- [ ] No secrets committed to the repo (`.env.example` only)

---

## Norms

- We have created a WhatsApp group where the primary conversation will take place. All coordination, updates, and blockers should be communicated there.
- Be responsive — a short "on it" or "blocked, need help" goes a long way.
- Don't break `main` — test locally before pushing.
- Document your GenAI usage in `docs/genai_appendix.md` as you go, not at the end.
- If the model numbers change, update the model card — don't leave stale metrics in docs.

---

## Decision-Making Process

Decisions are made by consensus based on a majority vote among team members. For significant changes (e.g. switching models, changing feature definitions), the outcome and reasoning should be documented in `docs/` by the person who raised the discussion.

---

## Conflict Resolution Plan

- Discuss the issue openly within the team WhatsApp group or in a group call.
- Respect one another's perspective — every team member's input is valued.
- If a resolution cannot be reached within the team, escalate to the course instructor.

---

## Accountability & Performance

Progress will be tracked based on the weekly action plan outlined in the Canvas assignment. Each team member is responsible for completing their assigned tasks by the deadlines specified there. Any delays or blockers should be flagged in the WhatsApp group as early as possible so the team can adjust.

---

## Tools & Resources

**Tech stack:** Python, Kafka (KRaft), MLflow, Docker

**Platforms:** GitHub (`streakh/Real-Time-Crypto-ML`) for version control, Google Docs for shared writing and planning, WhatsApp for team communication

**Datasets & APIs:** Coinbase Advanced Trade WebSocket API (public market data — BTC-USD ticker feed). No trades are placed.
