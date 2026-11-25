$ErrorActionPreference = 'Continue'
$dir = 'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer-factor-kb\.cache\seertmp'
$gbk = [Text.Encoding]::GetEncoding(936)
$sb = New-Object System.Text.StringBuilder

function Invoke-Seer([string]$argsLine) {
    $tmp = Join-Path $dir '_raw.json'
    cmd /c "seerapi $argsLine > `"$tmp`"" 2>$null
    if (-not (Test-Path $tmp)) { return $null }
    $raw = [IO.File]::ReadAllBytes($tmp)
    if ($raw.Length -eq 0) { return $null }
    $txt = $gbk.GetString($raw)
    try { return ($txt | ConvertFrom-Json) } catch { return $null }
}

$pets = @(
  @{id=2724; n='幻影蝶'}, @{id=3916; n='喵佐'}, @{id=3437; n='艾欧丽娅'},
  @{id=4250; n='时钟试炼官·耀'}, @{id=3022; n='王之哈莫'}, @{id=3613; n='芳馨·茉蕊儿(草王)'},
  @{id=3322; n='茉蕊儿(小草王)'}, @{id=4377; n='蒂朵'}, @{id=3036; n='乔特鲁德(龙妈)'},
  @{id=3573; n='艾莫莉萨'}, @{id=3443; n='万神寂灭·克罗诺斯(大克罗)'}, @{id=4636; n='西塔伦'},
  @{id=3540; n='鲁肃'}, @{id=4310; n='特罗斯'}, @{id=2758; n='万妖王·摩哥斯(鸭子)'}
)

foreach ($p in $pets) {
    $pet = Invoke-Seer "get pet $($p.id) --fields name,type,skill,soulmark"
    if (-not $pet) { [void]$sb.AppendLine("### $($p.n) [$($p.id)] FETCH-FAIL"); continue }
    [void]$sb.AppendLine("### $($p.n) [$($p.id)] type=$($pet.type.id)")
    $fifths = @()
    foreach ($s in $pet.skill) {
        if ($s.is_fifth -or $s.is_advanced -or $s.is_special) { $fifths += $s.skill.id }
    }
    $all = @($pet.skill | ForEach-Object { $_.skill.id })
    [void]$sb.AppendLine("  skillcount=$($all.Count) fifthspec=$($fifths -join ',')")
    if ($pet.soulmark) {
        foreach ($sm in $pet.soulmark) {
            $smo = Invoke-Seer "get soulmark $($sm.id) --fields name,info"
            if ($smo) { [void]$sb.AppendLine("  SOUL $($smo.name): $($smo.info)") }
        }
    }
    foreach ($sid in $fifths) {
        $sk = Invoke-Seer "get skill $sid --fields name,power,category,info,skill_effect"
        if ($sk) {
            $eff = ($sk.skill_effect | ForEach-Object { $_.info }) -join ' | '
            [void]$sb.AppendLine("  SK $sid $($sk.name) pow=$($sk.power) cat=$($sk.category.id): $($sk.info) || EFF: $eff")
        }
    }
    # store all skill ids for later
    [void]$sb.AppendLine("  ALLSK: $($all -join ',')")
}

[IO.File]::WriteAllText((Join-Path $dir 'probe-out.txt'), $sb.ToString(), [Text.Encoding]::UTF8)
"done"