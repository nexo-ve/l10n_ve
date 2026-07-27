export function formatWebSerialError(err) {
    if (!err) {
        return "Error desconocido.";
    }
    const name = err.name || "";
    const msg = (err.message && String(err.message).trim()) || "";
    const base = msg || String(err);
    if (name === "AbortError") {
        return "Selección de puerto cancelada.";
    }
    if (name === "NotAllowedError") {
        return "Permiso denegado para acceder al puerto serie.";
    }
    if (name === "NotFoundError") {
        return `Dispositivo no encontrado: ${base}`;
    }
    if (name === "SecurityError") {
        return `Web Serial bloqueado: use HTTPS y un origen permitido. ${base}`;
    }
    if (name === "InvalidStateError") {
        return `Puerto en estado inválido (puede estar abierto en otra pestaña). ${base}`;
    }
    if (/setSignals|control signals/i.test(base)) {
        return (
            "El adaptador USB no permite controlar las señales DTR/RTS; " +
            "se continuará sin ellas. Si falla la comunicación, cierre otras pestañas " +
            "que usen el puerto y vuelva a intentar."
        );
    }
    if (name === "NetworkError") {
        return `Error de comunicación en el puerto serie: ${base}`;
    }
    return base || name || "Error desconocido.";
}

export function formatWebSerialPortLabel(portInfo = {}) {
    const parts = [];
    if (portInfo.usbVendorId) {
        parts.push(`USB:${portInfo.usbVendorId.toString(16).padStart(4, "0")}`);
    }
    if (portInfo.usbProductId) {
        parts.push(portInfo.usbProductId.toString(16).padStart(4, "0"));
    }
    if (portInfo.usbSerialNumber) {
        parts.push(portInfo.usbSerialNumber);
    }
    if (parts.length) {
        return parts.join("-");
    }
    return "Web Serial";
}

export function readWebSerialPortInfo(port) {
    if (!port?.getInfo) {
        return {
            usbVendorId: null,
            usbProductId: null,
            usbSerialNumber: null,
            label: "Web Serial",
        };
    }
    const info = port.getInfo();
    const portInfo = {
        usbVendorId: info.usbVendorId ?? null,
        usbProductId: info.usbProductId ?? null,
        usbSerialNumber: info.usbSerialNumber ?? null,
    };
    return {
        ...portInfo,
        label: formatWebSerialPortLabel(portInfo),
    };
}

function mergeUint8Arrays(chunks) {
    let n = 0;
    for (const c of chunks) {
        n += c.length;
    }
    const out = new Uint8Array(n);
    let o = 0;
    for (const c of chunks) {
        out.set(c, o);
        o += c.length;
    }
    return out;
}

export class TfhkaWebSerialTransport {
    constructor() {
        this.port = null;
    }

    static isSupported() {
        return typeof navigator !== "undefined" && "serial" in navigator;
    }

    async requestPort(filters = []) {
        if (!TfhkaWebSerialTransport.isSupported()) {
            throw new Error("Web Serial API no disponible en este navegador.");
        }
        return navigator.serial.requestPort({ filters });
    }

    async open(serialPort, options = {}) {
        const openOptions = {
            baudRate: options.baudRate ?? 9600,
            dataBits: options.dataBits ?? 8,
            stopBits: options.stopBits ?? 1,
            parity: options.parity ?? "even",
            bufferSize: options.bufferSize ?? 512,
            flowControl: options.flowControl ?? "none",
        };
        if (this.port && this.port !== serialPort) {
            await this.close();
        }
        if (this.port === serialPort && this.isOpen()) {
            return;
        }
        try {
            await serialPort.open(openOptions);
        } catch (err) {
            if (err?.name === "InvalidStateError") {
                try {
                    await serialPort.close();
                } catch {
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
                await serialPort.open(openOptions);
            } else {
                throw err;
            }
        }
        this.port = serialPort;
    }

    async close() {
        if (!this.port) {
            return;
        }
        const port = this.port;
        this.port = null;
        try {
            await port.close();
        } catch {
        }
        await new Promise((resolve) => setTimeout(resolve, 50));
    }

    isOpen() {
        return !!(this.port && this.port.readable && this.port.writable);
    }

    async writeBytes(bytes, options = {}) {
        if (!this.isOpen()) {
            throw new Error("Puerto serie cerrado.");
        }
        const postMs = options.postWriteDelayMs ?? 35;
        const writer = this.port.writable.getWriter();
        try {
            await writer.write(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes));
        } finally {
            writer.releaseLock();
        }
        await new Promise((r) => setTimeout(r, postMs));
    }

    async drainInput(maxTotalMs = 200) {
        if (!this.isOpen()) {
            return;
        }
        const deadline = Date.now() + maxTotalMs;
        while (Date.now() < deadline) {
            const chunk = await this.readSome({
                byteTimeout: 12,
                totalTimeout: 45,
                maxLen: 512,
            });
            if (chunk.length === 0) {
                break;
            }
        }
    }

    async readSome(options = {}) {
        if (!this.isOpen()) {
            return new Uint8Array(0);
        }
        const byteTimeout = options.byteTimeout ?? 20;
        const totalTimeout = options.totalTimeout ?? 1000;
        const maxLen = options.maxLen ?? 512;
        const reader = this.port.readable.getReader();
        const chunks = [];
        let total = 0;
        const start = Date.now();
        let lastData = Date.now();
        try {
            while (Date.now() - start < totalTimeout && total < maxLen) {
                const wait = Math.min(
                    byteTimeout,
                    Math.max(1, start + totalTimeout - Date.now())
                );
                const result = await Promise.race([
                    reader.read(),
                    new Promise((resolve) =>
                        setTimeout(() => resolve({ timeout: true }), wait)
                    ),
                ]);
                if (result && result.timeout) {
                    if (total > 0 && Date.now() - lastData >= byteTimeout) {
                        break;
                    }
                    continue;
                }
                const { value, done } = result;
                if (done) {
                    break;
                }
                if (value && value.length) {
                    chunks.push(value);
                    total += value.length;
                    lastData = Date.now();
                } else if (total > 0 && Date.now() - lastData >= byteTimeout) {
                    break;
                }
            }
        } finally {
            reader.releaseLock();
        }
        return mergeUint8Arrays(chunks);
    }

    async readOneByte(timeoutMs) {
        if (!this.isOpen()) {
            return null;
        }
        const reader = this.port.readable.getReader();
        try {
            const readPromise = reader.read();
            const result = await Promise.race([
                readPromise,
                new Promise((resolve) =>
                    setTimeout(() => resolve({ timeout: true }), timeoutMs)
                ),
            ]);
            if (result && result.timeout) {
                try {
                    await reader.cancel();
                } catch {
                }
                try {
                    await readPromise;
                } catch {
                }
                return null;
            }
            const { value } = result;
            if (value && value.length) {
                return value[0];
            }
            return null;
        } finally {
            reader.releaseLock();
        }
    }

    async setSignals(signals) {
        if (!this.port || typeof this.port.setSignals !== "function") {
            return false;
        }
        try {
            await this.port.setSignals(signals);
            return true;
        } catch (err) {
            console.warn(
                "[l10n_ve_fiscal_serial] setSignals omitido:",
                formatWebSerialError(err)
            );
            return false;
        }
    }
}
