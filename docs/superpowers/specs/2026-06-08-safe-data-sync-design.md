# Safe Data Sync Design

## Scope

This change adds `DOMINGO ORUE` as a monitored project and hardens the existing Evolta synchronization. Authentication is explicitly deferred to a separate design covering Firebase Authentication with Microsoft as the identity provider.

## Data Contract

Every published dataset consists of these four reports from the same requested period:

- `reporteProspectos`: leads, digital leads, DNI coverage and contacted prospects.
- `ReporteVisitas`: unique showroom visits.
- `Separacion`: apartment reservations.
- `ReporteVenta`: apartment sales.

A synchronization is successful only when all four files exist, can be opened, contain data, include their required columns and have primary event dates inside the requested period.

## Synchronization Flow

1. Create an isolated staging directory inside the configured download directory.
2. Download all four reports into staging using report-specific project selector strategies.
3. Validate the complete staged dataset.
4. Calculate a manifest containing period, row counts, file sizes and current goals.
5. Back up the current published reports and local goal file.
6. Replace the published report set only after all validation succeeds.
7. Reload processor data and mark the synchronization complete.
8. On any failure, keep the prior published set unchanged and expose the validation error in sync status.

## Report Selectors

Each Evolta page receives its own selector configuration. The scraper searches known IDs/names and selects an option by explicit text/value candidates such as `--Todo--`, `Todos`, `0`, `-1` or an empty value. It verifies the selected state after the change event. It must not silently preserve a default project selection.

## Time And Period

Backend dates use `America/Lima`. When no range is supplied, the period is the first day of the current month through yesterday, matching the written operating procedure. Explicit ranges remain supported.

## Goals And Backup

Goals are not changed by report synchronization. Before publication, local goals are copied into the timestamped backup and their current values are included in the manifest. Period-scoped goal history remains a future migration because production may currently use Supabase without a known schema migration path.

## Frontend Contract

`VITE_API_URL` is the backend origin without `/api`. A single API client appends `/api` and is used by all requests. The UI includes `DOMINGO ORUE` in goals, dashboard metrics, indicators, global totals and PDF output.

## Excluded

- Firebase/Microsoft authentication and authorization.
- Supabase schema migration for monthly goal history.
- Deleting the existing `.tmp.driveupload` repository artifacts.

