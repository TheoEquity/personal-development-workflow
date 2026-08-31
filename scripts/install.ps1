[CmdletBinding()]
param(
    [Parameter()]
    [string]$DestinationRoot = (Join-Path (Join-Path $HOME ".codex") "skills"),

    [Parameter()]
    [switch]$Force,

    [Parameter()]
    [switch]$Check
)

$ErrorActionPreference = "Stop"

$customSkills = @(
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts",
    "writing-final-logic-drafts"
)

$requiredDependencies = @(
    "writing-lean-plans",
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

if ($Check -and $Force) {
    throw "-Check is read-only and cannot be combined with -Force."
}

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

function Get-CanonicalSkillFiles {
    param(
        [Parameter(Mandatory)]
        [string]$Root
    )

    Get-ChildItem -LiteralPath $Root -File -Recurse | Where-Object {
        $relativePath = $_.FullName.Substring($Root.Length).TrimStart(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        )
        $parts = $relativePath -split "[\\/]"
        "__pycache__" -notin $parts -and
        ".pytest_cache" -notin $parts -and
        $_.Extension -notin @(".pyc", ".sqlite", ".sqlite3", ".bak", ".tmp") -and
        $_.Name -notlike "*.pre-*-backup"
    }
}

function Get-RelativeFileMap {
    param(
        [Parameter(Mandatory)]
        [string]$Root,

        [Parameter()]
        [switch]$CanonicalSource
    )

    $files = if ($CanonicalSource) {
        @(Get-CanonicalSkillFiles -Root $Root)
    } else {
        @(Get-ChildItem -LiteralPath $Root -File -Recurse)
    }
    $map = @{}
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($Root.Length).TrimStart(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        ).Replace([System.IO.Path]::DirectorySeparatorChar, "/")
        $map[$relativePath] = $file.FullName
    }
    return $map
}

function Get-InstallationDifferences {
    $differences = @()
    foreach ($skillName in $customSkills) {
        $source = [System.IO.Path]::GetFullPath((Join-Path $sourceRoot $skillName))
        $target = [System.IO.Path]::GetFullPath((Join-Path $destinationFullPath $skillName))
        if (-not (Test-Path -LiteralPath $target -PathType Container)) {
            $differences += "missing installation: $skillName"
            continue
        }

        $sourceFiles = Get-RelativeFileMap -Root $source -CanonicalSource
        $targetFiles = Get-RelativeFileMap -Root $target
        foreach ($relativePath in @($sourceFiles.Keys | Sort-Object)) {
            $displayPath = "$skillName/$relativePath"
            if (-not $targetFiles.ContainsKey($relativePath)) {
                $differences += "missing from installation: $displayPath"
                continue
            }
            $sourceHash = (Get-FileHash -LiteralPath $sourceFiles[$relativePath] -Algorithm SHA256).Hash
            $targetHash = (Get-FileHash -LiteralPath $targetFiles[$relativePath] -Algorithm SHA256).Hash
            if ($sourceHash -ne $targetHash) {
                $differences += "content differs: $displayPath"
            }
        }
        foreach ($relativePath in @($targetFiles.Keys | Sort-Object)) {
            if (-not $sourceFiles.ContainsKey($relativePath)) {
                $differences += "extra in installation: $skillName/$relativePath"
            }
        }
    }
    return @($differences)
}

function Copy-SkillTree {
    param(
        [Parameter(Mandatory)]
        [string]$Source,

        [Parameter(Mandatory)]
        [string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-CanonicalSkillFiles -Root $Source | ForEach-Object {
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

if ($Check) {
    $differences = @(Get-InstallationDifferences)
    if ($differences.Count -gt 0) {
        throw "Installation differs from canonical source:`n$($differences -join [Environment]::NewLine)"
    }
    Write-Output "Installation matches canonical source at $destinationFullPath"
    return
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
