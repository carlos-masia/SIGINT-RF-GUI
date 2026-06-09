"""
Shiny web GUI: ARB catalog workflow aligned with ``smw200a_arb_signals.py --gui`` (Tk).

Loads ``smw200a_arb_signals`` from the sibling device repo under ``iceye/`` and puts that
folder on ``sys.path`` so ``import rs_scpi_tcp`` resolves to **SIGINT-RF-DEVICE-VSG_SMW200A**
(``smw_query_idn``, FSW helpers, etc.) — single source of truth with the ARB script.

Run (browser), from repo root ``iceye``:

    python -m shiny run --reload SIGINT-RF-GUI/SIGINT-RF-GUI/vsg_gui.py:app

Or:

    sigint-rf-gui-shiny

ARB upload / RF still uses RsSmw via ``VsgSmw200a`` inside ``play()`` (same as the Tk GUI).
"""

from __future__ import annotations

import importlib.util
import queue
import re
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from shiny import App, reactive, render, ui

__all__ = ("app", "main")

_gui_dir = Path(__file__).resolve().parent
if str(_gui_dir) not in sys.path:
    sys.path.insert(0, str(_gui_dir))


def _iceye_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _rel_iceye(path: Path) -> str:
    """Path relative to ``iceye/`` (POSIX slashes), for UI and short errors."""
    try:
        return path.resolve().relative_to(_iceye_root().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _strip_iceye_abs(text: str) -> str:
    """Remove absolute ``iceye`` prefix from tracebacks / messages (Windows or POSIX)."""
    b = str(_iceye_root().resolve())
    return text.replace(b + "\\", "").replace(b + "/", "").replace(b, "").lstrip("\\/")


def _device_inner() -> Path:
    return _iceye_root() / "SIGINT-RF-DEVICE-VSG_SMW200A" / "SIGINT-RF-DEVICE-VSG_SMW200A"


def _arb_script_path() -> Path:
    return _device_inner() / "smw200a_arb_signals.py"


def _ensure_import_paths() -> None:
    """Put GUI package dir and device inner dir on ``sys.path`` (device provides ``rs_scpi_tcp``)."""
    gui_dir = str(Path(__file__).resolve().parent)
    dev_inner = str(_device_inner())
    for p in (gui_dir, dev_inner):
        try:
            sys.path.remove(p)
        except ValueError:
            pass
    sys.path.insert(0, dev_inner)
    sys.path.insert(0, gui_dir)


_arb: Any | None = None
_arb_load_error: str | None = None


def _load_arb() -> tuple[Any | None, str | None]:
    """Load ``smw200a_arb_signals`` once on success; retry after failures if the file appears."""
    global _arb, _arb_load_error
    if _arb is not None:
        return _arb, None
    path = _arb_script_path()
    if not path.is_file():
        msg = f"smw200a_arb_signals.py not found:\n{_rel_iceye(path)}"
        _arb_load_error = msg
        return None, msg
    _ensure_import_paths()
    name = "_sigint_smw_arb_signals_gui"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        msg = f"Could not load import spec for {_rel_iceye(path)}"
        _arb_load_error = msg
        return None, msg
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        msg = _strip_iceye_abs("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        _arb_load_error = msg
        return None, msg
    _arb = mod
    _arb_load_error = None
    return _arb, None


def _sanitize_gp_id(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", name)


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


def _default_smw_ip_str() -> str:
    arb, err = _load_arb()
    if err or arb is None:
        return "192.168.0.10"
    try:
        return str(arb.default_smw_ip(None))
    except Exception:
        return "192.168.0.10"


def _default_fsw_ip_str() -> str:
    arb, err = _load_arb()
    if err or arb is None:
        return ""
    try:
        v = arb._fsw_ip_from_vsg_yaml()
        return v or ""
    except Exception:
        return ""


def _arb_config_path_str() -> str:
    arb, err = _load_arb()
    if err or arb is None:
        return _rel_iceye(_device_inner() / "vsg_config.yaml")
    try:
        return _rel_iceye(Path(arb.config_file_path()))
    except Exception:
        return _rel_iceye(_device_inner() / "vsg_config.yaml")


def _catalog_choices() -> list[str]:
    arb, err = _load_arb()
    if err or arb is None:
        return []
    return sorted(arb.CATALOG.keys())


def app_ui(request: Any | None = None) -> ui.Tag:
    """Shiny passes ``request`` on each page render; optional for direct calls."""
    _load_arb()
    choices = _catalog_choices()
    load_err = _arb_load_error

    banner = (
        ui.tags.p(
            ui.tags.strong("Could not load ARB module. "),
            "Fix the path or dependencies, then reload.",
            class_="text-danger",
        )
        if load_err
        else ui.tags.p(
            "RF only on a conducted/shielded bench. FSW uses ",
            ui.tags.code("rs_scpi_tcp"),
            " (device repo). ARB playback uses RsSmw inside ",
            ui.tags.code("play()"),
            " like the Tk GUI.",
        )
    )

    return ui.page_fluid(
        ui.h2("R&S SMW200A — ARB catalog (Shiny)"),
        banner,
        ui.tags.pre(_strip_iceye_abs(load_err), style="max-height:180px;overflow:auto;font-size:11px;")
        if load_err
        else None,
        ui.layout_columns(
            ui.card(
                ui.card_header("Connection"),
                ui.input_text("instr_visa", "VISA override (optional)", value="", width="100%"),
                ui.input_text("smw_ip", "SMW IP (HiSLIP/socket from YAML if empty)", value=_default_smw_ip_str()),
                ui.input_numeric("smw_scpi_port", "SMW SCPI TCP port (*IDN?)", value=5025, min=1, max=65535),
                ui.input_action_button("btn_scpi_idn", "Test SMW (SCPI TCP *IDN?)", class_="btn-secondary"),
                ui.input_text("fsw_ip", "FSW IP", value=_default_fsw_ip_str()),
                ui.layout_columns(
                    ui.input_numeric("fsw_port", "FSW port", value=5025, min=1, max=65535),
                    ui.input_numeric("fsw_timeout", "Socket timeout (s) FSW / SCPI", value=15, min=1, max=300),
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


def server(input: Any, output: Any, session: Any) -> None:
    log_tick = reactive.value(0)
    drain_tick = reactive.value(0)

    def touch_log() -> None:
        """Bump a reactive counter so ``log_area`` refreshes (must run in Shiny's reactive context)."""
        with _log_ui_lock:
            _log_ui_gen[0] += 1
            n = _log_ui_gen[0]
        log_tick.set(n)

    def request_log_drain() -> None:
        """Wake the thread-log drainer (must run in Shiny's reactive context)."""
        drain_tick.set(int(drain_tick()) + 1)

    @reactive.effect
    def _drain_thread_log() -> None:
        """Move lines from worker threads into ``_log_buf`` and refresh the log UI."""
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
        try:
            q_pending = not _log_thread_queue.empty()
        except Exception:
            q_pending = True
        keep_polling = (
            _play_running["v"] or _scpi_test_running["v"] or q_pending or n > 0
        )
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
                    ui.input_text(
                        sid,
                        "",
                        value=arb.format_gen_default_for_entry(spec),
                        width="100%",
                    ),
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
            _log_append(
                f"  {k:14s} {e.carrier_hz / 1e6:10.3f} MHz  {e.power_dbm:>4} dBm  {e.description}"
            )
            _log_append(f"       {e.permanent_delivery}")
            if e.trial_native:
                _log_append(f"       (trial native, not used here: {e.trial_native})")
        touch_log()

    @reactive.effect
    @reactive.event(input.btn_scpi_idn)
    def _on_scpi_idn() -> None:
        _ensure_import_paths()
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
                    q("[Test SMW] Finished (error).")
                    return
                try:
                    idn = smw_query_idn(ip, port, timeout_s=timeout, progress=q)
                    q(f"OK — *IDN?: {idn}")
                except Exception as e:
                    q(f"ERROR: {type(e).__name__}: {e}")
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
        except ValueError as e:
            ui.notification_show(str(e), duration=10, type="error")
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
            except Exception as e:
                _log_thread_queue.put(
                    _strip_iceye_abs(
                        "ERROR:\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__))
                    )
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
