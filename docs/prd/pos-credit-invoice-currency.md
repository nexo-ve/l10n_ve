# PRD: POS credit invoices in a configurable currency

- Status: Draft v1 (2026-09-20)
- Target: Odoo 19 Community, `l10n_ve` addons (branch 19.0)
- Owner: Nexodev / l10n_ve team

## 1. Problem

Venezuelan retailers define prices in USD, sell in VES (company currency) at the daily BCV rate, and sell on credit to identified customers. A credit invoice issued in VES loses value while it is unpaid. The market practice ("facturación indexada") is to issue the credit invoice in USD so that, at payment time, the customer pays the VES equivalent at the rate of the payment date.

Today a POS order invoiced on credit is always generated in the POS currency (VES). There is no way to configure a different currency for credit invoices.

## 2. Verified current state

Findings below were verified in source code (Odoo 19 core at `odoo/addons/point_of_sale` and the `l10n_ve`, `currency` and `private-addons` submodules). They are not runtime-tested yet.

### 2.1 Credit sales already work in Community

- `pos.payment.method.type` is computed: a method without a journal is automatically type `pay_later` ("Customer Account"). Every new POS config ships one by default with `split_transactions=True`. (`pos_payment_method.py:59,115-121`, `pos_config.py:1065-1074`)
- Payments of type `pay_later` never create an accounting payment move (`pos_payment.py:83`). When the order is invoiced, nothing is reconciled against the invoice, so the invoice stays open on the customer's receivable. (`pos_order.py:1198-1232`)
- On session close, `pay_later` payments of invoiced orders are skipped entirely, so no duplicated receivable is created. (`pos_session.py:895-970`)
- What Community lacks is `pos_settle_due` (Enterprise, license OEEL-1): customer due amount inside the POS and the "Settle due" button. Collection happens in Accounting.

Conclusion: no credit-flow implementation is needed. A runtime verification is required because the team reported it failing in Community once (see acceptance criteria AC-8).

### 2.2 Dual-currency display already exists (`currency_pos`)

`currency_pos` provides a per-session "Currency" button that selects a display currency, converted prices on product cards, order lines and the amount due on the payment screen, a rates widget, and dual amounts on receipts for foreign-currency payment lines. The selection is browser-session state and is not persisted. The product owner accepted this as sufficient. Persisting a default display currency per company and per POS is a non-goal of this PRD (see section 4).

### 2.3 What blocks a USD credit invoice

- `pos.order._prepare_invoice_vals` hardcodes `currency_id = order.currency_id` (POS currency) and builds lines from the order line `price_unit`, which is in VES. (`pos_order.py:945`, `_prepare_invoice_lines`)
- Both core and `currency_pos` enforce `invoice_journal_id.currency_id == config.currency_id`. This constrains the journal, not the move: an `account.move` may be in USD on a VES journal. No journal change is needed.
- `account.move.invoice_currency_rate` (Odoo 19 core, stored, writable) carries the rate from company currency to document currency and drives debit/credit in VES. This is the standard Odoo mechanism the feature relies on.
- Product USD prices come from `l10n_ve_product_currency.force_currency_id`; `currency_pos` converts them to VES server-side for POS financial amounts using `res.currency._convert` and the BCV rate table (`currency_rate_update` + `res_currency_rate_provider_BCV`).
- Credit detection: three modules use `type == 'pay_later'`, `l10n_ve_loyalty_pos` uses "method has no journal". Both are equivalent in practice because core restricts the method journal to cash or bank and derives `type` from it (`pos_payment_method.py:34-42,115-121`). No alignment work is needed.

## 3. Goals

- G1. A company-level default currency for POS credit invoices.
- G2. The same setting per POS config, initialized from the company default, not changeable per order.
- G3. When an order is paid fully or partially with a Customer Account method, the invoice is generated in the configured credit currency, with VES debit/credit at the BCV rate of the order date (standard Odoo multi-currency invoice).
- G4. Works with any emission medium already supported (fiscal machine, free-form, digital).

