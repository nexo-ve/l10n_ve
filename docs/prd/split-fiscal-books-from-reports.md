# PRD: Split the Venezuelan fiscal books out of `l10n_ve_reports`

- Status: Draft
- Date: 2026-09-19
- Repo: `nexo-ve/l10n_ve` (branch 19.0), consumed by `bar251` and the other nexodev deployments through the `addons/l10n_ve` submodule
- Related memory (Engram, project `bar251`): `l10n_ve/reports-non-ve-intrusiveness`, `l10n_ve/reports-display-currency`, `l10n_ve/reports-split-analysis`

## 1. Problem

`l10n_ve_reports` is a fork of Odoo Enterprise `account_reports` (models suffixed `.oca`) with a custom display-currency filter and the Venezuelan fiscal books. Its manifest depends on `l10n_ve_seniat` and `l10n_ve_withholding`.

A client that does not need the Venezuelan localization cannot install the reports without also installing both localization modules. That install:

- Forces two modules flagged `countries: ["ve"]` (hidden in Apps, need CLI/dev mode).
- Applies unguarded behavior changes to every company: `res.currency.rate.write()` blocks editing rates not dated today and caps edits at 2; `account.move` constraint forbids due date before invoice date; every new `res.partner` receives Venezuelan `type_person_id` / `withholding_type_id` defaults.
- Adds a hard `pandas` Python dependency used only by one withholding wizard.
- Adds Venezuelan seed data, SENIAT menus, dozens of hidden VE fields on invoice, partner and company forms, and a 🇻🇪 emoji prefix on every generic report menu label.

The coupling is very narrow. The 10.5k-line engine, all wizards, controllers, views, security, OWL components and every generic report have zero references to the two dependencies (verified 2026-09-19).

## 2. Goals

1. `l10n_ve_reports` becomes installable with only `account` and `web`, keeping 100% of the current generic reports and the display-currency filter.
2. A new bridge module `l10n_ve_reports_seniat` adds the Venezuelan fiscal books on top of `l10n_ve_reports`, `l10n_ve_seniat` and `l10n_ve_withholding`.
3. Existing Venezuelan databases upgrade in place without losing reports, menus, actions, cron, translations or user customizations.
4. No behavior change for Venezuelan clients.

## 3. Naming decision

- The generic engine keeps the name `l10n_ve_reports`. Reason: the generic records (reports, actions, menus, cron, views) keep their module owner in `ir_model_data`, so the upgrade path needs no mass rename. External consumers that reference generic xml_ids keep working unchanged.
- The bridge module is `l10n_ve_reports_seniat`, following the Odoo bridge-module convention already used in this repo by `l10n_ve_reports_stock`.
- Accepted tradeoff: the `l10n_ve_` prefix on a generic module is misleading for non-Venezuelan clients. The manifest `summary` and `description` must state clearly that the module has no localization dependency.

## 4. Non-goals

- Fixing the unguarded country rules in `l10n_ve_seniat` / `l10n_ve_withholding` (tracked separately; see memory `l10n_ve/reports-non-ve-intrusiveness`).
- Renaming the `.oca` model suffix or reconciling with OCA `account_financial_report`.
- Renaming `l10n_ve_reports` itself.
- Touching `l10n_ve_reports_stock` beyond verifying it still installs.

## 5. Users and scenarios

- Non-Venezuelan client: installs `l10n_ve_reports`, gets balance sheet, P&L, cash flow, general ledger, trial balance, aged partner balance, partner ledger, journal report, tax report, bank reconciliation, follow-up, customer statement, executive summary, analytic and budget reports, plus diary, bank and cash books, all viewable in any active currency with the three rate-date modes.
- Venezuelan client (existing): upgrades, `l10n_ve_reports_seniat` is auto-installed, and sees exactly the same menus and reports as today, including sales book, purchases book, fiscal machine sales book, report X and daily payments with process date and retention journals.
- Developer maintaining `l10n_ve_seniat`: updates the one reference to a menu that moves to the bridge module.

