$path = 'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\llm-seer\host\host_play.ps1'
$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count -gt 0) {
  "PARSE ERRORS: " + $errors.Count
  $errors | Select-Object -First 3 | ForEach-Object { "  line $($_.Extent.StartLineNumber): $($_.Message)" }
} else {
  "parse ok"
}