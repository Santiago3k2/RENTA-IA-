param([Parameter(Mandatory=$true)][string]$Ruta)
# Verificación de un libro generado: abre en Excel real, recalcula, imprime las
# cifras clave (por nombre definido, independientes de la fila) y caza errores.
$ErrorActionPreference = 'Stop'
$Ruta = (Resolve-Path $Ruta).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
$wb = $xl.Workbooks.Open($Ruta)
$xl.CalculateFullRebuild()

"=== CIFRAS CLAVE (nombres definidos) ==="
foreach ($n in $wb.Names) {
  try { "{0,-22} = {1}" -f $n.Name, $n.RefersToRange.Text }
  catch { "{0,-22} = (sin rango)" -f $n.Name }
}

"`n=== ERRORES DE FORMULA ==="
$found = $false
for ($i = 1; $i -le $wb.Worksheets.Count; $i++) {
  $ws = $wb.Worksheets.Item($i)
  try {
    foreach ($cell in $ws.UsedRange.SpecialCells(-4123, 16)) {
      "  {0} {1} -> {2}" -f $ws.Name, $cell.Address(0,0), $cell.Text
      $found = $true
    }
  } catch { }
}
if (-not $found) { "  ninguno" }

"`n=== HOJAS ==="
for ($i = 1; $i -le $wb.Worksheets.Count; $i++) { "  {0}. {1}" -f $i, $wb.Worksheets.Item($i).Name }

$wb.Close($false); $xl.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
