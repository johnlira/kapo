$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$root = Join-Path $projectRoot "repositorios"
$projectsFile = Join-Path $projectRoot "scripts/projetos.tsv"

if (-not (Test-Path $projectsFile)) {
    throw "Arquivo de projetos nao encontrado: $projectsFile"
}

$projetos = Import-Csv -Path $projectsFile -Delimiter "`t"
$cloned = 0
$ignored = 0
$failed = 0
$failures = @()

foreach ($projeto in $projetos) {
    $grupo = $projeto.grupo
    $nome = $projeto.nome
    $url = $projeto.url
    $destinoGrupo = Join-Path $root $grupo
    $destinoProjeto = Join-Path $destinoGrupo $nome

    New-Item -ItemType Directory -Force -Path $destinoGrupo | Out-Null

    if (Test-Path (Join-Path $destinoProjeto ".git")) {
        Write-Host "Ignorando ${grupo}/${nome}: pasta ja existe." -ForegroundColor Yellow
        $ignored++
        continue
    }

    if (Test-Path $destinoProjeto) {
        try {
            Remove-Item -LiteralPath $destinoProjeto -Force -ErrorAction Stop
        } catch {
            Write-Error "Falha ao clonar ${grupo}/${nome}: destino ja existe e nao e um repositorio Git."
            $failed++
            $failures += "${grupo}/${nome}"
            continue
        }
    }

    Write-Host "Clonando ${grupo}/${nome}..." -ForegroundColor Cyan
    git clone $url $destinoProjeto
    if ($LASTEXITCODE -eq 0) {
        $cloned++
    } else {
        $failed++
        $failures += "${grupo}/${nome}"
        Write-Warning "Falha ao clonar ${grupo}/${nome}. Continuando nos demais repositorios."
    }
}

Write-Host "`nResumo da clonagem:"
Write-Host "  Clonados com sucesso: $cloned"
Write-Host "  Ignorados: $ignored"
Write-Host "  Com falha: $failed"

if ($failed -gt 0) {
    Write-Host "`nRepositorios com falha:"
    $failures | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
