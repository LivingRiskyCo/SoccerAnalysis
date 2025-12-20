# PowerShell script to add Python Scripts directory to PATH
# Run this script as Administrator

$scriptsPath = "C:\Users\nerdw\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts"

# Check if path already exists
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$scriptsPath*") {
    # Add to user PATH
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$scriptsPath", "User")
    Write-Host "✓ Added Python Scripts directory to PATH" -ForegroundColor Green
    Write-Host "  Path: $scriptsPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "⚠ Please restart your terminal/IDE for changes to take effect" -ForegroundColor Yellow
} else {
    Write-Host "✓ Python Scripts directory is already in PATH" -ForegroundColor Green
}

