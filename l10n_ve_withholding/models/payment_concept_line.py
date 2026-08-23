from odoo import _, api, fields, models


class PaymentConceptLine(models.Model):
    _name = "payment.concept.line"
    _description = "Payment Concept Line"

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        "The concept code already exists",
    )

    pay_from = fields.Float(
        string="Payments greater than:", compute="_compute_pay_from", store=True
    )

    type_person_id = fields.Many2one(
        "type.person",
        string="Type person",
        store=True,
        required=True,
        domain=[("state", "=", True)],
    )
    payment_concept_id = fields.Many2one(
        "payment.concept",
        string="Associated Payment Concept",
        required=True,
        domain=[("status", "=", True)],
        ondelete="cascade",
    )
    percentage_tax_base = fields.Float(string="Percentage Taxable Base")
    tariff_id = fields.Many2one(
        "fees.retention", string="Tariff", domain=[("status", "=", True)]
    )
    code = fields.Char(string="Concept code", required=True)

    @api.onchange("percentage_tax_base")
    def check_value_percentage(self):
        if self.percentage_tax_base > 100:
            return {
                "warning": {
                    "title": _("Error in taxable base percentage field"),
                    "message": _(
                        "the percentage may not exceed 100% on the payment concept line"
                    ),
                },
                "value": {"percentage_tax_base": 0},
            }

    @api.depends("tariff_id.tax_unit_id.value", "tariff_id.amount_subtract")
    def _compute_pay_from(self):
        for record in self:
            if record.tariff_id.amount_subtract:
                record.pay_from = (record.tariff_id.tax_unit_id.value * 1000) / 12
            else:
                record.pay_from = 0
