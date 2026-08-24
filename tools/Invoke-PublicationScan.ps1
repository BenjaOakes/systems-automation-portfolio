[CmdletBinding()]
param(
    [string]$Path = (Get-Location).Path,
    [string]$OutputPath = (Join-Path (Get-Location).Path 'publication-scan.json')
)

Set-StrictMode -Version Latest
$root = (Resolve-Path -LiteralPath $Path).Path
$output = [System.IO.Path]::GetFullPath($OutputPath)
$scannerPath = [System.IO.Path]::GetFullPath($PSCommandPath)

function Add-Finding {
    param([System.Collections.Generic.List[object]]$Findings, [string]$File, [string]$Category, [string]$Rule, [int]$Line, [string]$Severity = 'REVIEW REQUIRED')
    [void]$Findings.Add([pscustomobject]@{Path=$File; Category=$Category; Rule=$Rule; Line=$Line; Severity=$Severity})
}

$findings = [System.Collections.Generic.List[object]]::new()
$files = @(Get-ChildItem -LiteralPath $root -Recurse -File -Force | Where-Object { [System.IO.Path]::GetFullPath($_.FullName) -ne $output -and [System.IO.Path]::GetFullPath($_.FullName) -ne $scannerPath })
$ignoredProvenance = [System.Collections.Generic.List[string]]::new()
$suspiciousNames = '(?i)(^|[\\/])(?:\.env(?:\..*)?|.*\.(?:pfx|p12|pem|key|crt|cer|credential|credentials|log|bak|zip|dump|export|state|sqlite|db))$'
$textExtensions = @('.ps1','.psm1','.psd1','.py','.ts','.tsx','.js','.json','.jsonl','.md','.txt','.toml','.yaml','.yml','.csv','.ini','.cfg','.config','.xml')

foreach ($file in $files) {
    $relative = [System.IO.Path]::GetRelativePath($root, $file.FullName)
    if ($relative -match '(?i)(^|[\\/])SOURCE_NOTES\.md$' -or $relative -match '(?i)^BUILD_REPORT\.md$') { [void]$ignoredProvenance.Add($relative); continue }
    if ($file.FullName -match $suspiciousNames) { Add-Finding $findings $relative 'SuspiciousFile' 'sensitive/runtime filename' 0 }
    if ($textExtensions -notcontains $file.Extension.ToLowerInvariant()) { continue }
    try { $lines = @(Get-Content -LiteralPath $file.FullName -ErrorAction Stop) } catch { Add-Finding $findings $relative 'Unreadable' 'file could not be inspected' 0; continue }
    for ($i=0; $i -lt $lines.Count; $i++) {
        $line = [string]$lines[$i]; $number = $i + 1
        if ($line -match '(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b') { Add-Finding $findings $relative 'Secret' 'private key or cloud access-key shape' $number }
        if ($line -match '(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[^<\s][^\s]*') { Add-Finding $findings $relative 'Secret' 'credential assignment shape' $number }
        if ($line -match '(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}') { Add-Finding $findings $relative 'Secret' 'bearer token shape' $number }
        if ($line -match '(?i)(?:Server|Data Source|Host)\s*=.*(?:User Id|Password|Account Key)\s*=') { Add-Finding $findings $relative 'Secret' 'connection string shape' $number }
        if ($line -match '(?i)https?://(?!localhost(?::\d+)?(?:/|\b)|127\.0\.0\.1(?::\d+)?(?:/|\b)|registry\.npmjs\.org(?:/|\b)|[^/\s]+\.example(?:/|\b)|[^/\s]+\.invalid(?:/|\b))[^\s"''<>]+') { Add-Finding $findings $relative 'URL' 'non-example URL requires review' $number }
        if ($line -match '(?<![0-9])(?:10\.(?:[0-9]{1,3}\.){2}[0-9]{1,3}|192\.168\.(?:[0-9]{1,3}\.)[0-9]{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])\.(?:[0-9]{1,3}\.)[0-9]{1,3})(?![0-9])') { Add-Finding $findings $relative 'Network' 'private IPv4 range' $number }
        $backslash = [regex]::Escape([string][char]92)
        $unixPathMarkers = (@('Users','home','private','var') | ForEach-Object { '/' + $_ + '/' }) -join '|'
        $pathPattern = '(?i)(?:[A-Z]:' + $backslash + '(?:Users|ScriptRunner|temp)' + $backslash + '|' + $unixPathMarkers + ')'
        if ($line -match $pathPattern) { Add-Finding $findings $relative 'Path' 'local or operational filesystem path' $number }
        if ($line -match '(?i)\b(?:tenant|application|app|object|group|directory)[_-]?(?:id|identifier)\s*[:=]\s*["'']?[0-9a-f]{8}-[0-9a-f-]{27,}["'']?') { Add-Finding $findings $relative 'Identifier' 'provider identifier shape' $number }
        if ($line -match '(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b') {
            $domain = $Matches[1].ToLowerInvariant()
            if ($domain -notmatch '(?:\.example|\.invalid|\.test)$') { Add-Finding $findings $relative 'Identity' 'non-synthetic email domain' $number }
        }
    }
}

$report = [pscustomobject]@{
    GeneratedUtc = [datetime]::UtcNow
    Root = $root
    FilesInspected = $files.Count - $ignoredProvenance.Count
    FilesConsidered = $files.Count
    IgnoredProvenanceFiles = @($ignoredProvenance)
    Findings = @($findings)
    FindingCount = $findings.Count
    Status = if ($findings.Count) { 'REVIEW REQUIRED' } else { 'PASS' }
    Notes = @('This scanner reports indicators and never deletes or rewrites files.', 'The scanner implementation is excluded from self-matching to avoid flagging its rule literals.', 'Gitignored provenance files are listed but excluded because they are local preparation records, not publication content.')
}
$parent = Split-Path -Parent $output
if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $output -Encoding utf8
$report | Select-Object Status,FilesInspected,FindingCount,@{Name='OutputPath';Expression={$output}} | Format-List
if ($findings.Count) { $findings | Sort-Object Path,Line | Format-Table -AutoSize }