## 6. Current state (verified inventory)

### 6.1 Generic (zero dependency references) — stays in `l10n_ve_reports`

- `models/account_report.py` (engine, display-currency filter at `_init_options_display_currency`, conversion via `res.currency._convert`)
- `models/account_move.py`, `account_move_line.py`, `res_company.py`, `res_partner.py`, `account_tax.py`, `account.py`, `account_fiscal_position.py`, `chart_template.py`, `ir_actions.py`, `account_journal_dashboard.py`, `mail_activity.py`, `mail_activity_type.py`, `res_config_settings.py`
- Report handlers: `balance_sheet.py`, `executive_summary_report.py`, `account_cash_flow_report.py`, `account_general_ledger.py`, `account_trial_balance_report.py`, `account_partner_ledger.py`, `account_aged_partner_balance.py`, `account_journal_report.py`, `account_generic_tax_report.py`, `bank_reconciliation_report.py`, `account_followup_report.py`, `account_customer_statement.py`, `account_sales_report.py`, `account_analytic_report.py`, `budget.py`
- Books that are generic despite the naming: `account_diary_book_report.py`, `account_bank_book_report.py`, `account_cash_book_report.py`, `l10n_ve_liquidity_book_report_mixin.py`
- All of `wizard/`, `controllers/`, `views/`, `security/ir.model.access.csv`, `static/src/**`, `static/tests/**`
- Data: `account_report_actions.xml`, `aged_partner_balance.xml`, `balance_sheet.xml`, `bank_book_report.xml`, `bank_reconciliation_report.xml`, `cash_book_report.xml`, `cash_flow_report.xml`, `customer_statement.xml`, `diary_book_report.xml`, `executive_summary.xml`, `followup_report.xml`, `general_ledger.xml`, `generic_tax_report.xml`, `journal_report.xml`, `mail_activity_type_data.xml`, `mail_templates.xml`, `menuitems.xml`, `partner_ledger.xml`, `pdf_export_templates.xml`, `profit_and_loss.xml`, `report_send_cron.xml`, `sales_report.xml`, `trial_balance.xml`
- Tests: the ~30 generic test files under `tests/`

### 6.2 Venezuela-bound — moves to `l10n_ve_reports_seniat`

- `models/l10n_ve_book_report_mixin.py` (built on `account.tax.group._l10n_ve_*` API and `company.l10n_ve_on_behalf_of_third_party_enabled`)
- `models/account_sales_book_report.py`, `account_purchase_book_report.py`, `account_sales_book_fiscal_machine_report.py`, `account_report_x.py`
- Data: `sales_book_report.xml`, `purchases_book_report.xml`, `sales_book_fiscal_machine_report.xml`, `report_x.xml`, `seniat_reports_menuitems.xml` (9 references to `l10n_ve_seniat.menu_seniat_reports`)

### 6.3 Mixed — needs a split

- `models/account_daily_payments_report.py` and `data/daily_payments_report.xml`. Generic: bank/cash journal filtering, week helpers, report-currency conversion. VE-only: `l10n_ve_process_date` on move/payment (around lines 128-132) and the company retention journal fields (around lines 476-481).

### 6.4 External consumers of `l10n_ve_reports.*` xml_ids

| Consumer | References | Impact |
|---|---|---|
| `l10n_ve_reports_stock` | manifest dependency; `static/src/components/inventory_book_report/filters.xml` | Generic templates, no change expected. Verify. |
| `private-addons/pr_payments` | `static/src/components/daily_payments_report/filters/*.xml` | Generic daily payments templates, no change expected. Verify. |
| `private-addons/pskloud_migration` | `data/daily_payments_report_column.xml` | Generic report column, no change expected. Verify. |
| `l10n_ve_seniat/models/ir_ui_menu.py` | `l10n_ve_reports.menu_seniat_report_sales_book_fiscal_machine` | Menu moves to the bridge module. Must change. |
| `l10n_ve_seniat/tests/test_l10n_ve_book_report_columns.py`, `tests/test_ir_ui_menu.py` | book report xml_ids | Move or adapt tests. |

