import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref(
        "l10n_ve_fiscal_serial.menu_seniat_fiscal_machines",
        raise_if_not_found=False,
    )
    if menu and menu.action:
        _logger.info(
            "Clearing stale action %s from menu Máquinas Fiscales",
            menu.action,
        )
        menu.action = False
