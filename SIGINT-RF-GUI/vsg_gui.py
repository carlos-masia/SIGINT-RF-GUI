"""
Shiny web GUI for the R&S SMW200A ARB catalog.

Depends on the installed package **SIGINT-RF-DEVICE-VSG_SMW200A**, which provides:
  - ``vsg_smw200a``  — CATALOG, play(), generators, VsgSmw200a, config helpers.
  - ``rs_scpi_tcp``  — raw TCP SCPI: Test SMW (*IDN?), FSW tuning.

Run:
    sigint-rf-gui-shiny

Or with live reload:
    python -m shiny run --reload SIGINT-RF-GUI/SIGINT-RF-GUI/vsg_gui.py:app
"""

from __future__ import annotations

import queue
import re
import threading
import traceback
from typing import Any

from shiny import App, reactive, render, ui

__all__ = ("app", "main")


# ---------------------------------------------------------------------------
# ARB module  (vsg_smw200a from installed device package)
# ---------------------------------------------------------------------------

_arb: Any | None = None
_arb_load_error: str | None = None


def _load_arb() -> tuple[Any | None, str | None]:
    global _arb, _arb_load_error
    if _arb is not None:
        return _arb, None
    try:
        import vsg_smw200a as _mod
        _arb = _mod
        _arb_load_error = None
    except Exception as exc:
        _arb_load_error = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return _arb, _arb_load_error


# ---------------------------------------------------------------------------
# Config helpers (vsg_smw200a — installed with the device package)
# ---------------------------------------------------------------------------

def _default_smw_ip_str() -> str:
    return "169.254.2.20"
    # try:
    #     from vsg_smw200a import default_smw_ip
    #     return str(default_smw_ip(None))
    # except Exception:
    #     return "192.168.0.10"


def _default_fsw_ip_str() -> str:
    try:
        import vsg_smw200a
        return vsg_smw200a._fsw_ip_from_vsg_yaml() or ""
    except Exception:
        return ""


def _arb_config_path_str() -> str:
    try:
        from vsg_smw200a import config_file_path
        return str(config_file_path())
    except Exception:
        return "(vsg_config.yaml — not found)"


def _catalog_choices() -> list[str]:
    arb, _ = _load_arb()
    if arb is None:
        return []
    return sorted(arb.CATALOG.keys())


