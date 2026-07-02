# Layer 17 Calendar Reminders

Batch 17A supports downloadable ICS reminder files.

## Supported Reminder Types

- `application_window`
- `internship_deadline`
- `follow_up`
- `market_refresh_alert`
- `institutional_report_review`
- `data_request_due`

## ICS Export Behavior

Reminder creation stores a user-owned reminder record and generates an ICS file. The ICS description includes product-object provenance:

- product object type and id
- product object label
- freshness status
- confidence label
- Job Market Intelligence boundary notice

The ICS endpoint returns `text/calendar` with a `Content-Disposition` attachment header.

## ATS Boundary

Reminders are not application records. They do not create:

- application statuses
- resume submission workflows
- LinkedIn, Handshake, university job board, or employer portal automation

Receipt fields mark external writes, live sync, OAuth, and two-way sync as false.

## Deferred Direct Calendar Integrations

Google Calendar and Outlook direct writes are deferred. Batch 17A exposes only ICS files so users can import reminders manually into the calendar tool they choose.
