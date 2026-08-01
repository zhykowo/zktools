<#
.SYNOPSIS
    启用或禁用指定的即插即用 (PnP) 设备。
.PARAMETER Action
    操作类型，可选值为 "Enable" 或 "Disable"。
.PARAMETER InstanceId
    设备的实例 ID。
#>
param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("Enable", "Disable", IgnoreCase=$true)]
    [string]$Action,

    [Parameter(Mandatory=$true)]
    [string]$InstanceId
)

# 确保脚本发生错误时能抛出异常
$ErrorActionPreference = "Stop"

# 根据 Action 参数决定执行哪个命令
if ($Action -ieq "Enable") {
    Write-Host "正在启用设备: $InstanceId"
    Enable-PnpDevice -InstanceId $InstanceId -Confirm:$false
} 
else {
    Write-Host "正在禁用设备: $InstanceId"
    Disable-PnpDevice -InstanceId $InstanceId -Confirm:$false
}

Write-Host "操作成功完成。"