def _sanitize_gp_id(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", name)


# ---------------------------------------------------------------------------
# Log state (shared between Shiny reactive context and background threads)
# ---------------------------------------------------------------------------

_log_buf: list[str] = []
_log_lock = threading.Lock()
_play_running = {"v": False}
_scpi_test_running = {"v": False}
_LOG_THREAD_SCPI_DONE = "__VSG_SCPI_TEST_DONE__"
_log_thread_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
_log_ui_gen: list[int] = [0]
_log_ui_lock = threading.Lock()


def _log_clear() -> None:
    with _log_lock:
        _log_buf.clear()
    while True:
        try:
            _log_thread_queue.get_nowait()
        except queue.Empty:
            break


def _log_append(line: str) -> None:
    with _log_lock:
        _log_buf.append(line.rstrip())
        if len(_log_buf) > 2000:
            del _log_buf[:-1500]


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def app_ui(request: Any | None = None) -> ui.Tag:
    _load_arb()
    choices = _catalog_choices()
    load_err = _arb_load_error

    banner = (
        ui.tags.p(
            ui.tags.strong("Could not load vsg_smw200a. "),
            "Install or reinstall SIGINT-RF-DEVICE-VSG_SMW200A, then reload.",
            class_="text-danger",
        )
        if load_err
        else ui.tags.p(
            "RF only on a conducted/shielded bench. "
            "Test SMW uses ",
            ui.tags.code("rs_scpi_tcp"),
            ". ARB playback uses RsSmw via ",
            ui.tags.code("vsg_smw200a"),
            ".",
        )
    )

    return ui.page_fluid(
        ui.h2("R&S SMW200A — ARB catalog (Shiny)"),
        banner,
        ui.tags.pre(load_err, style="max-height:180px;overflow:auto;font-size:11px;")
        if load_err
        else None,
        ui.layout_columns(
            ui.card(
                ui.card_header("Connection"),
                ui.input_text("instr_visa", "VISA override (optional)", value="", width="100%"),
                ui.input_text(
                    "smw_ip",
                    "SMW IP (HiSLIP/socket from vsg_config.yaml if empty)",
                    value=_default_smw_ip_str(),
                ),
                ui.input_numeric("smw_scpi_port", "SMW SCPI TCP port (*IDN?)", value=5025, min=1, max=65535),
                ui.input_action_button("btn_scpi_idn", "Test SMW (SCPI TCP *IDN?)", class_="btn-secondary"),
                ui.input_text("fsw_ip", "FSW IP", value=_default_fsw_ip_str()),
                ui.layout_columns(
                    ui.input_numeric("fsw_port", "FSW port", value=5025, min=1, max=65535),
                    ui.input_numeric("fsw_timeout", "Socket timeout (s)", value=15, min=1, max=300),
                ),
                ui.p(ui.tags.small(ui.tags.code(f"vsg_config: {_arb_config_path_str()}"))),
            ),
            ui.card(
                ui.card_header("Signal & FSW"),
                ui.input_select(
                    "signal",
                    "Catalog signal",
                    choices=choices if choices else {"": "(ARB module not loaded)"},
                    selected=choices[0] if choices else "",
                ),
                ui.input_checkbox("dry_run", "Dry-run (.wv only, no upload / no RF)", value=False),
                ui.layout_columns(
                    ui.input_text("rf_mhz", "RF carrier MHz (empty = catalog)", value=""),
                    ui.input_text("rf_dbm", "RF power dBm (empty = catalog)", value=""),
                ),
                ui.layout_columns(
                    ui.input_text("fsw_span_hz", "FSW span Hz (empty = auto)", value=""),
                    ui.input_text("fsw_ref_dbm", "FSW ref dBm (empty = auto)", value=""),
                    ui.input_text("fsw_ch", "FSW ch", value="1"),
                ),
            ),
            col_widths=(6, 6),
        ),
        ui.card(
            ui.card_header("Waveform parameters (I/Q generator)"),
            ui.output_ui("dyn_gen_params"),
        ),
        ui.layout_columns(
            ui.input_action_button("btn_play", "Generate & apply (SMW + optional FSW)", class_="btn-primary"),
            ui.input_action_button("btn_list", "List catalog in log", class_="btn-secondary"),
            col_widths=(6, 6),
        ),
        ui.card(
            ui.card_header("Log"),
            ui.output_ui("log_area"),
        ),
    )


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def server(input: Any, output: Any, session: Any) -> None:
    log_tick = reactive.value(0)
    drain_tick = reactive.value(0)

    def touch_log() -> None:
        with _log_ui_lock:
            _log_ui_gen[0] += 1
            n = _log_ui_gen[0]
        log_tick.set(n)

    def request_log_drain() -> None:
        drain_tick.set(int(drain_tick()) + 1)

    @reactive.effect
    def _drain_thread_log() -> None:
        drain_tick()
        n = 0
        while True:
            try:
                ln = _log_thread_queue.get_nowait()
            except queue.Empty:
                break
            if ln == _LOG_THREAD_SCPI_DONE:
                _scpi_test_running["v"] = False
                continue
            _log_append(ln)
            n += 1
        if n:
            touch_log()
        keep_polling = _play_running["v"] or _scpi_test_running["v"] or not _log_thread_queue.empty() or n > 0
        if keep_polling:
            reactive.invalidate_later(0.12)

    @reactive.calc
    def arb_mod() -> tuple[Any | None, str | None]:
        return _load_arb()

    @render.ui
    def dyn_gen_params() -> ui.Tag:
        arb, err = arb_mod()
        if err or arb is None:
            return ui.p("(ARB module not loaded.)", class_="text-muted")
        name = input.signal()
        if not name or name not in arb.CATALOG:
            return ui.p("(Select a catalog signal.)", class_="text-muted")
        entry = arb.CATALOG[name]
        specs = arb.list_generator_param_specs(entry)
        if not specs:
            return ui.p("(no editable parameters)", class_="text-muted")
        rows = []
        for spec in specs:
            sid = f"gp_{_sanitize_gp_id(spec.name)}"
            rows.append(
                ui.layout_columns(
                    ui.tags.span(spec.label, class_="fw-bold"),
                    ui.input_text(sid, "", value=arb.format_gen_default_for_entry(spec), width="100%"),
                    col_widths=(3, 9),
                )
            )
        return ui.TagList(*rows)

    @render.ui
    def log_area() -> ui.Tag:
        log_tick()
        with _log_lock:
            body = "\n".join(_log_buf) if _log_buf else "(empty)"
        return ui.tags.pre(
            body,
            style="max-height:420px;overflow:auto;font-family:Consolas,monospace;font-size:12px;",
        )

    def _parse_opt_float(s: str) -> float | None:
        t = (s or "").strip()
        return None if not t else float(t)

    def _collect_gen_kwargs(arb: Any, signal_name: str) -> dict[str, Any]:
        entry = arb.CATALOG[signal_name]
        specs = arb.list_generator_param_specs(entry)
        out: dict[str, Any] = {}
        for spec in specs:
            sid = f"gp_{_sanitize_gp_id(spec.name)}"
            try:
                raw = str(input[sid]())
            except Exception:
                raw = ""
            out[spec.name] = arb.parse_gen_param_value(spec, raw)
        return out

    @reactive.effect
    @reactive.event(input.btn_list)
    def _on_list() -> None:
        arb, err = arb_mod()
        _log_clear()
        if err or arb is None:
            _log_append(err or "ARB not loaded.")
            touch_log()
            return
        _log_append("Available signals (ARB I/Q [P], B9+K515+K527):")
        for k, e in arb.CATALOG.items():
            _log_append(f"  {k:14s} {e.carrier_hz / 1e6:10.3f} MHz  {e.power_dbm:>4} dBm  {e.description}")
            _log_append(f"       {e.permanent_delivery}")
            if e.trial_native:
                _log_append(f"       (trial native, not used here: {e.trial_native})")
        touch_log()

    @reactive.effect
    @reactive.event(input.btn_scpi_idn)
    def _on_scpi_idn() -> None:
        from rs_scpi_tcp import smw_query_idn

        ip = str(input.smw_ip()).strip()
        try:
            port = int(input.smw_scpi_port())
            timeout = float(input.fsw_timeout())
        except (TypeError, ValueError):
            port = 5025
            timeout = 15.0

        def run() -> None:
            def q(msg: str) -> None:
                _log_thread_queue.put(msg)

            try:
                q("[Test SMW] Started in background — you can keep using this page.")
                q("--- SCPI TCP *IDN? ---")
                if not ip:
                    q("ERROR: enter SMW IP for TCP test.")
                    return
                try:
                    idn = smw_query_idn(ip, port, timeout_s=timeout, progress=q)
                    q(f"OK — *IDN?: {idn}")
                except Exception as exc:
                    q(f"ERROR: {type(exc).__name__}: {exc}")
                q("[Test SMW] Finished.")
            finally:
                _log_thread_queue.put(_LOG_THREAD_SCPI_DONE)

        _scpi_test_running["v"] = True
        threading.Thread(target=run, daemon=True).start()
        request_log_drain()

    @reactive.effect
    @reactive.event(input.btn_play)
    def _on_play() -> None:
        arb, err = arb_mod()
        if err or arb is None:
            ui.notification_show(err or "ARB not loaded.", duration=12, type="error")
            return
        name = str(input.signal()).strip()
        if not name or name not in arb.CATALOG:
            ui.notification_show("Select a valid catalog signal.", duration=6, type="warning")
            return

        instr = str(input.instr_visa()).strip() or None
        smw_ip = str(input.smw_ip()).strip() or None
        fsw_ip = str(input.fsw_ip()).strip() or None
        try:
            fsw_port = int(input.fsw_port())
            fsw_ch = int(str(input.fsw_ch()).strip())
        except ValueError:
            ui.notification_show("FSW port and FSW ch must be integers.", duration=8, type="error")
            return
        try:
            fsw_timeout_s = float(input.fsw_timeout())
        except (TypeError, ValueError):
            fsw_timeout_s = 15.0
        try:
            gen_kwargs = _collect_gen_kwargs(arb, name)
        except ValueError as exc:
            ui.notification_show(str(exc), duration=10, type="error")
            return

        rf_mhz = _parse_opt_float(str(input.rf_mhz()))
        rf_dbm = _parse_opt_float(str(input.rf_dbm()))
        carrier_hz = None if rf_mhz is None else float(rf_mhz) * 1e6
        power_dbm = rf_dbm
        fsw_span = _parse_opt_float(str(input.fsw_span_hz()))
        fsw_ref = _parse_opt_float(str(input.fsw_ref_dbm()))
        addr = arb.resolve_instr_addr(instr, smw_ip)
        dry = bool(input.dry_run())

        _log_clear()
        touch_log()
        _play_running["v"] = True
        request_log_drain()

        def work() -> None:
            try:
                def emit(msg: str) -> None:
                    _log_thread_queue.put(msg)

                emit(f"VISA: {addr}")
                arb.play(
                    name,
                    dry_run=dry,
                    instr_addr=addr,
                    carrier_hz=carrier_hz,
                    power_dbm=power_dbm,
                    gen_kwargs=gen_kwargs,
                    fsw_ip=fsw_ip,
                    fsw_port=fsw_port,
                    fsw_timeout_s=fsw_timeout_s,
                    fsw_span_hz=fsw_span,
                    fsw_ref_dbm=fsw_ref,
                    fsw_ch=fsw_ch,
                    log=emit,
                )
                emit("Done.")
            except Exception as exc:
                _log_thread_queue.put(
                    "ERROR:\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                )
            finally:
                _play_running["v"] = False

        threading.Thread(target=work, daemon=True).start()


app = App(app_ui, server)


def main() -> None:
    """Open the Shiny ARB catalog app in the default browser."""
    app.run(launch_browser=True)


if __name__ == "__main__":
    main()
