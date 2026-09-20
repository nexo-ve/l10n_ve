Bridge module between the generic accounting reports engine (`l10n_ve_reports`) and the Venezuelan localization (`l10n_ve_seniat`, `l10n_ve_withholding`).

It contains the SENIAT fiscal-book reports (sales book, purchases book, fiscal-machine sales book, report X) and their menus, which previously lived inside `l10n_ve_reports` and forced a hard dependency on the Venezuelan localization for every installation.

`l10n_ve_reports_seniat` auto-installs as soon as `l10n_ve_reports`, `l10n_ve_seniat` and `l10n_ve_withholding` are all present in the database, so existing Venezuelan installations keep the exact same reports and menus with no manual step required.
