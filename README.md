# Running Dashboard

Personal fitness dashboard — single HTML file, no build step.

- Daily metrics: sleep, HRV, RHR, mood, water, Liquid IV
- Run log with pace chart and mileage graph
- Daily goals with cross-device sync via Firebase Firestore
- Morning readiness checklist + daily readiness score
- Shoe tracker, strength log, cross-training log
- Electrolyte / iron / vitamin trackers
- Heat & sweat calculator

Deployed via GitHub Pages. Data syncs between iPhone (homescreen app) and laptop through Firestore; localStorage serves as an instant-render cache.
