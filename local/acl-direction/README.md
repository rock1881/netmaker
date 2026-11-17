# Netmaker v1.7.0 社区版：设备策略通讯方向

基线：`gravitl/netmaker` v1.7.0，commit `9b0f07fd351511a89ad5cdbf67b84c4dc0285bb4`。
本地分支：`feat/acl-direction`。Netclient 仓库位于 `../netclient`。

## 修改

- 接受 `allowed_traffic_direction=0`（源端可主动访问目标）或 `1`（双向），拒绝无效枚举。
- 启动时保留管理员选择的方向。
- 网络存在启用的单向设备策略时，使用已有的细粒度防火墙规则，禁用整网 ACCEPT 快捷路径。
- 内置 gateway 组可匹配目标节点的显式防火墙规则。
- UI 新建和编辑设备策略表单提供方向下拉框；移除这两个表单的方向强制重置。

仅修改 Apache-2.0 社区版服务端实现，不修改 `pro/`、企业授权状态或其他功能开关。
现有 UI v1.7.0 静态资产使用 SHA-256 锁定的小补丁；`patch-ui.py` 遇到不同上游包会拒绝修改。

## 语义

单向是限制谁可以发起新连接。已允许连接的回包由客户端 conntrack 放行。
多条策略的允许范围取并集；双向或 All Nodes 放行策略可能覆盖单向限制。
已有连接不会因为改方向立即断开。Netclient 的 DNS/管理保留端口例外沿用上游行为。
Linux 上由 Netclient 防火墙执行；静态 WireGuard 客户端依靠接入网关执行。

## 构建与验证

与线上一致的构建器：
`gravitl/go-builder:1.26.0@sha256:5ba9960b9a9cb998eade0c00d4af6d131e3309748179396d0c470c992d70be52`。
Linux amd64，CGO_ENABLED=1，`go build -tags ce -buildvcs=false -ldflags="-s -w"`。

```sh
go test -tags ce ./logic -run '(?i)(acl|cedirection|peer)' -count=1
```

`logic/acls_direction_ce_test.go` 覆盖方向校验、启动迁移、节点/通配符/gateway 组、
双向 WireGuard peering、单向防火墙下发、静态客户端经网关的方向限制。
`ACL_DIRECTION_FIXTURE_DIR` 可导出真实规则供客户端集成测试使用。

`../netclient/local/acl-direction-probe/` 用未修改的 Netclient 防火墙实现，在隔离 Docker 网络测试
v1.7.0 和 v1.6.0、iptables 和 nftables 的 TCP/UDP/ICMP 正向、回包与反向新连接。
该探针只能在一次性容器中运行，因为 `firewall.Init()` 会重建 Netmaker 自有规则链。

## 部署与维护

生产备份与发布目录：`us1-pub:/root/netmaker-acl-direction-20261117/`。
Compose 只替换 netmaker、netmaker-ui 镜像，现有策略方向和控制台 IP 白名单保持原样。

升级前先合并新的上游标签，再检查补丁、重新运行上述测试。
不要直接替换回官方服务端镜像：官方 CE 启动迁移会把单向策略改成双向。
回滚脚本在存在启用的单向策略时会拒绝自动回滚，避免无意扩大访问权限。