## 4. Non-goals

- Persisting the POS display currency (company or POS level). `currency_pos` behavior stays as is.
- Showing product lines or order totals in a second currency on the receipt.
- Debit notes for exchange differences ("notas de débito por indexación").
- Collecting credit from the POS ("Settle due"). Collection happens in Accounting.
- Changing POS order, session, cash box, or cash report currency. All remain in the POS currency (VES).

## 5. Users and scenarios

- Cashier: sells to an identified customer, selects the Customer Account payment method, validates. Sees nothing new. The invoice comes out in USD.
- Accountant: collects the open USD invoice later by registering a payment in VES at the rate of the payment date. Standard Odoo exchange-difference handling applies.
- Administrator: sets the credit invoice currency once at company level; new POS configs inherit it; can override per POS.

## 6. Functional requirements

### 6.1 Configuration

- FR-1. `res.company` gets a "POS credit invoice currency" field. Empty means "use the POS currency" (behavior identical to today). Exposed in Point of Sale settings.
- FR-2. `pos.config` gets the same field. On creation it defaults to the company value. On module install or upgrade, existing configs without a value are backfilled from the company value.
- FR-3. The field is read-only for cashiers and not exposed in the POS UI. It cannot be changed per order.
- FR-4. Saving a POS config whose credit currency is inactive or has no rate at all raises a validation error.

### 6.2 Credit detection

- FR-5. An order is "on credit" when at least one of its payment lines uses a payment method of type `pay_later`. This is the single canonical rule for new code.

### 6.3 Invoice generation

- FR-6. When the order is on credit and the POS credit currency differs from the POS currency, the generated invoice uses the credit currency. Otherwise generation is unchanged.
- FR-7. The invoice rate is the rate from company currency to credit currency at the order date, taken from the standard rate table (latest rate on or before that date). It is written to `invoice_currency_rate` so debit/credit land in VES.
- FR-8. Invoice line unit prices, discounts and taxes are expressed in the credit currency. For products priced in USD, the USD unit price on the invoice must equal the product's USD price within currency rounding. Pricelist rules and discounts defined in VES are converted with the same rate.
- FR-9. The invoice journal, fiscal series and control numbering are unchanged. The same journal issues VES cash invoices and USD credit invoices.
- FR-10. The invoice must satisfy Odoo's balance check: sum of VES debit/credit equals the POS order total in VES within rounding. Any residual rounding goes to the standard rounding handling, never to a manual adjustment line.

### 6.4 Payments and mixed orders

- FR-11. For a mixed order (part cash or card in VES, part Customer Account), the whole invoice is in the credit currency. Non-credit payments create their payment moves in VES as today and are reconciled against the USD invoice. The residual remains in USD.
- FR-12. IGTF behavior is unaffected: it depends on the payment currency, not on the invoice currency. A USD invoice paid in VES must not trigger IGTF.

### 6.5 Refunds

- FR-13. A POS refund of an order whose invoice was issued in the credit currency produces a credit note in the same currency, at the rate of the original invoice, so that residuals cancel exactly.

### 6.6 Documents

- FR-14. All existing invoice outputs (free-form PDF, ESC/P, fiscal machine, digital/TFHKA) must render a foreign-currency invoice correctly: amounts in USD, VES equivalent and the applied rate where the fiscal format requires it. Existing report templates must be audited (see R-2).

## 7. Business rules and edge cases

- BR-1. If the credit currency equals the POS currency, nothing changes.
- BR-2. Anonymous customer plus Customer Account is already blocked by core when the method has `split_transactions=True`. `l10n_ve_pos` already forces invoicing on every order. Both remain mandatory.
- BR-3. Rates are daily. The BCV provider dates each rate with the BCV value date, and `currency_pos` loads into the POS the latest rate dated on or before today (`currency_pos/models/res_currency_rate.py:9-31`). Frontend and backend therefore agree whenever the session is loaded on the same day as the order. The invoice uses the rate at the order date. A session kept open across a date change without reload is the only divergent case and is accepted.
- BR-4. Group invoicing of several orders in one invoice (session closed, "invoice several orders") must either honor the same rule per order or be blocked for mixed credit/non-credit selections. Default: block with a clear error.
- BR-5. Loyalty eWallet credits from refunds paid on credit (`l10n_ve_loyalty_pos`) keep their current conversion logic; they operate on the POS order, not on the invoice.

