# Reporting Requirements & Plans

## Sources
- [R&R v1.0](XPRIZE%20Wildfire%20Track%20A%20Finals%20-%20Rules%20and%20Regulations%20v1.0.md)
- [All-teams call 2026-03-17](../meetings/2026-03-17_all-teams-call_notes.md)
- [Daily report template](https://docs.google.com/document/d/1tv1byuTecHJHllIRhx7Iv3dhyVpp6AZY/edit)
- [Final report template](https://docs.google.com/document/d/1o2cZq-w4FciyPboqLkIMaHCMOBUQp3s2G7TGUUJx0-s/edit?tab=t.0#heading=h.30j0zll)

---

## 1. Real-Time: Team System Access

| Aspect | Requirement |
|--------|------------|
| **What** | Judges observe your platform live during testing days |
| **When** | Continuously during burns |
| **Delivery** | Logins, portal access, or screen share (Rule 4) |
| **Content** | 1-min detection, 10-min characterization, 15-min updates |
| **Format** | No constraints — your system |
| **Notes** | This is the primary real-time judging method. 1-min clock starts at satellite overpass, not ignition. |

### Our plan
- [ ] TODO: Define how judges will access our system (logins? portal? screen share?)
- [ ] TODO: Ensure system can display detections, characterizations, and updates in real time

---

## 2. Real-Time (Optional): OGC Data to ArcGIS

| Aspect | Requirement |
|--------|------------|
| **What** | Live OGC-format data pushed to ESRI/ArcGIS portal |
| **When** | During burns (optional in real-time; required in daily report) |
| **Delivery** | API or integration with ArcGIS Online |
| **Format** | OGC standard (schema expected ~2026-03-24) |
| **Notes** | Not scored on ESRI integration quality per se, but scored on OGC data quality and delivery speed. New ESRI portal is live. |

### Our plan
- [ ] TODO: Decide whether to implement real-time ESRI integration or batch with daily report
- [ ] TODO: Review OGC schema when released (~Mar 24)
- [ ] TODO: Smoke test ESRI integration before April 8 dry run

---

## 3. Daily Report (Email)

| Aspect | Requirement |
|--------|------------|
| **What** | Summary of all fires detected that day |
| **When** | By 20:00 daily (UTC+10) |
| **Delivery** | Email to wildfire@xprize.org |
| **Subject** | `XPWF-A <TEAM NAME> Finals Daily Report <DD MM YYYY>` |
| **Format** | Word/PDF following [XPRIZE template](https://docs.google.com/document/d/1tv1byuTecHJHllIRhx7Iv3dhyVpp6AZY/edit) |
| **Content** | All fires detected (not just competition fires), EO sources used that day, OGC data files |
| **Notes** | OGC data attached/included for ESRI ingestion. Report every fire regardless of whether XPRIZE monitored it. |

### Our plan
- [ ] TODO: Review daily report template and build workflow to populate it
- [ ] TODO: Decide format for OGC data attachment (which OGC file type?)
- [ ] TODO: Build process to catalogue all detections throughout the day for end-of-day report
- [ ] TODO: Assign who is responsible for compiling and sending the daily report

---

## 4. Final Report (Email)

| Aspect | Requirement |
|--------|------------|
| **What** | Comprehensive summary of all observations across the finals window |
| **When** | Within 24 hours of finals closure (exact time TBD) |
| **Delivery** | Email to wildfire@xprize.org |
| **Subject** | `XPWF-A <TEAM NAME> Final Report` |
| **Format** | Following [XPRIZE template](https://docs.google.com/document/d/1o2cZq-w4FciyPboqLkIMaHCMOBUQp3s2G7TGUUJx0-s/edit?tab=t.0#heading=h.30j0zll) |
| **Content** | Detailed description of system used, all observations, which EO sources were used when and on which fires (Rule 3). Can be more detailed than daily reports. |
| **Notes** | This is the team's opportunity to provide context and clarification to judges. |

### Our plan
- [ ] TODO: Review final report template
- [ ] TODO: Plan how to accumulate data across the testing window for the final report
- [ ] TODO: Assign who is responsible for compiling the final report

---

## 5. VIP Presentation (April 15)

| Aspect | Requirement |
|--------|------------|
| **What** | Team presentation to VIPs, sponsors, RFS, XPRIZE CEO |
| **When** | 2026-04-15, time TBD (two blocks to accommodate time zones) |
| **Duration** | 7-8 minutes per team, followed by panel Q&A |
| **Notes** | Up to 2 additional guests (non-team) for dinner. |

### Our plan
- [ ] TODO: Prepare presentation
- [ ] TODO: Decide who presents (on-site vs remote)
- [ ] TODO: Identify any guests to invite

---

## Format & Standards (All Reporting)

| Standard | Requirement | Reference |
|----------|------------|-----------|
| **Geospatial data** | OGC format | Rule 7 |
| **Units** | SI | Rule 5 |
| **Date/time** | ISO 8601, UTC or UTC+10 (K) | Rule 6 |
| **EO source declaration** | Every report must declare sources used | Rule 3 |

---

## Key Dates

| Date | Deliverable |
|------|------------|
| 2026-03-18 | Satellite list submission |
| ~2026-03-24 | OGC/ESRI schema expected |
| 2026-03-31 | Finals Application (CONOPS, quad chart, system diagram, AI/ML plan, personnel, ROM cost) |
| 2026-04-08 | Dry run / integration shakeout |
| 2026-04-09–21 | Daily reports due by 20:00 each testing day |
| 2026-04-15 | VIP presentation |
| Finals close + 24h | Final report due |