## 7. Proposed solution

### 7.1 Module layout

| Module | Depends | Contents |
|---|---|---|
| `l10n_ve_reports` | `account`, `web` | Everything in 6.1 plus the generic half of 6.3. Manifest summary updated to state no localization dependency. |
| `l10n_ve_reports_seniat` | `l10n_ve_reports`, `l10n_ve_seniat`, `l10n_ve_withholding` | Everything in 6.2 plus the VE half of 6.3. `auto_install: True` so existing Venezuelan databases pick it up on upgrade. |

`l10n_ve_reports` bumps to `19.0.2.0.0` so its migration script runs.

### 7.2 Daily payments split

- `l10n_ve_reports` keeps the `account.daily.payments.report.handler.oca` class with journal filtering and currency conversion. The "date to use" helper becomes an overridable method returning the payment/move date.
- `l10n_ve_reports_seniat` adds an `_inherit` on that handler that overrides the date helper to prefer `l10n_ve_process_date` and adds the retention journal grouping.
- The report record, its columns and options referenced by `pr_payments` and `pskloud_migration` stay in `l10n_ve_reports` with their xml_ids.

### 7.3 Menus

- `menuitems.xml` (parents are native `account.*` menus) stays in `l10n_ve_reports`. Labels lose the 🇻🇪 prefix.
- `seniat_reports_menuitems.xml` moves to `l10n_ve_reports_seniat`. Where it re-parents generic reports (diary, bank, cash books) under the SENIAT menu, it does so via `record` overrides of the `l10n_ve_reports` menus, so Venezuelan users see no change.
- `l10n_ve_seniat/models/ir_ui_menu.py`: today it references a menu owned by a module that depends on `l10n_ve_seniat`, which is a reverse dependency. Move that logic into `l10n_ve_reports_seniat` (an `_inherit` of `ir.ui.menu` there) and delete it from `l10n_ve_seniat`. If it must stay, use `raise_if_not_found=False`.

### 7.4 Upgrade path for existing databases

- Only the records listed in 6.2 change owner. `pre-migrate.py` in `l10n_ve_reports` 19.0.2.0.0 runs `UPDATE ir_model_data SET module = 'l10n_ve_reports_seniat' WHERE module = 'l10n_ve_reports' AND name IN (<explicit list generated from the moved data files>)`. Prefer `openupgradelib.rename_xmlids` if available in the deploy image.
- Add `l10n_ve_reports_seniat` to `ir_module_module` as `to install` in the same pre-migration when `l10n_ve_seniat` is installed, or rely on `auto_install`. Verify with `click-odoo-update`, noting the known post_deploy script issue in memory `nexodev-post-deploy-script-broken`.
- Translations: the `es_VE.po` entries whose source belongs to moved files go to `l10n_ve_reports_seniat/i18n/`; the rest stays.

### 7.5 Currency conversion hardening (small, in scope)

In the engine, replace the silent `except Exception` around `source_currency._convert` with: log a warning with report, line and date, and surface a report-level warning ("Some amounts could not be converted to <currency> for <date>") instead of mixing currencies silently.

## 8. Functional requirements

