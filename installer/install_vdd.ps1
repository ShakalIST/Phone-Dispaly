# Installs Virtual Display Driver (VirtualDrivers/Virtual-Display-Driver, MIT)
# so the phone gets its own desktop instead of a mirror of the laptop screen.
# Run elevated. Log: %ProgramData%\PhoneDisplay\vdd_install.log

$ErrorActionPreference = 'Continue'
$logDir = Join-Path $env:ProgramData 'PhoneDisplay'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'vdd_install.log'
Start-Transcript -Path $log -Force | Out-Null

function Test-VddInstalled {
    $dev = Get-PnpDevice -Class Display -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -match 'Virtual Display Driver|MttVDD' }
    return [bool]$dev
}

try {
    if (Test-VddInstalled) {
        Write-Host 'Virtual Display Driver is already installed.'
        exit 0
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host 'winget not found. Install "App Installer" from Microsoft Store, then re-run the installer.'
        exit 2
    }

    $common = @('-e', '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity')
    Write-Host '--- VC++ Redistributable ---'
    & winget install --id Microsoft.VCRedist.2015+.x64 @common
    Write-Host '--- Virtual Display Driver package ---'
    & winget install --id VirtualDrivers.Virtual-Display-Driver @common

    # winget installs it as a portable package; find its folder
    $roots = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'),
        (Join-Path $env:ProgramFiles 'WinGet\Packages')
    )
    $pkg = $null
    foreach ($r in $roots) {
        if (Test-Path $r) {
            $pkg = Get-ChildItem $r -Directory -Filter 'VirtualDrivers.Virtual-Display-Driver*' -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($pkg) { break }
        }
    }
    if (-not $pkg) { throw 'Virtual Display Driver package folder not found after winget install.' }
    Write-Host "Package: $($pkg.FullName)"

    # x64 files live in the folder named "x86" in this package
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'ARM64' } else { 'x86' }
    $drv = Join-Path $pkg.FullName "SignedDrivers\$arch\VDD"
    $devcon = Join-Path $pkg.FullName 'Dependencies\devcon.exe'
    $inf = Join-Path $drv 'MttVDD.inf'
    if (-not (Test-Path $inf)) { throw "Driver INF not found: $inf" }
    if (-not (Test-Path $devcon)) { throw "devcon.exe not found: $devcon" }

    # the driver reads its settings from C:\VirtualDisplayDriver
    $cfgDir = 'C:\VirtualDisplayDriver'
    New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
    if (-not (Test-Path (Join-Path $cfgDir 'vdd_settings.xml'))) {
        Copy-Item (Join-Path $drv 'vdd_settings.xml') $cfgDir -Force
    }

    Write-Host '--- devcon install ---'
    & $devcon install $inf 'Root\MttVDD'
    Write-Host "devcon exit code: $LASTEXITCODE"

    Start-Sleep -Seconds 3
    if (Test-VddInstalled) {
        Write-Host 'OK: virtual display installed.'
        exit 0
    }
    throw 'Driver did not appear in Display adapters.'
}
catch {
    Write-Host "ERROR: $_"
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
