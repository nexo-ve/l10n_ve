# Venezuela - POS Credit Invoice Currency

Issue POS credit (pay later) invoices in a configurable currency.

## Overview

Venezuelan retailers sell on credit to identified customers at the daily
BCV rate. This module lets a company (and, per POS, an override) define the
currency used to invoice orders paid, in whole or in part, with a "Customer
Account" (`pay_later`) payment method, so the credit invoice is issued in
that currency (typically USD) instead of the POS currency (VES). Payment
that is not on credit is unaffected and keeps posting in the POS currency.

Refunds of an order invoiced in a credit currency reuse that invoice's
currency and rate, so the credit note cancels the original residual
exactly.

See `docs/prd/pos-credit-invoice-currency.md` in the `l10n_ve` repository
for the full requirements.

## Configuration

1. Go to **Point of Sale > Configuration > Settings** and set the
   **Company default** credit invoice currency (empty keeps the current
   behavior: credit invoices in the POS currency).
2. Optionally override it per Point of Sale in the same settings screen.
3. The selected currency must be active and have at least one exchange rate
   defined.

The company default only applies to Point of Sale configs **created after**
it is set: each `pos.config` reads it once, as its field default, at
creation time. Existing POS configs keep their own value and are not
updated retroactively when the company default changes.

## Non-goals

This module does not persist a POS display currency, does not add exchange
difference documents, and does not implement due-collection inside the POS
(collection happens in Accounting, as usual for pay-later payments in
Community).
