# WebDesktop 打包脚本：使用 PyInstaller 将应用打包为独立 exe
# 用法：powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = 'Stop'

# 切换到脚本所在目录（项目根）
Set-Location -Path $PSScriptRoot

# 沙箱兼容：将临时目录指向工作区，并通过 sitecustomize 修复 mkdtemp 权限问题
$tmpDir = Join-Path $PSScriptRoot '.tmp'
$sitecustomizeDir = Join-Path $PSScriptRoot '.sitecustomize'
$siteDir = Join-Path $PSScriptRoot '.site'
$extraPaths = @()
if (Test-Path $sitecustomizeDir) { $extraPaths += $sitecustomizeDir }
if (Test-Path $siteDir) { $extraPaths += $siteDir }
if ($extraPaths.Count -gt 0) {
    $env:PYTHONPATH = ($extraPaths -join ';') + ';' + $env:PYTHONPATH
}
if (Test-Path $tmpDir) {
    $env:TMP = $tmpDir
    $env:TEMP = $tmpDir
}

Write-Host '=== WebDesktop 打包开始 ==='

# 开发模式下第三方依赖安装在 .site 目录（沙箱环境下系统 site-packages 不可写）
$siteDir = Join-Path $PSScriptRoot '.site'
$pathsArgs = @()
if (Test-Path $siteDir) {
    $pathsArgs = @('--paths', $siteDir)
    Write-Host "检测到本地依赖目录：$siteDir"
}

# 应用默认图标：根目录 app.ico（打包嵌入 exe，同时作为运行时窗口/任务栏图标来源）
$iconFile = Join-Path $PSScriptRoot 'app.ico'
if (-not (Test-Path $iconFile)) {
    Write-Error "未找到应用图标：$iconFile，请在项目根目录放置 app.ico 后重试。"
    exit 1
}

# 清理旧的打包产物
if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }

# PyInstaller 打包：单文件、无控制台窗口、收集 webview 相关模块，使用 app.ico 作为 exe 图标
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name WebDesktop `
    --icon $iconFile `
    --collect-all webview `
    --hidden-import bottle `
    --hidden-import proxy_tools `
    @pathsArgs `
    main.py

# 配置文件不再随包分发：首次运行时程序自动在用户主目录 ~/.WebDesktop 下创建
Write-Host ''
Write-Host '=== 打包完成 ==='
Write-Host ('生成文件：' + (Join-Path 'dist' 'WebDesktop.exe'))
Write-Host '运行 create_shortcut.ps1 可在桌面创建快捷方式。'
