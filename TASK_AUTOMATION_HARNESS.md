# Task Automation & Script Engineering Harness

## 1. Overview & Objective
This document defines the mandatory engineering standards, directory structures, lifecycle practices, and execution harness for all task scripts and automations created in this workspace. Every script—regardless of complexity or target environment (development, ad-hoc, staging, or production)—must strictly adhere to these specifications.

---

## 2. Core Pillars & Execution Lifecycle

```
+----------------------------------------------------------------------------------------------------+
| 1. ROLLBACK PLAN DESIGN    ==> 2. ISOLATED TASK FOLDER   ==> 3. SCRIPT IMPLEMENTATION              |
|    (Define undo strategy)         (Dedicated directory)         (Idempotent, fail-fast & safe)     |
|                                                                                                    |
|                                  ===> 4. STEP-BY-STEP EXECUTION LOGGING                            |
|                                       ([INFO] across all phases & production)                      |
|                                                                                                    |
|                                  ===> 5. FINAL KPI & EXECUTION REPORT                              |
|                                       (Duration, freed space, throughput, exit status)             |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Directory Architecture: Isolated Folders per Task

Every automation, script, and task **must reside and execute within its own dedicated, self-contained directory** under the workspace. Storing loose script files, logs, or reports in the workspace root is strictly prohibited.

### 3.1 Standard Folder Hierarchy
```
f:/windows/tasks/<task_identifier>/
├── run.ps1 | run.py | run.sh            # Main executable task logic
├── rollback.ps1 | rollback.py           # Standalone or callable rollback routine
├── config/                              # Configuration files & parameters
│   └── settings.json                    # Task-specific configurations
├── logs/                                # Step-by-step execution log files
│   └── task_YYYYMMDD_HHMMSS.log
├── reports/                             # Final KPI execution summary reports
│   └── report_YYYYMMDD_HHMMSS.json
├── artifacts/                           # Output files, processed data, generated exports
│   └── ...
└── backups/                             # Pre-execution snapshots used for rollback
    └── ...
```

### 3.2 Output & Result Storage Rules
1. **Isolated Task Root:** All generated outputs, intermediate files, and results for `<task_identifier>` must strictly reside inside `f:/windows/tasks/<task_identifier>/`.
2. **Dynamic Path Resolution:** Scripts must never hardcode absolute workspace paths. All subdirectories (`logs/`, `reports/`, `artifacts/`, `backups/`) must be resolved dynamically relative to the task's script location (`$PSScriptRoot` or `Path(__file__).parent`).
3. **Zero Root Pollution:** The workspace root `f:/windows/` must only contain shared documentation, common harnesses, and individual task subfolders under `tasks/`.

---

## 4. Mandatory Engineering Rules

### 4.1 Pre-Development Rollback Plan (Mandatory Before Coding)
Before writing or executing any automation or task script:
1. **Rollback Strategy Definition:** A concrete, documented procedure must be designed detailing how to restore the system to its pre-execution state in case of partial or total failure.
2. **State Preservation / Backups:**
   - **File modifications / deletions:** Store a pre-execution copy in the task's `backups/` directory.
   - **System / Database changes:** Define explicit undo transactions or reversal operations.
3. **Automated Rollback Trigger:** Where possible, trap fatal errors and automatically trigger the rollback procedure before exiting.

---

### 4.2 Robust Execution & Error Handling
* **Fail-Fast Policy:** Terminate immediately on unhandled errors:
  - **Bash:** `set -euo pipefail`
  - **PowerShell:** `$ErrorActionPreference = 'Stop'`
  - **Python:** Strict `try...except` hierarchies with `sys.exit(non_zero)`.
* **Explicit Exit Codes:**
  - `0`: Successful completion.
  - `> 0`: Meaningful non-zero exit codes mapped to specific failure states.
* **Idempotency & Safety:**
  - Scripts must be safely re-executable without generating duplicate records, race conditions, or corrupted state.
  - Destructive operations (deletions, drops, overrides) must provide a `--dry-run` or `-WhatIf` flag.
* **Secret & Configuration Management:**
  - Zero hardcoded credentials or sensitive API keys. Use environment variables or `.env` files located in `config/` (excluded via `.gitignore`).

---

### 4.3 Step-by-Step Execution Logging (`[INFO]`)
Detailed step-by-step progress logging is **mandatory in all environments** (debugging, ad-hoc execution, and production runs):

1. **Log Format:** Standardized format with timestamps, severity levels, and explicit step descriptors:
   ```
   [YYYY-MM-DD HH:MM:SS] [LEVEL] [Step X/N] <Action Description>
   ```
2. **Log Levels:**
   - `[DEBUG]`: Low-level state, payload inspections, internal diagnostics.
   - `[INFO]`: Progress of every distinct step, milestone start/completion, and operational checkpoints.
   - `[WARN]`: Non-fatal anomalies or recoverable fallbacks.
   - `[ERROR]`: Execution-blocking failures and error stack summaries.
3. **Dual Output:** Output directly to standard out (`stdout`/`stderr`) and persist into `tasks/<task_identifier>/logs/task_YYYYMMDD_HHMMSS.log`.

---

### 4.4 Mandatory Execution Summary & KPI Report
Every task or automation **must generate a persistent report file** in `tasks/<task_identifier>/reports/report_YYYYMMDD_HHMMSS.json` (or `.md`) upon completion containing:

#### Report Components:
* **Metadata:** Task Name, Execution Timestamp, Hostname, Triggered By, Exit Status (`SUCCESS` | `FAILED` | `ROLLED_BACK`).
* **Timing:** Start Time, End Time, Total Elapsed Duration (seconds).
* **Core Task KPIs (Context-Specific):**
  * **File Copy / Transfer Tasks:**
    * Total Files Processed / Succeeded / Skipped / Failed.
    * Total Data Volume Transferred (MB / GB).
    * Elapsed Transfer Time & Average Throughput (MB/s).
  * **Cleanup / Deletion Tasks:**
    * Total Files / Directories Removed.
    * Total Storage Resources Freed (KB / MB / GB).
    * Memory / Cache Reclaimed.
  * **Data Processing / API Tasks:**
    * Total Records Ingested vs. Outputted.
    * Error / Retry Count.
    * Processing Speed (Records/sec).

---

## 5. Standard Implementation Templates

### 5.1 PowerShell Standard Template (`tasks/<task_name>/run.ps1`)

```powershell
<#
.SYNOPSIS
    Standard Task Script with Isolated Storage, Step-by-Step Logging, Rollback, and KPI Reporting.
