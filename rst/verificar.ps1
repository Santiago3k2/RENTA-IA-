param([Parameter(Mandatory=$true)][string]$Ruta)
# Abre el libro del SIMPLE en Excel real, recalcula y devuelve las casillas del
# 2593 tal como las verá el contador. Es la comprobación que no puede hacerse
# desde Python: openpyxl escribe fórmulas, no las evalúa.
$ErrorActionPreference = 'Stop'
$Ruta = (Resolve-Path $Ruta).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
$wb = $xl.Workbooks.Open($Ruta)
$xl.CalculateFullRebuild()

# por índice y no por nombre: los nombres llevan tildes y este script
# se lee con la codificación de la consola
$liq = $wb.Worksheets.Item(1)
$casillas = @{
  '25 Ingresos gravados'       = 'F18'
  '26 Ingresos no gravados'    = 'F19'
  '29 Base del anticipo'       = 'F22'
  '29b Base en UVT'             = 'F23'
  '29c Tarifa'                  = 'F24'
  '30 Anticipo consolidado'    = 'F25'
  '43 ICA consolidado'         = 'F28'
  '43b Componente nacional'     = 'F29'
  '44 Descuento pensión'       = 'F30'
  '49 Anticipo neto'           = 'F32'
  '77 IVA generado'            = 'F35'
  '78 IVA descontable'         = 'F36'
  '80 ReteIVA'                 = 'F37'
  '74 Total IVA'               = 'F38'
  '81 Total a pagar'           = 'F48'
  '82 Aproximado a mil'        = 'F49'
}
"=== CASILLAS DEL FORMULARIO 2593 ==="
foreach ($k in ($casillas.Keys | Sort-Object)) {
  "{0,-26} {1,-5} = {2}" -f $k, $casillas[$k], $liq.Range($casillas[$k]).Text
}

"`n=== VERIFICACIONES DE LA HOJA 3.IVA ==="
$iva = $wb.Worksheets.Item(3)
foreach ($f in 13..17) {
  "  {0} = {1}" -f $iva.Range("B$f").Text, $iva.Range("F$f").Text
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
