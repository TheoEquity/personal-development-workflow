[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$skillNames = @(
    "using-personal-development-workflow",
    "managing-change-ledger",
    "exploring-and-grilling-requirements",
    "writing-specs",
    "writing-test-drafts"
)

function Invoke-PythonCheck {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python check failed with exit code $LASTEXITCODE`: python $($Arguments -join ' ')"
    }
}

Push-Location $repositoryRoot
try {
    Invoke-PythonCheck -Arguments @(
        "-B", "-m", "unittest", "-v",
        "tests.test_package_contract",
        "tests.test_install_script"
    )

    foreach ($skillName in $skillNames) {
        $testsDirectory = Join-Path (Join-Path $repositoryRoot "skills") "$skillName/tests"
        if (Test-Path -LiteralPath $testsDirectory -PathType Container) {
            Invoke-PythonCheck -Arguments @(
                "-B", "-m", "unittest", "discover",
                "-s", $testsDirectory,
                "-p", "test_*.py",
                "-v"
            )
        }
    }

    $pythonFiles = @(
        Get-ChildItem -LiteralPath (Join-Path $repositoryRoot "skills"), (Join-Path $repositoryRoot "tests") -File -Recurse -Filter "*.py" |
            ForEach-Object { $_.FullName }
    )
    Invoke-PythonCheck -Arguments (@("-B", "-m", "py_compile") + $pythonFiles)
}
finally {
    Pop-Location
}

Write-Output "All package, Skill, installer, and Python compile checks passed."
