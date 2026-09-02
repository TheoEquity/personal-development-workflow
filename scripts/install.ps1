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
    "writing-test-drafts"
)

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$sourceRoot = Join-Path $repositoryRoot "skills"
$triggerOverridePath = Join-Path $repositoryRoot "config/global-skill-trigger-overrides.json"
$destinationFullPath = [System.IO.Path]::GetFullPath($DestinationRoot)

if (-not (Test-Path -LiteralPath $triggerOverridePath -PathType Leaf)) {
    throw "Global Skill trigger override file does not exist: $triggerOverridePath"
}
$triggerOverrides = Get-Content -LiteralPath $triggerOverridePath -Raw -Encoding UTF8 | ConvertFrom-Json
$triggerOverrideEntries = @($triggerOverrides.PSObject.Properties | Sort-Object Name)
if ($triggerOverrideEntries.Count -eq 0) {
    throw "Global Skill trigger override file is empty: $triggerOverridePath"
}
foreach ($entry in $triggerOverrideEntries) {
    $description = [string]$entry.Value
    if (-not $description.StartsWith("Use when", [System.StringComparison]::Ordinal)) {
        throw "Global Skill trigger description must start with 'Use when': $($entry.Name)"
    }
    if ($description -match "[\r\n]") {
        throw "Global Skill trigger description must be a single line: $($entry.Name)"
    }
}

if ($Check -and $Force) {
    throw "-Check is read-only and cannot be combined with -Force."
}

if (-not (Test-Path -LiteralPath $destinationFullPath -PathType Container)) {
    throw "Destination skill root does not exist: $destinationFullPath"
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

function Get-SkillDescription {
    param(
        [Parameter(Mandatory)]
        [string]$SkillFile
    )

    $content = [System.IO.File]::ReadAllText($SkillFile)
    $matches = [regex]::Matches($content, "(?m)^description:[^\r\n]*(?=\r?$)")
    if ($matches.Count -ne 1) {
        throw "Expected exactly one description line in $SkillFile"
    }
    return $matches[0].Value.Substring("description:".Length).Trim()
}

function Set-SkillDescription {
    param(
        [Parameter(Mandatory)]
        [string]$SkillFile,

        [Parameter(Mandatory)]
        [string]$Description
    )

    $content = [System.IO.File]::ReadAllText($SkillFile)
    $pattern = [regex]::new("(?m)^description:[^\r\n]*(?=\r?$)")
    if ($pattern.Matches($content).Count -ne 1) {
        throw "Expected exactly one description line in $SkillFile"
    }
    $updated = $pattern.Replace($content, "description: $Description", 1)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($SkillFile, $updated, $utf8NoBom)
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
    foreach ($entry in $triggerOverrideEntries) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $destinationFullPath $entry.Name))
        Assert-ChildPath -Parent $destinationFullPath -Child $target
        $skillFile = Join-Path $target "SKILL.md"
        if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
            continue
        }
        $actualDescription = Get-SkillDescription -SkillFile $skillFile
        if ($actualDescription -cne [string]$entry.Value) {
            $differences += "trigger description differs: $($entry.Name)"
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

$triggerSkillsToUpdate = @(
    foreach ($entry in $triggerOverrideEntries) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $destinationFullPath $entry.Name))
        Assert-ChildPath -Parent $destinationFullPath -Child $target
        $skillFile = Join-Path $target "SKILL.md"
        if (
            (Test-Path -LiteralPath $skillFile -PathType Leaf) -and
            (Get-SkillDescription -SkillFile $skillFile) -cne [string]$entry.Value
        ) {
            [pscustomobject]@{
                Name = $entry.Name
                SkillFile = $skillFile
                Description = [string]$entry.Value
            }
        }
    }
)

if ($existingSkills.Count -gt 0 -and -not $Force) {
    throw "Custom skill destination already exists: $($existingSkills -join ', '). Re-run with -Force to back up and replace."
}

$backupRoot = $null
if ($existingSkills.Count -gt 0 -or $triggerSkillsToUpdate.Count -gt 0) {
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

    foreach ($triggerSkill in $triggerSkillsToUpdate) {
        $backupTarget = Join-Path (
            Join-Path $backupRoot "trigger-overrides"
        ) $triggerSkill.Name
        New-Item -ItemType Directory -Path $backupTarget -Force | Out-Null
        Copy-Item -LiteralPath $triggerSkill.SkillFile -Destination (
            Join-Path $backupTarget "SKILL.md"
        )
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

foreach ($triggerSkill in $triggerSkillsToUpdate) {
    Set-SkillDescription `
        -SkillFile $triggerSkill.SkillFile `
        -Description $triggerSkill.Description
}

$presentTriggerSkills = @(
    foreach ($entry in $triggerOverrideEntries) {
        $skillFile = Join-Path (Join-Path $destinationFullPath $entry.Name) "SKILL.md"
        if (Test-Path -LiteralPath $skillFile -PathType Leaf) {
            $entry.Name
        }
    }
)

Write-Output "Installed $($customSkills.Count) custom skills into $destinationFullPath"
Write-Output "Configured $($presentTriggerSkills.Count) global Skill trigger descriptions; skipped $($triggerOverrideEntries.Count - $presentTriggerSkills.Count) missing Skills"
if ($null -ne $backupRoot) {
    Write-Output "Backup created at $backupRoot"
}
