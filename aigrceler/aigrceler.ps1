# aigrceler.ps1  -  AIGRCeler v2 menu (same place and same idea as in Deliverables_2)
#
# This file sits in a company's root folder, next to that company's own real
# .claude\ folder and CLAUDE.md. It is generic and self-locating: it never
# needs editing, and the same three items (.claude\, CLAUDE.md, aigrceler.ps1)
# are copied as they are into any company's root folder.
#
#   <company root>\.claude\                     the framework (agents, skills, engine, catalog, templates)
#   <company root>\CLAUDE.md                    operating rules
#   <company root>\aigrceler.ps1                this menu
#   <company root>\data\ catalog\ decisions\    the company's records (created by the engine on first run)
#   <company root>\projects\<AI system>\        one folder per AI system (created by the engine)
#   <company root>\projects\<AI system>\.claude   a JUNCTION back to ..\..\.claude  (created by this menu)
#
# A junction is an NTFS feature (no admin rights, no copies): the AI-system
# folder sees the company's one shared .claude\ so Claude Code started there
# has all the agents and skills. Deleting an AI-system folder removes only the
# link, never the shared .claude\.
#
# WHAT THIS MENU DOES
#   1. Checks that a real .claude\ is next to it, and that Python 3 is installed.
#   2. First run only: sets up the company (name, who acts as AI Governance, on what authority).
#   3. Lists the company's AI systems; you pick one, or choose company-level work, or add a new system.
#   4. Starts Claude Code in the chosen folder (or tells you which folder to open).
#
# HOW TO RUN (from the folder this file is in):
#   From cmd.exe or PowerShell:   powershell -ExecutionPolicy Bypass -File aigrceler.ps1
#   From a PowerShell prompt:     .\aigrceler.ps1   (if your policy allows local scripts)
#   cmd.exe cannot run .ps1 files directly; always use the first form from cmd.
#
# UPDATING THE FRAMEWORK: replace the .claude\ folder and CLAUDE.md with the new
# ones. Company records live outside .claude\ (data\, catalog\, decisions\,
# projects\) and are never touched by an update.

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$banner = @'
          _____ _____ ______ _   _ ______  _____ _____  _____
    /\   |_   _/ ____|  ____| \ | |  ____|/ ____|_   _|/ ____|
   /  \    | || |  __| |__  |  \| | |__  | (___   | | | (___
  / /\ \   | || | |_ |  __| | . ` |  __|  \___ \  | |  \___ \
 / ____ \ _| || |__| | |____| |\  | |____ ____) |_| |_ ____) |
/_/    \_\_____\_____|______|_| \_|______|_____/|_____|_____/
'@

$consoleWidth = 80
try {
    $w = $Host.UI.RawUI.WindowSize.Width
    if ($w -gt 0) { $consoleWidth = $w }
} catch {}
$border = "=" * $consoleWidth
$bannerLines = $banner -split "`r?`n"
$bannerBlockWidth = ($bannerLines | Measure-Object -Property Length -Maximum).Maximum
$bannerPad = " " * [Math]::Max(0, [int](($consoleWidth - $bannerBlockWidth) / 2))
$subtitle = "AI Governance Framework v2  -  Company Menu"
$subtitlePad = " " * [Math]::Max(0, [int](($consoleWidth - $subtitle.Length) / 2))

Write-Host ""
Write-Host $border -ForegroundColor DarkCyan
foreach ($bannerLine in $bannerLines) { Write-Host ($bannerPad + $bannerLine) -ForegroundColor Cyan }
Write-Host ""
Write-Host ($subtitlePad + $subtitle) -ForegroundColor White
Write-Host $border -ForegroundColor DarkCyan
Write-Host ""

$orgRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($orgRoot)) { $orgRoot = (Get-Location).Path }
$claudeDir = Join-Path $orgRoot ".claude"
$engine = Join-Path $claudeDir "shared\engine\aigrceler.py"
$wsFile = Join-Path $orgRoot "data\workspace.json"
$projectsDir = Join-Path $orgRoot "projects"

Write-Host "Company root: $orgRoot"
Write-Host ""

# --- Sanity checks ---
if (-not (Test-Path $claudeDir)) {
    Write-Host "ERROR: No .claude\ folder found next to this script at:" -ForegroundColor Red
    Write-Host "  $claudeDir" -ForegroundColor Red
    Write-Host "This script must sit in the company's root folder, alongside the framework's" -ForegroundColor Red
    Write-Host ".claude\ folder and CLAUDE.md. Copy those here first." -ForegroundColor Red
    exit 1
}
$claudeItem = Get-Item -Path $claudeDir -Force
if ($claudeItem.LinkType) {
    Write-Host "ERROR: $claudeDir is itself a $($claudeItem.LinkType) (a link), not a real folder." -ForegroundColor Red
    Write-Host "The company root's own .claude\ must be the real copy; only the AI-system folders hold links." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $engine)) {
    Write-Host "ERROR: the engine was not found at $engine. The .claude\ folder looks incomplete." -ForegroundColor Red
    exit 1
}

$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = @("py", "-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = @("python") }
else {
    Write-Host "ERROR: Python 3 was not found (tried 'py -3' and 'python'). Install Python 3, then run this again." -ForegroundColor Red
    exit 1
}

# Runs the engine and returns its exit code and text. Native programs write messages
# to stderr; PowerShell would treat those as errors, so errors are relaxed for the call.
function Invoke-Engine {
    param([string[]]$EngineArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($script:py.Count -gt 1) {
            $out = & $script:py[0] $script:py[1] $script:engine @EngineArgs "--ws" $script:orgRoot 2>&1
        } else {
            $out = & $script:py[0] $script:engine @EngineArgs "--ws" $script:orgRoot 2>&1
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    $text = (@($out) | ForEach-Object { "$_" }) -join "`n"
    return [pscustomobject]@{ Code = $code; Text = $text }
}

# --- First run: set up the company ---
if (-not (Test-Path $wsFile)) {
    Write-Host "This company has no AIGRCeler workspace yet. Setting it up." -ForegroundColor Yellow
    Write-Host ""
    $company = Read-Host "Company name"
    $gov = Read-Host "Who will act as AI Governance (the name of a person)"
    $contact = Read-Host "How to reach them (email or phone)"
    $basis = Read-Host "On what authority (for example: engagement letter, board note, owner's decision)"
    if ([string]::IsNullOrWhiteSpace($company) -or [string]::IsNullOrWhiteSpace($gov)) {
        Write-Host "ERROR: company name and the AI Governance person are required. Nothing was changed." -ForegroundColor Red
        exit 1
    }
    $r = Invoke-Engine @("ws", "init", "--company", $company, "--governance-name", $gov,
                         "--governance-contact", $contact, "--basis", $basis)
    Write-Host $r.Text
    if ($r.Code -ne 0) { exit 1 }
    Write-Host ""
}

# --- Step 1: find the company's AI systems ---
# An AI system = a folder under projects\ that has data\project.json (written by the engine).
# Its .claude\ junction is created here if it is missing.
function Get-AigrcelerSystems {
    $systems = @()
    if (Test-Path $script:projectsDir) {
        $dirs = @(Get-ChildItem -Path $script:projectsDir -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notlike ".*" -and $_.Name -notlike "_*" })
        foreach ($d in $dirs) {
            if (Test-Path (Join-Path $d.FullName "data\project.json")) {
                $link = Join-Path $d.FullName ".claude"
                if (-not (Test-Path $link)) {
                    try {
                        New-Item -ItemType Junction -Path $link -Target $script:claudeDir -Force | Out-Null
                    } catch {
                        Write-Host "NOTE: could not link .claude\ into $($d.Name): $_" -ForegroundColor Yellow
                    }
                }
                $systems += $d.Name
            }
        }
    }
    return $systems
}