.DESCRIPTION
    Complies with the Task Automation & Script Engineering Harness.
.PARAMETER DryRun
    Simulates execution without performing destructive actions.
#>
[CmdletBinding()]
param (
    [switch]$DryRun
)

# 1. Strict Configuration & Directory Isolation
$ErrorActionPreference = 'Stop'
$TaskDir     = $PSScriptRoot
$LogDir      = Join-Path $TaskDir "logs"
$ReportDir   = Join-Path $TaskDir "reports"
$ArtifactDir = Join-Path $TaskDir "artifacts"
$BackupDir   = Join-Path $TaskDir "backups"

New-Item -ItemType Directory -Force -Path $LogDir, $ReportDir, $ArtifactDir, $BackupDir | Out-Null
$Timestamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile    = Join-Path $LogDir "task_$Timestamp.log"
$ReportFile = Join-Path $ReportDir "report_$Timestamp.json"

# 2. Step-by-Step Logging Function
function Write-Log {
    param (
        [Parameter(Mandatory=$true)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR", "DEBUG")][string]$Level = "INFO"
    )
    $TimeStr = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Line = "[$TimeStr] [$Level] $Message"
    Write-Output $Line
    Add-Content -Path $LogFile -Value $Line
}

# 3. Rollback Procedure
function Invoke-Rollback {
    Write-Log "Initiating rollback sequence..." "WARN"
    # Restore pre-execution state from $BackupDir
    Write-Log "Rollback sequence completed successfully." "WARN"
}

# 4. Main Execution Routine
$StartTime = Get-Date
$KPIs = @{
    TaskName         = (Split-Path -Leaf $TaskDir)
    Status           = "RUNNING"
    StartTime        = $StartTime.ToString("o")
    DryRun           = [bool]$DryRun
    ItemsProcessed   = 0
    BytesTransferred = 0
    ResourcesFreedMB = 0.0
    DurationSeconds  = 0.0
}

try {
    Write-Log "[Step 1/3] Validating environment and preparing workspace..." "INFO"
    # Environment checks and pre-execution snapshot if needed

    Write-Log "[Step 2/3] Executing main processing workload (DryRun: $DryRun)..." "INFO"
    # Main workload logic here
    $KPIs.ItemsProcessed = 150
    $KPIs.BytesTransferred = 20971520  # Example: 20 MB

    Write-Log "[Step 3/3] Saving outputs to artifacts directory and wrapping up..." "INFO"
    $KPIs.Status = "SUCCESS"
}
catch {
    $KPIs.Status = "FAILED"
    $KPIs.ErrorMessage = $_.Exception.Message
    Write-Log "Critical failure during execution: $_" "ERROR"
    Invoke-Rollback
    throw $_
}
finally {
    $EndTime = Get-Date
    $Duration = ($EndTime - $StartTime).TotalSeconds
    $KPIs.EndTime = $EndTime.ToString("o")
    $KPIs.DurationSeconds = [Math]::Round($Duration, 2)

    # Generate KPI Report File
    $KPIs | ConvertTo-Json -Depth 4 | Set-Content -Path $ReportFile
    Write-Log "Execution finished with status: $($KPIs.Status). Report saved to: $ReportFile" "INFO"
}
```

---

### 5.2 Python Standard Template (`tasks/<task_name>/run.py`)

```python
#!/usr/bin/env python3
"""
Standard Task Automation Script.
Conforms to the Task Automation & Script Engineering Harness.
"""

import sys
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# 1. Base Paths & Directory Isolation
TASK_DIR = Path(__file__).resolve().parent
LOG_DIR = TASK_DIR / "logs"
REPORT_DIR = TASK_DIR / "reports"
ARTIFACT_DIR = TASK_DIR / "artifacts"
BACKUP_DIR = TASK_DIR / "backups"

for directory in (LOG_DIR, REPORT_DIR, ARTIFACT_DIR, BACKUP_DIR):
    directory.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"task_{TIMESTAMP}.log"
REPORT_FILE = REPORT_DIR / f"report_{TIMESTAMP}.json"

# 2. Logging Setup (Console & File)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# 3. Rollback Procedure
def execute_rollback() -> None:
    """Restores pre-execution state from BACKUP_DIR on failure."""
    logging.warning("Initiating rollback sequence...")
    # Add rollback actions (restore backups, purge temporary data, etc.)
    logging.warning("Rollback sequence completed successfully.")

# 4. Main Workflow
def main(dry_run: bool = False) -> int:
    start_time = time.time()
    kpi_data: Dict[str, Any] = {
        "task_name": TASK_DIR.name,
        "status": "RUNNING",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "kpis": {
            "items_processed": 0,
            "bytes_transferred": 0,
            "resources_freed_mb": 0.0,
            "duration_seconds": 0.0
        }
    }

    try:
        logging.info("[Step 1/3] Performing dependency and environment pre-checks...")
        # Check prerequisites & take snapshots if necessary

        logging.info(f"[Step 2/3] Running main automation pipeline (dry_run={dry_run})...")
        # Example workload simulation
        kpi_data["kpis"]["items_processed"] = 75
        kpi_data["kpis"]["resources_freed_mb"] = 256.0

        logging.info("[Step 3/3] Workload completed successfully. Generating artifacts...")
        kpi_data["status"] = "SUCCESS"
        return 0

    except Exception as exc:
        logging.error(f"Critical error during execution: {exc}", exc_info=True)
        kpi_data["status"] = "FAILED"
        kpi_data["error_message"] = str(exc)
        execute_rollback()
        return 1

    finally:
        end_time = time.time()
        kpi_data["end_time"] = datetime.now(timezone.utc).isoformat()
        kpi_data["kpis"]["duration_seconds"] = round(end_time - start_time, 3)

        # Write KPI Report File
        with open(REPORT_FILE, "w", encoding="utf-8") as rf:
            json.dump(kpi_data, rf, indent=2)

        logging.info(f"Execution concluded. Status: {kpi_data['status']}. Report saved to: {REPORT_FILE}")

if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv
    exit_code = main(dry_run=is_dry_run)
    sys.exit(exit_code)
```

---

## 6. Pre-Flight Checklist for Every Workspace Task
For every task or script developed in this workspace, verify:
- [ ] **Isolated Task Directory:** Is the script located inside its own `tasks/<task_identifier>/` directory?
- [ ] **Rollback Plan Documented & Ready:** Is there an explicit procedure and backup mechanism to revert changes?
- [ ] **Step-by-Step Logging:** Does every meaningful step log `[INFO]` with timestamps to both console and `logs/`?
- [ ] **Safe Path Resolution:** Are all paths resolved dynamically relative to the task folder?
- [ ] **Fail-Fast & Exit Codes:** Does the script stop on errors and return valid non-zero exit codes?
- [ ] **Simulation Support:** Is `--dry-run` or `-WhatIf` supported for impactful operations?
- [ ] **KPI Report Generated:** Does the script output a summary report with key metrics to `reports/` upon completion?
