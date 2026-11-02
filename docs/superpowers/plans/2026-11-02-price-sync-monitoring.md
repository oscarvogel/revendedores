# Monitor de sincronización de precios — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that the existing ERP sync persisted article withdrawal/delivery base prices in Revendedores, compare customer-facing canary prices with the VFP reference every 2 hours, and run a bounded nightly full audit with deduplicated WhatsApp alerts.

**Architecture:** Add a standalone Python monitor to this repository under `ops/automatizaciones/`, with its own unit-testable comparison and alert-state functions. Deploy that script into the existing scheduler image, where it can import the live VFP `Calculaprecio` reference and reuse the configured WhatsApp sender from `/data/jobs`; schedule it after the existing updater and guard each run with the shared monitor lock. Production inspection confirmed the updater cron at `0 * * * *` (hourly). The full audit reads back the four persisted `pblret*`/`pblrep*` fields for every article and compares final prices for every active article × distinct complete customer pricing profile × delivery mode. The portal-side calculation is kept in a small pure function matching `calcular_precio_articulo`; the independent expected value uses VFP `PrecioBase` + `PrecioPublico`. The canary includes client 00591/condition 53 and rotates across other customers, products, lists, freight types, and delivery modes.

**Tech Stack:** Python 3.12, existing Peewee legacy models/VFP calculator, existing `resumen_dashboard_whatsapp` sender, cron, pytest.

**Spec:** `docs/specs/price-sync-monitoring.md`

## Global Constraints

- The current updater remains the only mass writer of ERP article/customer data.
- Do not report success until the updater completed without database errors and the persisted Revendedores values have been read back.
- Compare all four fields `pblret1`, `pblrep1`, `pblret4`, and `pblrep4` against the VFP `PrecioBase` reference; compare final prices for every active article and distinct complete customer pricing profile against VFP `PrecioPublico`.
- Run canaries every 2 hours and the full audit nightly, in bounded batches with a single-run lock and resource/time limits.
- Reuse the existing WhatsApp recipient/configuration; do not add credentials or phone numbers to source control.
- Deduplicate alerts; send only for new/changed discrepancies, sync failures, read failures, or incomplete scans.

## Review Focus

1. A running updater lock must defer the monitor and never create a green result.
2. A caught `OperationalError` in the updater log must count as a sync failure even if the process exits zero.
3. Decimal differences at the configured tolerance boundary must be classified consistently.
4. List 4, payment condition 53, and delivery freight must be included in canary coverage.
5. A failed WhatsApp send must preserve alert state for retry and must not mark the discrepancy as notified.
6. A legitimate zero price must not be treated as missing or overwritten.

---

### Task 1: Price comparison and alert state

**Files:**
- Create: `ops/automatizaciones/price_sync_monitor.py`
- Test: `ops/automatizaciones/tests/test_price_sync_monitor.py`

**Interfaces:**
- `compare_price(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool` returns true when values differ by more than tolerance.
- `compare_synced_article(article, reference) -> list[dict]` returns discrepancies keyed by article/list/mode for the four persisted base prices.
- `calculate_portal_price(article, customer, location, payment, modality) -> Decimal` mirrors the portal calculation using only supplied rows.
- `calculate_vfp_price(calculator, article, customer, location, payment, modality) -> Decimal` composes the legacy `PrecioBase` and `PrecioPublico` calls as an independent reference.
- `update_alert_state(previous: dict, current: list[dict]) -> tuple[dict, list[dict]]` returns persisted deduplication state and alerts to send.

- [x] Write failing tests for exact match, tolerance boundary, each of the four pbl fields, new/changed/resolved discrepancies, legitimate zero prices, and WhatsApp failure retry behavior.
- [x] Run the focused pytest command; confirm the expected missing-function failures.
- [x] Implement the pure comparison/state functions using `Decimal` and stable fingerprints; resolved discrepancies leave the active state.
- [x] Run the focused command; all tests pass (23 total after integration hardening).

### Task 2: ERP/Revendedores integration and WhatsApp notification

**Files:**
- Modify: `ops/automatizaciones/price_sync_monitor.py`
- Test: `ops/automatizaciones/tests/test_price_sync_monitor.py`

**Interfaces:**
- `run_monitor(mode: str, *, dry_run: bool = False) -> dict` accepts `canary` or `full` and returns counts, sync status, discrepancies, and completion status.
- The integration loads `libs.Facturacion.Calculaprecio` for the VFP reference, reads `ArticulosReventa` only after the updater lock is clear, and imports `destinatarios`/`enviar` from the existing WhatsApp automation module in `/data/jobs`.

