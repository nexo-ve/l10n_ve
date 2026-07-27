/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { createFiscalSerialAuditLogger } from "./fiscal_serial_audit";

const REPORT_LABELS = {
    report_x: _t("Reporte X"),
    report_z: _t("Reporte Z"),
};

export async function l10nVeFiscalSerialExecuteReport({
    env,
    action,
    logTag = "[l10n_ve_fiscal_serial]",
}) {
    const fiscalSerial = env.services.l10n_ve_fiscal_serial;
    const notification = env.services.notification;
    const ui = env.services.ui;
    const progressLabel = REPORT_LABELS[action] || _t("Imprimiendo reporte fiscal");

    if (!fiscalSerial) {
        notification.add(
            _t("El servicio de máquina fiscal no está disponible."),
            { type: "danger" }
        );
        return false;
    }
    if (!fiscalSerial.isSupported()) {
        notification.add(
            _t(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS para imprimir desde el navegador."
            ),
            { type: "danger" }
        );
        return false;
    }

    notification.add(
        _t("Seleccione la máquina fiscal en el cuadro de puertos del navegador."),
        { type: "warning" }
    );

    let driver;
    let auditLogger;
    let hadError = false;
    let errorDetail = "";
    let blocked = false;
    const setProgress = (percent, message) => {
        const pct = Math.max(0, Math.min(100, Math.round(percent)));
        if (blocked) {
            ui.unblock();
            blocked = false;
        }
        ui.block({ message: `${message || progressLabel} ${pct}%` });
        blocked = true;
    };

    try {
        setProgress(0, progressLabel);
        auditLogger = createFiscalSerialAuditLogger(env.services.orm, {
            source: "report",
        });
        driver = fiscalSerial.createTfhkaFiscal();
        auditLogger.attachDriver(driver);
        const opened = await driver.openFpCtrl({ baudRate: 9600, parity: "even" });
        if (!opened) {
            throw new Error(driver.estado || _t("No fue posible abrir el puerto serial."));
        }
        setProgress(50, progressLabel);
        const machine = fiscalSerial.createTfhkaFiscalMachine(driver);
        const response = await machine.runAction({ action, data: {} });
        if (!response?.valid) {
            throw new Error(response?.message || _t("No se pudo imprimir el reporte fiscal."));
        }
        try {
            await driver.closeFpCtrl({ reason: "success" });
        } catch {
        }
        driver = null;
        setProgress(100, progressLabel);
        notification.add(response.message || `${progressLabel} ${_t("completado.")}`, {
            type: "success",
        });
        return true;
    } catch (error) {
        hadError = true;
        const msg =
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            String(error || _t("Error al imprimir el reporte fiscal."));
        errorDetail = msg;
        console.error(`${logTag} Error reporte fiscal:`, error);
        notification.add(msg, { type: "danger" });
        return false;
    } finally {
        if (driver) {
            try {
                await driver.closeFpCtrl({
                    reason: hadError ? "error" : "finally_cleanup",
                    detail: errorDetail,
                });
            } catch {
            }
        } else if (auditLogger) {
            await auditLogger.flush();
        }
        if (blocked) {
            ui.unblock();
        }
    }
}