1. Installing `l10n_ve_reports` on a fresh database with only `account` and `web` succeeds and shows all generic reports under Accounting > Reporting.
2. Every generic report supports the display-currency filter with rate-date modes current, document and manual, converting company-currency amounts with `res.currency._convert`.
3. Installing `l10n_ve_reports_seniat` on top adds sales book, purchases book, fiscal machine sales book, report X and the SENIAT menu tree, identical to today.
4. Daily payments report behaves identically for Venezuelan companies (process date, retention journals) and works for non-Venezuelan companies without those concepts.
5. Upgrading an existing Venezuelan database keeps all `account.report` records, menus, actions, the `ir_cron_account_report_send` cron, annotations and user-created report variants with their original database ids, and ends with `l10n_ve_reports_seniat` installed.
6. `l10n_ve_reports_stock`, `pr_payments`, `pskloud_migration` and `l10n_ve_seniat` install and pass their tests after the split.
7. No `l10n_ve_reports` menu label contains the 🇻🇪 emoji.
8. `l10n_ve_seniat` no longer references any `l10n_ve_reports*` xml_id.

## 9. Acceptance criteria and verification

- Fresh install matrix, run in the test container:
  - `account`, `web`, `l10n_ve_reports` only.
  - Same plus `l10n_ve_seniat`, `l10n_ve_withholding`, `l10n_ve_reports_seniat`, `l10n_ve_reports_stock`.
- Full test suite of both modules green; the ~30 generic tests run in the generic-only database.
- Upgrade test: snapshot of a Venezuelan database (or the demo database with `l10n_ve_reports` 19.0.1.0.0 installed), upgrade to 19.0.2.0.0, then assert via SQL that no `ir_model_data` row for the moved records was recreated (ids unchanged), that `account.report` count is unchanged, and that `l10n_ve_reports_seniat` is installed.
- Manual check: open balance sheet in USD with manual date in both databases.
- `grep -r "l10n_ve_reports\."` across `bar251/addons` returns only references to records that still live in `l10n_ve_reports`, plus `l10n_ve_reports_seniat.*` references inside the bridge module.

## 10. Risks

- Moving the fiscal-book records without a migration causes Odoo to recreate them and orphan customizations. Mitigated by 7.4 and the upgrade test. Scope is small: four report definitions and the SENIAT menu tree.
- The daily payments split is the only place where generic and VE logic share a class. Mitigated by keeping the current tests and adding one per company type.
- Hidden test dependencies on Venezuelan fixtures in `tests/common.py`. Detected by the generic-only install matrix.
- `auto_install` on the bridge module must not pull it into databases that install `l10n_ve_seniat` without wanting reports. Acceptable: today those databases already get the reports because `l10n_ve_seniat` clients always install `l10n_ve_reports`. Confirm with the team.
- Five nexodev deployments share the submodule (memory `nexodev-private-addons-submodule-fanout`). Bump the submodule in each only after the upgrade test passes, and exclude `leblanc` per the existing rule.

## 11. Decisions

1. `auto_install: True` on `l10n_ve_reports_seniat`. Decided 2026-09-19. It is the mechanism Odoo uses for bridge modules and removes a manual step in five deployments.
2. Keep the `.oca` suffix on the 31 report handler models (for example `account.balance.sheet.report.handler.oca`). Decided 2026-09-19. The suffix exists only to avoid `_name` collisions with Enterprise `account_reports`; it does not mean the code comes from OCA. Renaming is out of scope because model names are stored in `ir_model`, `ir_model_data` and in `account.report.custom_handler_model_name`, so it would need its own migration.

No open decisions remain. The PRD is ready for the SDD spec and design phases.

## 12. Effort and delivery

Estimated 16-24 hours. Suggested slices, each a reviewable PR:

1. Create `l10n_ve_reports_seniat`, move the 6.2 files, trim `l10n_ve_reports` manifest to `account` and `web`, remove the 🇻🇪 prefix from generic labels. Install matrix green.
2. Daily payments split, `ir.ui.menu` logic moved out of `l10n_ve_seniat`, test relocation.
3. Migration script, i18n split, upgrade test, conversion warning hardening.
4. Submodule bumps across deployments.

Changed lines will exceed 400 in slice 1 because of file moves, so plan chained PRs from the start and ask reviewers to review moves with rename detection.