- [x] Add failing integration tests for updater-running, updater-log `OperationalError`, database read failure, successful readback, incomplete full scan, zero-price preservation, and failed WhatsApp send.
- [x] Run the focused pytest command and confirm those failures.
- [x] Implement canary rotation across client/payment/list/delivery cases, including 00591/condition 53; run the nightly audit over every active article × distinct complete customer pricing profile × both delivery modes. Compare all four persisted pbl fields to VFP `PrecioBase`, then compare portal-side final prices with VFP `PrecioBase` + `PrecioPublico`.
- [x] Recheck persisted article rows after the current sync; if sync errors or any batch is incomplete, record non-green status and alert. When possible, still inspect the persisted prices after a sync error, but never report green.
- [x] Reuse `resumen_dashboard_whatsapp.destinatarios(env)` and `enviar(texto, telefono, env, dry_run)`; persist dedupe state atomically under `/data`.
- [x] Run focused tests and fixture dry-run coverage; verify message formatting does not expose credentials or unnecessary customer details.

### Task 3: Scheduler deployment and live verification

**Files:**
- Create: `ops/automatizaciones/price_sync_monitor.cron`
- Modify: `deploy_production.md`
- Compose/Dockerfile: `/srv/fasa-data/compose/automations/automatizaciones/`
- Production build context/source: `/srv/fasa-data/automation-src/automatizaciones/jobs/price_sync_monitor.py`
- Production cron source: `/srv/fasa-data/automation-src/automatizaciones/cron.disabled`

**Interfaces:**
- Schedule canary runs every 2 hours at minute 15; schedule the nightly full scan at 03:10, with a hard 45-minute internal limit before the 04:00 updater, and skip canaries while the full scan lock is held.
- Cron invokes `price_sync_monitor.py --mode canary` or `--mode full`; first live run uses `--dry-run`.

- [x] Add cron entries with the existing shared runner/flock, bounded runtime, log paths under `/data/logs/linux/price_sync_monitor`, and a shared lock under `/data/locks`.
- [x] Document backup, copy, and two-stage overlay rebuild steps for only `automatizaciones-scheduler`; no other services restart.
- [x] Deploy the script without cron entries and rerun the canary in production dry-run. After tightening sync-log health, the real log's caught `Connection already opened` warning is accepted only alongside completed bonifications, 10,369 updated rows, zero errors, and `exit_code=0`. The final canary checked 44 base fields and 30 final price cases, prepared 2 notifications, sent 0, and remained incomplete for one article missing from ERP Stock.
- [x] Verify the nightly full run completes its available coverage within budget; it checks all article base fields and valid source-backed customer prices, and reports missing ERP source rows as incomplete.
- [x] After reviewing the 789 missing ERP Stock rows, add the cron entries and rebuild only the scheduler; confirm startup, schedule, and per-case deduplication. Real WhatsApp delivery remains untriggered until an actual scheduled discrepancy run.

## Plan review notes

- The existing updater is confirmed to write the four pbl fields into Revendedores. Production cron currently runs hourly; the new monitor verifies the persisted result and does not add another mass update job.
- The initial production canary dry-run checked 44 base fields and 30 customer price cases, preparing three notices; one was a false positive from the caught `Connection already opened` log block. The final canary after fixing health parsing prepared two notices for the missing ERP Stock article/incomplete check and sent none.
- A full dry-run reached 47,216 base fields and 315,650 final price cases in 30m29s, then safely stopped when the hourly updater acquired its lock. After adding per-process ORM lookup caching and Decimal normalization for the ERP's zero-freight float, a fresh full run checked 47,216 base fields and 704,960 valid final-price cases in approximately 3 minutes. It reported 789 Revendedores articles absent from ERP Stock and no other price differences; no WhatsApp was sent.
- The existing price comparator is insufficient: it checks only `precio1`/`precio4`, has no WhatsApp sender, and is not scheduled.
- The VFP reference's `Reparto` returns float `0.00` for products without a freight type; `PrecioPublico` then multiplies it by Decimal VAT. The monitor normalizes this result to `Decimal`, with a regression test reproducing the TypeError.
- Grouped WhatsApp notifications track each underlying case separately. Canary rotation preserves cases outside its sample; the authoritative full audit clears resolved cases. This prevents the rotating sample from re-notifying an unchanged discrepancy.
- The scheduler image `local/automatizaciones:price-monitor-live-20261102-183904` is running healthy with both cron entries. Backup is at `/srv/fasa-data/backups/automatizaciones/price-sync-monitor-20261102-183904`; only `automatizaciones-scheduler` was recreated. The post-deploy canary dry-run verified 44 base fields and 30 price cases, found 8 missing Stock rows in its selected sample, and sent no real WhatsApp. The first real scheduled canary has not run yet.
- The VFP reference is mounted from `/var/www/html/utiles/libs/Facturacion.py`. The WhatsApp helper/configuration are mounted as `/data/jobs/resumen_dashboard_whatsapp.py` and `/data/env/alertas-whatsapp.env`; the monitor imports those paths without adding credentials to the image.
