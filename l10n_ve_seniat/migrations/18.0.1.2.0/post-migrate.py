import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

LEGACY_ALIQUOT_FIELDS = [
    ("exent_aliquot_sale", "exent_aliquot_purchase", "exempt", True, 10),
    ("general_aliquot_sale", "general_aliquot_purchase", "general", False, 20),
    ("reduced_aliquot_sale", "reduced_aliquot_purchase", "reduced", False, 30),
    ("extend_aliquot_sale", "extend_aliquot_purchase", "extend", False, 40),
]

RATE_INFERENCE = {
    0.0: ("exempt", True),
    16.0: ("general", False),
    8.0: ("reduced", False),
    31.0: ("extend", False),
}


def _legacy_columns_exist(cr):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'exent_aliquot_sale'
        """
    )
    return bool(cr.fetchone())


def _get_legacy_tax_group_id(cr, company_id, sale_field, purchase_field):
    cr.execute(
        f"""
        SELECT sale_tax.tax_group_id, purchase_tax.tax_group_id
        FROM res_company company
        LEFT JOIN account_tax sale_tax ON sale_tax.id = company.{sale_field}
        LEFT JOIN account_tax purchase_tax ON purchase_tax.id = company.{purchase_field}
        WHERE company.id = %s
        """,
        (company_id,),
    )
    row = cr.fetchone()
    if not row:
        return False
    return row[0] or row[1]


def _infer_group_config(env, tax_group):
    taxes = env["account.tax"].search(
        [
            ("tax_group_id", "=", tax_group.id),
            ("amount_type", "=", "percent"),
        ],
        limit=1,
    )
    if not taxes:
        return False
    return RATE_INFERENCE.get(float(taxes.amount))


def _configure_tax_group(tax_group, aliquot_type, exclude, sequence):
    values = {"sequence": sequence}
    if exclude:
        values.update(
            {
                "l10n_ve_exclude_from_reports": True,
                "l10n_ve_aliquot_type": False,
            }
        )
    else:
        values.update(
            {
                "l10n_ve_exclude_from_reports": False,
                "l10n_ve_aliquot_type": aliquot_type,
            }
        )
    if (
        tax_group.l10n_ve_exclude_from_reports == values["l10n_ve_exclude_from_reports"]
        and tax_group.l10n_ve_aliquot_type == values["l10n_ve_aliquot_type"]
        and tax_group.sequence == sequence
    ):
        return
    tax_group.write(values)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ve_country = env.ref("base.ve", raise_if_not_found=False)
    if not ve_country:
        return

    companies = env["res.company"].search(
        [("account_fiscal_country_id", "=", ve_country.id)]
    )
    legacy_exists = _legacy_columns_exist(cr)
    TaxGroup = env["account.tax.group"]

    for company in companies:
        configured_group_ids = set()
        if legacy_exists:
            for (
                sale_field,
                purchase_field,
                aliquot_type,
                exclude,
                sequence,
            ) in LEGACY_ALIQUOT_FIELDS:
                tax_group_id = _get_legacy_tax_group_id(
                    cr, company.id, sale_field, purchase_field
                )
                if not tax_group_id:
                    continue
                tax_group = TaxGroup.browse(tax_group_id)
                if not tax_group.exists():
                    continue
                _configure_tax_group(tax_group, aliquot_type, exclude, sequence)
                configured_group_ids.add(tax_group.id)

        ve_groups = TaxGroup.search(
            [
                ("company_id", "=", company.id),
                ("country_id", "=", ve_country.id),
            ]
        )
        for tax_group in ve_groups:
            if tax_group.id in configured_group_ids:
                continue
            if tax_group.l10n_ve_aliquot_type or tax_group.l10n_ve_exclude_from_reports:
                continue
            inferred = _infer_group_config(env, tax_group)
            if not inferred:
                continue
            aliquot_type, exclude = inferred
            default_sequence = next(
                seq
                for _sale, _purchase, atype, exc, seq in LEGACY_ALIQUOT_FIELDS
                if atype == aliquot_type and exc == exclude
            )
            _configure_tax_group(
                tax_group, aliquot_type, exclude, tax_group.sequence or default_sequence
            )

    moves = env["account.move"].search(
        [
            ("company_id.account_fiscal_country_id", "=", ve_country.id),
            (
                "move_type",
                "in",
                ["out_invoice", "out_refund", "in_invoice", "in_refund"],
            ),
        ]
    )
    if moves:
        moves._recompute_recordset(["sale_tax_data", "purchase_tax_data"])
        _logger.info(
            "Recomputed sale/purchase tax data for %s Venezuelan moves",
            len(moves),
        )
