param(
  [Parameter(Mandatory=$true)][string]$Ruta,
  [Parameter(Mandatory=$true)][int]$Hoja,
  [Parameter(Mandatory=$true)][string]$Rango,
  [Parameter(Mandatory=$true)][string]$Png
)
# Exporta un rango como imagen para revisión visual.
# Excel debe abrirse VISIBLE (minimizado): con la app oculta el portapapeles falla.
$ErrorActionPreference = 'Stop'
$Ruta = (Resolve-Path $Ruta).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $true; $xl.DisplayAlerts = $false
$wb = $xl.Workbooks.Open($Ruta)
$xl.CalculateFullRebuild()
Start-Sleep -Milliseconds 1500

$ws = $wb.Worksheets.Item($Hoja)
$ws.Activate()
Start-Sleep -Milliseconds 800
$rng = $ws.Range($Rango)
$rng.Select() | Out-Null
Start-Sleep -Milliseconds 500
$rng.CopyPicture(1, 2) | Out-Null
Start-Sleep -Milliseconds 1500

$ch = $ws.ChartObjects().Add(0, 0, $rng.Width + 6, $rng.Height + 6)
$ch.Chart.ChartArea.Border.LineStyle = -4142
$ch.Chart.Paste()
Start-Sleep -Milliseconds 1500
$ch.Chart.Export($Png, "PNG") | Out-Null
$ch.Delete()

$wb.Close($false); $xl.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
"listo: $Png"