# @(...) keeps a single result an array instead of unrolling it into a string.
$systems = @(Get-AigrcelerSystems)

Write-Host "AI systems in this company:" -ForegroundColor White
if ($systems.Count -eq 0) {
    Write-Host "  (none yet)" -ForegroundColor DarkGray
} else {
    for ($i = 0; $i -lt $systems.Count; $i++) { Write-Host "  [$($i + 1)] $($systems[$i])" }
}
Write-Host "  [W] Company-level work (people, roles, control catalog, risks across systems)"
Write-Host "  [N] Add a new AI system"
Write-Host "  [D] Open the dashboard (every AI system at a glance)"
Write-Host "  [Q] Quit"
Write-Host ""

$choice = Read-Host "Select a number, W for company-level work, N for new, D for the dashboard, or Q to quit"
$targetPath = $null
$targetLabel = $null

if ($choice -match '^[Qq]$') {
    Write-Host "Cancelled. Nothing was changed."
    exit 0
} elseif ($choice -match '^[Dd]$') {
    # Rebuild the dashboard from the records, then open it in the default browser. It only reads; nothing is changed.
    $r = Invoke-Engine @("dashboard", "build")
    Write-Host $r.Text
    $dash = Join-Path $orgRoot "dashboard\index.html"
    if (($r.Code -eq 0) -and (Test-Path $dash)) {
        Start-Process $dash
        Write-Host "Opened the dashboard in your browser: $dash" -ForegroundColor Green
    } else {
        Write-Host "The dashboard could not be built. See the message above." -ForegroundColor Red
        exit 1
    }
    exit 0
} elseif ($choice -match '^[Ww]$') {
    $targetPath = $orgRoot
    $targetLabel = "Company-level work"
} elseif ($choice -match '^[Nn]$') {
    Write-Host ""
    $newName = Read-Host "Name of the new AI system (letters, digits, spaces, hyphen)"
    if ([string]::IsNullOrWhiteSpace($newName)) {
        Write-Host "ERROR: No name entered. Nothing was changed." -ForegroundColor Red
        exit 1
    }
    $newName = $newName.Trim()
    if ($newName -notmatch '^[A-Za-z0-9][A-Za-z0-9 _\-]*$') {
        Write-Host "ERROR: Use letters, digits, spaces, underscore or hyphen only. Got: '$newName'" -ForegroundColor Red
        exit 1
    }
    $purpose = Read-Host "What does it do, in one line (you can leave this empty and add it later)"

    Write-Host ""
    Write-Host "This will register the AI system '$newName' and create:" -ForegroundColor Yellow
    Write-Host "  projects\<its folder>\   (records, evidence, decisions, people)" -ForegroundColor Yellow
    Write-Host "  projects\<its folder>\.claude   (junction -> $claudeDir)" -ForegroundColor Yellow
    Write-Host ""
    $confirm = Read-Host "Type CREATE to proceed"
    if ($confirm -ne "CREATE") {
        Write-Host "Cancelled. Nothing was changed."
        exit 0
    }

    $createArgs = @("project", "create", "--name", $newName)
    if (-not [string]::IsNullOrWhiteSpace($purpose)) { $createArgs += @("--purpose", $purpose) }
    $r = Invoke-Engine $createArgs
    Write-Host $r.Text
    if ($r.Code -ne 0) { exit 1 }

    $m = [regex]::Match($r.Text, "AI system '([^']+)' registered")
    if (-not $m.Success) {
        Write-Host "ERROR: the system was registered but its folder name could not be read from the reply." -ForegroundColor Red
        exit 1
    }
    $slug = $m.Groups[1].Value
    $targetPath = Join-Path $projectsDir $slug
    try {
        New-Item -ItemType Junction -Path (Join-Path $targetPath ".claude") -Target $claudeDir -Force | Out-Null
        Write-Host "OK: $slug is registered, and its .claude\ is linked to the company's shared copy." -ForegroundColor Green
    } catch {
        Write-Host "ERROR creating the .claude link: $_" -ForegroundColor Red
        exit 1
    }
    $targetLabel = $slug
} elseif ($choice -match '^\d+$') {
    $idx = [int]$choice - 1
    if ($idx -lt 0 -or $idx -ge $systems.Count) {
        Write-Host "ERROR: '$choice' is not a valid selection." -ForegroundColor Red
        exit 1
    }
    $targetLabel = $systems[$idx]
    $targetPath = Join-Path $projectsDir $targetLabel
} else {
    Write-Host "ERROR: '$choice' is not a valid selection." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Active: $targetLabel" -ForegroundColor Cyan
Write-Host " Folder: $targetPath" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $targetPath

if (Get-Command claude -ErrorAction SilentlyContinue) {
    Write-Host "Launching Claude Code in this folder. It will start by telling you where things stand and what is waiting for you." -ForegroundColor Green
    Write-Host ""
    claude "start AIGRCeler"
} else {
    Write-Host "NOTE: 'claude' was not found on PATH, so it wasn't launched automatically." -ForegroundColor Yellow
    Write-Host "This PowerShell window is now sitting in:" -ForegroundColor Yellow
    Write-Host "  $targetPath" -ForegroundColor Yellow
    Write-Host "Run 'claude' here yourself to start the session." -ForegroundColor Yellow
}