## 8. Acceptance criteria

All to be run on a fresh database using the project's own Docker Compose stack (repository root `docker-compose.yaml` plus override, Odoo 19 Community, addons mounted at `/mnt/extra-addons`), company currency VES, USD active with a BCV rate.

- AC-1. Company setting exists, defaults empty, appears in POS settings. New POS config inherits the company value. Upgrade backfills existing configs.
- AC-2. Order for a customer, one product priced 10 USD, paid 100% with Customer Account, config credit currency USD: posted invoice in USD, line price 10.00 USD, `invoice_currency_rate` equals the BCV rate of the day, VES debit/credit equals the POS order total, `payment_state = not_paid`, residual 10.00 USD.
- AC-3. Same order with credit currency empty: invoice in VES, identical to today's behavior.
- AC-4. Mixed order (50% cash VES, 50% Customer Account): invoice in USD, cash payment move in VES reconciled partially, residual equals the credit part in USD, session closes without error and without duplicated receivable lines.
- AC-5. Refund of AC-2 from the POS: credit note in USD at the original rate, original invoice and credit note fully reconciled.
- AC-6. With a USD rate dated today and another dated tomorrow already in the table, sell today: the POS prices and the invoice both use today's rate.
- AC-7. IGTF-enabled company: AC-4 with the cash part in VES produces no IGTF line.
- AC-8. Credit flow baseline in Community without this feature: Customer Account payment plus invoice leaves the invoice open, session closes cleanly. Documents that the earlier "not working" report was configuration, not a missing feature.
- AC-9. Each supported emission medium prints or transmits a USD credit invoice with a VES equivalent and rate where required.
- AC-10. Automated tests: TransactionCase coverage for AC-2 through AC-6 in the implementing module.

## 9. Design constraints and pointers

Not a solution. Items the design phase must respect.

- Extend `pos.order._prepare_invoice_vals` and line preparation. Do not relax the `pos.config` currency constraints.
- Reuse the standard rate table and `res.currency._convert`. Do not introduce a parallel rate source.
- Prefer deriving USD line prices from the product's original USD price (`force_currency_id`) over re-converting VES, when available, to avoid rounding drift. Fall back to conversion at the order rate.
- Placement: `l10n_ve_pos` already owns forced invoicing and the invoice journal picker, and already depends on `l10n_ve_exchange_rates`. Adding a dependency on `currency_pos` or `l10n_ve_product_currency` is a design decision to make explicitly, since `currency_pos` depends on `pos_sale` and `pos_hr`.
- Follow the existing `pos.config` related-field pattern used by `l10n_ve_pos_igtf_percent` for the company default plus per-config override.

## 10. Risks and assumptions

- R-1. Group invoicing and session-close invoicing paths in core may bypass the per-order rule (BR-4).
- R-2 (deferred by product owner, 2026-09-20). Fiscal outputs in `private-addons` (`hka_seniat_invoice`, `hka_pos_seniat_invoice`, ESC/P and free-form reports in `l10n_ve_*`) have not been audited for foreign-currency invoices, and regulatory acceptance per emission medium has not been confirmed. Not blocking for this iteration; revisit before rollout. FR-14 and AC-9 stay as the definition of done for that later step.
- A-1. The company default is empty, so upgrading changes nothing until an administrator sets a currency.
- A-2. When the credit currency has no rate on the order date, the latest previous rate is used (standard Odoo lookup). FR-4 only guards the case of a currency with no rate at all.
