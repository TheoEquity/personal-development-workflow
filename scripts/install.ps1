[CmdletBinding()]
param(
    [Parameter()]
    [string]$DestinationRoot = (Join-Path (Join-Path $HOME ".codex") "skills"),

    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$customSkills = @(
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts"
)

$requiredDependencies = @(
    "writing-plans",
    "using-git-worktrees",
    "subagent-driven-development",
    "executing-plans",
    "test-driven-development",
    "verification-before-completion",
    "finishing-a-development-branch"
)

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$sourceRoot = Join-Path $repositoryRoot "skills"
$destinationFullPath = [System.IO.Path]::GetFullPath($DestinationRoot)

if (-not (Test-Path -LiteralPath $destinationFullPath -PathType Container)) {
    throw "Destination skill root does not exist: $destinationFullPath"
}

function Get-SkillFrontmatterName {
    param(
        [Parameter(Mandatory)]
        [string]$SkillFile
    )

    $lines = @(Get-Content -LiteralPath $SkillFile -Encoding UTF8)
    if ($lines.Count -lt 3 -or $lines[0].Trim() -ne "---") {
        return $null
    }

    $declaredName = $null
    $hasClosingDelimiter = $false
    for ($index = 1; $index -lt $lines.Count; $index++) {
        $line = $lines[$index].Trim()
        if ($line -eq "---") {
            $hasClosingDelimiter = $true
            break
        }
        if ($line -match "^name:\s*([A-Za-z0-9-]+)\s*$") {
            $declaredName = $Matches[1]
        }
    }

    if (-not $hasClosingDelimiter) {
        return $null
    }
    return $declaredName
}

$missingDependencies = @(
    foreach ($dependency in $requiredDependencies) {
        $skillFile = Join-Path (Join-Path $destinationFullPath $dependency) "SKILL.md"
        if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
            $dependency
        }
    }
)

if ($missingDependencies.Count -gt 0) {
    throw "Missing required Superpowers skills: $($missingDependencies -join ', ')"
}

$invalidDependencies = @(
    foreach ($dependency in $requiredDependencies) {
        $skillFile = Join-Path (Join-Path $destinationFullPath $dependency) "SKILL.md"
        $declaredName = Get-SkillFrontmatterName -SkillFile $skillFile
        if ($declaredName -ne $dependency) {
            "$dependency declares '$declaredName'"
        }
    }
)

if ($invalidDependencies.Count -gt 0) {
    throw "Invalid Superpowers skill identity: $($invalidDependencies -join ', ')"
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory)]
        [string]$Parent,

        [Parameter(Mandatory)]
        [string]$Child
    )

    $parentWithSeparator = $Parent.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $Child.StartsWith($parentWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside destination root: $Child"
    }
}

function Copy-SkillTree {
    param(
        [Parameter(Mandatory)]
        [string]$Source,

        [Parameter(Mandatory)]
        [string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -File -Recurse | Where-Object {
        $_.FullName -notmatch "[\\/]__pycache__[\\/]" -and
        $_.Extension -notin @(".pyc", ".sqlite", ".sqlite3")
    } | ForEach-Object {
        $relativePath = $_.FullName.Substring($Source.Length).TrimStart(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        )
        $targetFile = Join-Path $Destination $relativePath
        $targetParent = Split-Path -Parent $targetFile
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $targetFile
    }
}

$existingSkills = @(
    foreach ($skillName in $customSkills) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $destinationFullPath $skillName))
        Assert-ChildPath -Parent $destinationFullPath -Child $target
        if (Test-Path -LiteralPath $target) {
            $skillName
        }
    }
)

if ($existingSkills.Count -gt 0 -and -not $Force) {
    throw "Custom skill destination already exists: $($existingSkills -join ', '). Re-run with -Force to back up and replace."
}

$backupRoot = $null
if ($existingSkills.Count -gt 0) {
    $timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffffffZ")
    $backupRoot = Join-Path (
        Join-Path $destinationFullPath ".personal-development-workflow-backups"
    ) $timestamp
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

    foreach ($skillName in $existingSkills) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $destinationFullPath $skillName))
        Assert-ChildPath -Parent $destinationFullPath -Child $target
        $backupTarget = Join-Path $backupRoot $skillName
        Copy-Item -LiteralPath $target -Destination $backupTarget -Recurse
    }
}

foreach ($skillName in $customSkills) {
    $source = [System.IO.Path]::GetFullPath((Join-Path $sourceRoot $skillName))
    $target = [System.IO.Path]::GetFullPath((Join-Path $destinationFullPath $skillName))
    Assert-ChildPath -Parent $destinationFullPath -Child $target

    if (-not (Test-Path -LiteralPath (Join-Path $source "SKILL.md") -PathType Leaf)) {
        throw "Packaged custom skill is missing SKILL.md: $source"
    }

    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    Copy-SkillTree -Source $source -Destination $target
}

Write-Output "Installed $($customSkills.Count) custom skills into $destinationFullPath"
if ($null -ne $backupRoot) {
    Write-Output "Backup created at $backupRoot"
}
