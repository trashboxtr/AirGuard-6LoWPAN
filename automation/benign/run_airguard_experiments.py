#!/usr/bin/env python3
"""AirGuard-6LoWPAN reproducible Cooja experiment runner.

Designed for:
  project root: /home/ubuntu/AirGuard-6LoWPAN
  Contiki-NG:   /home/ubuntu/contiki-ng
  Cooja:        /home/ubuntu/contiki-ng/tools/cooja

The runner:
  * validates the four scenario files and radio ratios;
  * reuses the same paired seed set across all scenarios;
  * creates a per-run temporary Cooja configuration;
  * injects an active ScriptRunner plugin for headless logging;
  * runs Cooja without a GUI;
  * validates the resulting log;
  * writes a per-run JSON sidecar and a global manifest.csv;
  * resumes safely unless --force is used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_PROJECT_ROOT = Path("/home/ubuntu/AirGuard-6LoWPAN")
DEFAULT_CONTIKI_ROOT = Path("/home/ubuntu/contiki-ng")
EXPECTED_MOTES = 16
DEFAULT_DURATION_S = 600
DEFAULT_WARMUP_S = 120
DEFAULT_SEEDS = tuple(range(1001, 1011))

SCENARIOS = {
    "Clean": {
        "csc": "simulations/baseline/AirGuard_Baseline_CrossLayer.csc",
        "tx": 1.0,
        "rx": 1.0,
        "label": "normal",
        "level": "clean",
    },
    "RX90": {
        "csc": "simulations/impairment/AirGuard_Impairment_RX90_CrossLayer.csc",
        "tx": 1.0,
        "rx": 0.90,
        "label": "impairment",
        "level": "light",
    },
    "RX75": {
        "csc": "simulations/impairment/AirGuard_Impairment_RX75_CrossLayer.csc",
        "tx": 1.0,
        "rx": 0.75,
        "label": "impairment",
        "level": "moderate",
    },
    "RX60": {
        "csc": "simulations/impairment/AirGuard_Impairment_RX60_CrossLayer.csc",
        "tx": 1.0,
        "rx": 0.60,
        "label": "impairment",
        "level": "heavy",
    },
}

FINAL_METRIC_RE = re.compile(r"AIRGUARD_METRIC,.*?node=(\d+),.*?time_ms=(\d+)")
BOOT_RE = re.compile(r"AIRGUARD_BOOT,.*?node=(\d+)")
COMPLETE_RE = re.compile(r"AIRGUARD_AUTOMATION,status=complete")


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    scenario: str
    class_label: str
    impairment_level: str
    tx_success: float
    rx_success: float
    seed: int
    duration_s: int
    warmup_s: int
    analysis_s: int
    source_csc: str
    output_log: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_seed_list(value: str) -> list[int]:
    seeds: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start > end:
                raise argparse.ArgumentTypeError("Seed aralığında başlangıç sondan büyük olamaz.")
            seeds.extend(range(start, end + 1))
        else:
            seeds.append(int(token))
    if not seeds:
        raise argparse.ArgumentTypeError("En az bir seed belirtilmelidir.")
    if any(seed < 0 for seed in seeds):
        raise argparse.ArgumentTypeError("Seed değerleri negatif olamaz.")
    return sorted(set(seeds))


def float_close(actual: float, expected: float, tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= tol


def xml_local_name(tag: str) -> str:
    """Return an XML tag name without an optional namespace prefix."""
    return tag.rsplit("}", 1)[-1]


def iter_named(root: ET.Element, name: str):
    """Iterate over elements by local tag name, independent of nesting."""
    for node in root.iter():
        if xml_local_name(node.tag) == name:
            yield node


def actual_mote_nodes(root: ET.Element) -> list[ET.Element]:
    """Return real simulation motes, excluding GUI plugin <mote> entries.

    Cooja can save mote definitions either directly under <simulation> or in a
    different nesting layout. GUI plugin configurations may also contain
    lightweight <mote> tags. A real mote definition has interface configuration
    and/or a motetype identifier, so we detect it structurally.
    """
    motes: list[ET.Element] = []
    for node in iter_named(root, "mote"):
        child_names = {xml_local_name(child.tag) for child in list(node)}
        if "motetype_identifier" in child_names or "interface_config" in child_names:
            motes.append(node)
    return motes


def firmware_source_nodes(root: ET.Element) -> list[ET.Element]:
    """Return XML <source> nodes referring to the AirGuard firmware."""
    result: list[ET.Element] = []
    for node in iter_named(root, "source"):
        text = node.text or ""
        if "udp-server.c" in text or "udp-client.c" in text:
            result.append(node)
    return result


def load_and_validate_csc(path: Path, expected_tx: float, expected_rx: float) -> ET.ElementTree:
    if not path.is_file():
        raise FileNotFoundError(f"Senaryo dosyası bulunamadı: {path}")
    tree = ET.parse(path)
    root = tree.getroot()
    simulation = root.find("simulation")
    if simulation is None:
        raise ValueError(f"<simulation> bulunamadı: {path}")

    seed_node = simulation.find("randomseed")
    if seed_node is None:
        raise ValueError(f"<randomseed> bulunamadı: {path}")

    radio = simulation.find("radiomedium")
    if radio is None:
        raise ValueError(f"<radiomedium> bulunamadı: {path}")
    tx_node = radio.find("success_ratio_tx")
    rx_node = radio.find("success_ratio_rx")
    if tx_node is None or rx_node is None:
        raise ValueError(f"TX/RX success ratio alanı eksik: {path}")

    actual_tx = float(tx_node.text or "nan")
    actual_rx = float(rx_node.text or "nan")
    if not float_close(actual_tx, expected_tx) or not float_close(actual_rx, expected_rx):
        raise ValueError(
            f"Radyo oranı uyuşmuyor: {path}\n"
            f"  beklenen TX/RX={expected_tx}/{expected_rx}\n"
            f"  bulunan  TX/RX={actual_tx}/{actual_rx}"
        )

    motes = actual_mote_nodes(root)
    mote_count = len(motes)
    if mote_count != EXPECTED_MOTES:
        raise ValueError(
            f"Beklenen mote sayısı {EXPECTED_MOTES}, bulunan {mote_count}: {path}"
        )

    sources = [node.text or "" for node in firmware_source_nodes(root)]
    if not any("udp-server.c" in source for source in sources):
        raise ValueError(f"udp-server.c motetype kaynağı bulunamadı: {path}")
    if not any("udp-client.c" in source for source in sources):
        raise ValueError(f"udp-client.c motetype kaynağı bulunamadı: {path}")
    return tree


def make_logger_script(spec: RunSpec) -> str:
    target_ms = spec.duration_s * 1000
    fallback_ms = (spec.duration_s + 10) * 1000
    # Cooja ScriptRunner TIMEOUT values are milliseconds of simulation time.
    return f'''/* Auto-generated AirGuard headless logger. */
TIMEOUT({fallback_ms});

var target_ms = {target_ms};
var expected_motes = {EXPECTED_MOTES};
var seen_final = {{}};
var final_count = 0;

log.log("AIRGUARD_AUTOMATION,status=started,scenario={spec.scenario},seed={spec.seed},tx={spec.tx_success},rx={spec.rx_success},duration_s={spec.duration_s},warmup_s={spec.warmup_s},expected_motes={EXPECTED_MOTES}\\n");

timeout_function = function () {{
  if (final_count >= expected_motes) {{
    log.log("AIRGUARD_AUTOMATION,status=complete,scenario={spec.scenario},seed={spec.seed},final_count=" + final_count + ",grace_s=10\\n");
  }} else {{
    log.log("AIRGUARD_AUTOMATION,status=fallback_timeout,scenario={spec.scenario},seed={spec.seed},final_count=" + final_count + "\\n");
  }}
  log.testOK();
}}

while (true) {{
  if (msg) {{
    log.log(time + " " + id + " " + msg + "\\n");
    if (msg.indexOf("AIRGUARD_METRIC") >= 0) {{
      var match = /time_ms=(\\d+)/.exec(msg);
      if (match && parseInt(match[1], 10) >= target_ms && !seen_final[id]) {{
        seen_final[id] = true;
        final_count++;
      }}
    }}
  }}
  YIELD();
}}
'''


def remove_script_runner_plugins(root: ET.Element) -> None:
    for plugin in list(root.findall("plugin")):
        plugin_text = (plugin.text or "").strip()
        if plugin_text == "org.contikios.cooja.plugins.ScriptRunner":
            root.remove(plugin)


def add_script_runner_plugin(root: ET.Element) -> None:
    plugin = ET.SubElement(root, "plugin")
    plugin.text = "\n    org.contikios.cooja.plugins.ScriptRunner\n    "
    config = ET.SubElement(plugin, "plugin_config")
    config.text = "\n      "
    script = ET.SubElement(config, "scriptfile")
    script.text = "[CONFIG_DIR]/airguard_logger.js"
    script.tail = "\n      "
    active = ET.SubElement(config, "active")
    active.text = "true"
    active.tail = "\n    "
    config.tail = "\n  "
    plugin.tail = "\n"


def absolutize_firmware_sources(tree: ET.ElementTree, project_root: Path) -> None:
    root = tree.getroot()
    firmware_dir = project_root / "firmware" / "airguard-rpl-udp"
    for source_node in firmware_source_nodes(root):
        source_text = source_node.text or ""
        if "udp-server.c" in source_text:
            source_node.text = str(firmware_dir / "udp-server.c")
        elif "udp-client.c" in source_text:
            source_node.text = str(firmware_dir / "udp-client.c")


def generate_run_files(spec: RunSpec, source_tree: ET.ElementTree, run_work_dir: Path, project_root: Path) -> tuple[Path, Path]:
    run_work_dir.mkdir(parents=True, exist_ok=True)
    # Parse again from serialized bytes so each run gets an independent tree.
    source_bytes = ET.tostring(source_tree.getroot(), encoding="utf-8")
    root = ET.fromstring(source_bytes)
    tree = ET.ElementTree(root)

    simulation = root.find("simulation")
    assert simulation is not None
    seed_node = simulation.find("randomseed")
    assert seed_node is not None
    seed_node.text = str(spec.seed)

    title_node = simulation.find("title")
    if title_node is not None:
        title_node.text = f"AirGuard {spec.scenario} seed {spec.seed}"

    absolutize_firmware_sources(tree, project_root)
    remove_script_runner_plugins(root)
    add_script_runner_plugin(root)

    generated_csc = run_work_dir / "run.csc"
    tree.write(generated_csc, encoding="utf-8", xml_declaration=True)

    logger_js = run_work_dir / "airguard_logger.js"
    logger_js.write_text(make_logger_script(spec), encoding="utf-8")
    return generated_csc, logger_js


def validate_environment(project_root: Path, contiki_root: Path) -> dict[str, str]:
    errors: list[str] = []
    paths = {
        "project_root": project_root,
        "contiki_root": contiki_root,
        "cooja_gradlew": contiki_root / "tools" / "cooja" / "gradlew",
        "firmware_dir": project_root / "firmware" / "airguard-rpl-udp",
        "udp_client": project_root / "firmware" / "airguard-rpl-udp" / "udp-client.c",
        "udp_server": project_root / "firmware" / "airguard-rpl-udp" / "udp-server.c",
        "project_conf": project_root / "firmware" / "airguard-rpl-udp" / "project-conf.h",
        "makefile": project_root / "firmware" / "airguard-rpl-udp" / "Makefile",
    }
    for name, path in paths.items():
        if name.endswith("_root") or name.endswith("_dir"):
            if not path.is_dir():
                errors.append(f"{name}: klasör bulunamadı: {path}")
        elif not path.is_file():
            errors.append(f"{name}: dosya bulunamadı: {path}")

    scenario_hashes: dict[str, str] = {}
    for scenario, cfg in SCENARIOS.items():
        csc_path = project_root / cfg["csc"]
        try:
            load_and_validate_csc(csc_path, float(cfg["tx"]), float(cfg["rx"]))
            scenario_hashes[f"csc_{scenario}_sha256"] = sha256_file(csc_path)
        except Exception as exc:  # collect all checks
            errors.append(str(exc))

    if errors:
        raise RuntimeError("Ortam doğrulaması başarısız:\n- " + "\n- ".join(errors))

    hashes = {
        "udp_client_sha256": sha256_file(paths["udp_client"]),
        "udp_server_sha256": sha256_file(paths["udp_server"]),
        "project_conf_sha256": sha256_file(paths["project_conf"]),
        "makefile_sha256": sha256_file(paths["makefile"]),
        **scenario_hashes,
    }
    return hashes


def build_specs(project_root: Path, scenarios: Iterable[str], seeds: Iterable[int], duration_s: int, warmup_s: int, group: str) -> list[RunSpec]:
    specs: list[RunSpec] = []
    analysis_s = duration_s - warmup_s
    for scenario in scenarios:
        cfg = SCENARIOS[scenario]
        for seed in seeds:
            run_id = f"{scenario}_seed{seed:04d}_{duration_s}s"
            output_log = (
                project_root
                / "raw-data"
                / "mote-logs"
                / "cross-layer-v1_1"
                / group
                / scenario
                / f"AirGuard_{scenario}_N16_{duration_s}s_seed{seed:04d}.log"
            )
            specs.append(
                RunSpec(
                    run_id=run_id,
                    scenario=scenario,
                    class_label=str(cfg["label"]),
                    impairment_level=str(cfg["level"]),
                    tx_success=float(cfg["tx"]),
                    rx_success=float(cfg["rx"]),
                    seed=seed,
                    duration_s=duration_s,
                    warmup_s=warmup_s,
                    analysis_s=analysis_s,
                    source_csc=str(project_root / str(cfg["csc"])),
                    output_log=str(output_log),
                )
            )
    return specs


def write_matrix(path: Path, specs: list[RunSpec]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(specs[0]).keys()) if specs else list(RunSpec.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for spec in specs:
            writer.writerow(asdict(spec))


def read_log_validation(log_path: Path, target_ms: int) -> dict[str, object]:
    boots: set[int] = set()
    final_nodes: set[int] = set()
    complete_marker = False
    fallback_marker = False
    test_ok = False

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            boot_match = BOOT_RE.search(line)
            if boot_match:
                boots.add(int(boot_match.group(1)))
            metric_match = FINAL_METRIC_RE.search(line)
            if metric_match and int(metric_match.group(2)) >= target_ms:
                final_nodes.add(int(metric_match.group(1)))
            if COMPLETE_RE.search(line):
                complete_marker = True
            if "AIRGUARD_AUTOMATION,status=fallback_timeout" in line:
                fallback_marker = True
            if line.strip() == "TEST OK":
                test_ok = True

    valid = (
        len(boots) == EXPECTED_MOTES
        and len(final_nodes) == EXPECTED_MOTES
        and complete_marker
        and test_ok
        and not fallback_marker
    )
    return {
        "valid": valid,
        "boot_count": len(boots),
        "boot_nodes": sorted(boots),
        "final_metric_count": len(final_nodes),
        "final_metric_nodes": sorted(final_nodes),
        "complete_marker": complete_marker,
        "fallback_marker": fallback_marker,
        "test_ok": test_ok,
    }


def run_subprocess(command: list[str], cwd: Path, console_log: Path) -> int:
    console_log.parent.mkdir(parents=True, exist_ok=True)
    with console_log.open("w", encoding="utf-8") as out:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            out.write(line)
            out.flush()
            sys.stdout.write(line)
        return process.wait()


def execute_run(spec: RunSpec, project_root: Path, contiki_root: Path, firmware_hashes: dict[str, str], force: bool, keep_work: bool) -> tuple[str, dict[str, object]]:
    output_log = Path(spec.output_log)
    metadata_path = output_log.with_suffix(".metadata.json")
    output_log.parent.mkdir(parents=True, exist_ok=True)

    if output_log.exists() and metadata_path.exists() and not force:
        validation = read_log_validation(output_log, spec.duration_s * 1000)
        if validation["valid"]:
            print(f"[SKIP] Geçerli çıktı zaten var: {output_log}")
            return "skipped", validation

    automation_root = project_root / "experiments" / "automation"
    run_work_dir = automation_root / "work" / spec.run_id
    if run_work_dir.exists():
        shutil.rmtree(run_work_dir)
    run_work_dir.mkdir(parents=True, exist_ok=True)

    cfg = SCENARIOS[spec.scenario]
    source_tree = load_and_validate_csc(Path(spec.source_csc), spec.tx_success, spec.rx_success)
    generated_csc, logger_js = generate_run_files(spec, source_tree, run_work_dir, project_root)

    generated_csc_hash = sha256_file(generated_csc)
    logger_hash = sha256_file(logger_js)

    cooja_path = contiki_root / "tools" / "cooja"
    gradlew = cooja_path / "gradlew"
    command = [
        str(gradlew),
        "--no-watch-fs",
        "--parallel",
        "--build-cache",
        "-p",
        str(cooja_path),
        "run",
        f"--args=--contiki={contiki_root} --no-gui --logdir={run_work_dir} {generated_csc}",
    ]

    print("\n" + "=" * 78)
    print(f"[RUN] {spec.run_id}")
    print(f"      scenario={spec.scenario}, seed={spec.seed}, TX/RX={spec.tx_success}/{spec.rx_success}")
    print(f"      duration={spec.duration_s}s, warmup={spec.warmup_s}s, analysis={spec.analysis_s}s")
    print("=" * 78)

    started_at = utc_now()
    wall_start = time.monotonic()
    console_log = run_work_dir / "cooja-console.log"
    return_code = run_subprocess(command, cooja_path, console_log)
    wall_elapsed_s = round(time.monotonic() - wall_start, 3)
    finished_at = utc_now()

    produced_log = run_work_dir / "COOJA.testlog"
    if return_code != 0:
        raise RuntimeError(
            f"Cooja başarısız oldu (return code {return_code}). Konsol: {console_log}"
        )
    if not produced_log.is_file():
        raise RuntimeError(f"COOJA.testlog üretilmedi: {run_work_dir}")

    shutil.copy2(produced_log, output_log)
    validation = read_log_validation(output_log, spec.duration_s * 1000)
    log_hash = sha256_file(output_log)

    metadata = {
        **asdict(spec),
        "status": "valid" if validation["valid"] else "invalid",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "wall_elapsed_s": wall_elapsed_s,
        "cooja_return_code": return_code,
        "command": command,
        "contiki_commit": read_contiki_commit(contiki_root),
        "source_csc_sha256": sha256_file(Path(spec.source_csc)),
        "generated_csc_sha256": generated_csc_hash,
        "logger_js_sha256": logger_hash,
        "output_log_sha256": log_hash,
        "validation": validation,
        "firmware_hashes": firmware_hashes,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    if not validation["valid"]:
        raise RuntimeError(
            f"Log doğrulaması başarısız: {output_log}\n"
            f"Detay: {json.dumps(validation, ensure_ascii=False)}"
        )

    if not keep_work:
        shutil.rmtree(run_work_dir)

    print(f"[OK] {output_log}")
    print(f"     SHA-256: {log_hash}")
    return "completed", validation


def read_contiki_commit(contiki_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(contiki_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def append_manifest(manifest_path: Path, spec: RunSpec, status: str, validation: dict[str, object]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "timestamp_utc",
        "status",
        *RunSpec.__dataclass_fields__.keys(),
        "boot_count",
        "final_metric_count",
        "complete_marker",
        "fallback_marker",
        "test_ok",
        "output_log_sha256",
    ]
    row = {
        "timestamp_utc": utc_now(),
        "status": status,
        **asdict(spec),
        "boot_count": validation.get("boot_count", ""),
        "final_metric_count": validation.get("final_metric_count", ""),
        "complete_marker": validation.get("complete_marker", ""),
        "fallback_marker": validation.get("fallback_marker", ""),
        "test_ok": validation.get("test_ok", ""),
        "output_log_sha256": sha256_file(Path(spec.output_log)) if Path(spec.output_log).is_file() else "",
    }
    new_file = not manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def compile_firmware(project_root: Path, jobs: int) -> None:
    firmware_dir = project_root / "firmware" / "airguard-rpl-udp"
    print("[BUILD] Firmware derleniyor...")
    subprocess.run(
        ["make", "TARGET=cooja", f"-j{jobs}"],
        cwd=firmware_dir,
        check=True,
    )
    print("[BUILD] Firmware hazır.")


def print_check_summary(project_root: Path, contiki_root: Path, hashes: dict[str, str]) -> None:
    print("\nAirGuard otomasyon ön kontrolü başarılı.")
    print(f"Project root : {project_root}")
    print(f"Contiki root : {contiki_root}")
    print(f"Contiki commit: {read_contiki_commit(contiki_root)}")
    print("\nDoğrulanan senaryolar:")
    for scenario, cfg in SCENARIOS.items():
        print(f"  {scenario:5s}  TX={cfg['tx']}  RX={cfg['rx']}  {cfg['csc']}")
    print("\nFirmware hash özeti:")
    for key in ("udp_client_sha256", "udp_server_sha256", "project_conf_sha256", "makefile_sha256"):
        print(f"  {key}: {hashes[key]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AirGuard-6LoWPAN Cooja çoklu-seed deney otomasyonu"
    )
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--contiki-root", type=Path, default=DEFAULT_CONTIKI_ROOT)
    parser.add_argument("--check", action="store_true", help="Sadece ortam ve senaryo doğrulaması yap")
    parser.add_argument("--smoke", action="store_true", help="Clean/seed1001 için 120 saniyelik otomasyon testi çalıştır")
    parser.add_argument("--full", action="store_true", help="Varsayılan 4×10=40 koşuluk matrisi çalıştır")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCENARIOS.keys(),
        help="Yalnız seçilen senaryoyu çalıştır; birden çok kez verilebilir",
    )
    parser.add_argument(
        "--seeds",
        type=parse_seed_list,
        default=None,
        help="Örnek: 1001-1010 veya 1001,1005,1010",
    )
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_S)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP_S)
    parser.add_argument("--group", default="final-600s", help="Çıktı klasör grubu")
    parser.add_argument("--force", action="store_true", help="Geçerli mevcut logları yeniden üret")
    parser.add_argument("--keep-work", action="store_true", help="Geçici çalışma dosyalarını sakla")
    parser.add_argument("--skip-build", action="store_true", help="Başlangıç firmware derlemesini atla")
    parser.add_argument("--jobs", type=int, default=2, help="make paralel iş sayısı")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    contiki_root = args.contiki_root.resolve()

    if args.duration <= 0:
        print("HATA: --duration pozitif olmalıdır.", file=sys.stderr)
        return 2
    if args.warmup < 0 or args.warmup >= args.duration:
        print("HATA: --warmup, 0 ile duration arasında olmalıdır.", file=sys.stderr)
        return 2

    try:
        hashes = validate_environment(project_root, contiki_root)
        print_check_summary(project_root, contiki_root, hashes)
    except Exception as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1

    if args.check and not (args.smoke or args.full or args.scenario):
        return 0

    if args.smoke:
        scenarios = ["Clean"]
        seeds = [1001]
        duration_s = 120
        warmup_s = 60
        group = "automation-smoke"
    else:
        scenarios = args.scenario or list(SCENARIOS.keys())
        seeds = args.seeds or list(DEFAULT_SEEDS)
        duration_s = args.duration
        warmup_s = args.warmup
        group = args.group
        if not (args.full or args.scenario or args.seeds):
            print(
                "\nÇalıştırma modu belirtilmedi. Önce --smoke, ardından --full kullanın.",
                file=sys.stderr,
            )
            return 2

    if not args.skip_build:
        try:
            compile_firmware(project_root, args.jobs)
        except subprocess.CalledProcessError as exc:
            print(f"HATA: Firmware derlemesi başarısız: {exc}", file=sys.stderr)
            return 1

    specs = build_specs(project_root, scenarios, seeds, duration_s, warmup_s, group)
    automation_root = project_root / "experiments" / "automation"
    matrix_path = automation_root / f"experiment_matrix_{group}.csv"
    manifest_path = automation_root / f"manifest_{group}.csv"
    write_matrix(matrix_path, specs)
    print(f"\nDeney matrisi: {matrix_path}")
    print(f"Koşu sayısı  : {len(specs)}")
    print(f"Paired seeds : {', '.join(str(seed) for seed in seeds)}")

    completed = 0
    skipped = 0
    try:
        for index, spec in enumerate(specs, start=1):
            print(f"\n[{index}/{len(specs)}] {spec.run_id}")
            status, validation = execute_run(
                spec,
                project_root,
                contiki_root,
                hashes,
                force=args.force,
                keep_work=args.keep_work,
            )
            append_manifest(manifest_path, spec, status, validation)
            if status == "completed":
                completed += 1
            elif status == "skipped":
                skipped += 1
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu. Tamamlanan koşular korunmuştur.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\nHATA: {exc}", file=sys.stderr)
        print("Düzeltmeden sonra aynı komutu yeniden çalıştırabilirsiniz; geçerli koşular atlanır.", file=sys.stderr)
        return 1

    print("\n" + "=" * 78)
    print("AirGuard deney otomasyonu tamamlandı.")
    print(f"Yeni tamamlanan : {completed}")
    print(f"Atlanan/geçerli : {skipped}")
    print(f"Manifest        : {manifest_path}")
    print(f"Log kökü        : {project_root / 'raw-data/mote-logs/cross-layer-v1_1' / group}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
