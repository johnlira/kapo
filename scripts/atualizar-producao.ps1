<# Atualiza exclusivamente os repositorios clonados para origin/producao. #>

$ErrorActionPreference = "Stop"

$Branch = "producao"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$root = Join-Path $projectRoot "repositorios"
$grupos = @("back", "front", "monolito")
$script:atualizados = 0
$script:ignorados = 0
$script:falhas = New-Object System.Collections.Generic.List[string]

foreach ($grupo in $grupos) {
    $pastaGrupo = Join-Path $root $grupo

    if (-not (Test-Path $pastaGrupo)) {
        Write-Host "Ignorando ${grupo}: pasta nao encontrada." -ForegroundColor Yellow
        $script:ignorados++
        continue
    }

    Get-ChildItem -Path $pastaGrupo -Directory | ForEach-Object {
        $pastaGit = Join-Path $_.FullName ".git"
        $nomeProjeto = "$grupo/$($_.Name)"

        if (-not (Test-Path $pastaGit)) {
            Write-Host "Ignorando ${nomeProjeto}: nao e um repositorio Git." -ForegroundColor Yellow
            $script:ignorados++
            return
        }

        Write-Host "Sincronizando $nomeProjeto com origin/$Branch..." -ForegroundColor Cyan
        git -C $_.FullName fetch origin $Branch
        if ($LASTEXITCODE -eq 0) { git -C $_.FullName reset --hard }
        if ($LASTEXITCODE -eq 0) { git -C $_.FullName clean -fd }
        if ($LASTEXITCODE -eq 0) { git -C $_.FullName checkout -B $Branch "origin/$Branch" }
        if ($LASTEXITCODE -eq 0) { git -C $_.FullName reset --hard "origin/$Branch" }
        if ($LASTEXITCODE -eq 0) { git -C $_.FullName clean -fd }

        if ($LASTEXITCODE -eq 0) {
            $script:atualizados++
        } else {
            $script:falhas.Add($nomeProjeto)
            Write-Host "Falha ao sincronizar $nomeProjeto. Continuando nos demais repositorios." -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Resumo da sincronizacao:"
Write-Host "  Sincronizados com sucesso: $script:atualizados"
Write-Host "  Ignorados: $script:ignorados"
Write-Host "  Com falha: $($script:falhas.Count)"

if ($script:falhas.Count -gt 0) {
    Write-Host ""
    Write-Host "Repositorios com falha:" -ForegroundColor Red
    foreach ($falha in $script:falhas) {
        Write-Host "  - $falha" -ForegroundColor Red
    }
    exit 1
}

if ($script:atualizados -gt 0) {
    (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") |
        Set-Content -Path (Join-Path $root ".ultima-sincronizacao-producao")
}
