# shadowrocket-subboost

一份可直接导入 **Shadowrocket** 的 `.conf` 分流配置。它以原 Mihomo/Clash YAML 的策略意图为基准，并补入 [LingJingMaster/Shadowrocket-Rules](https://github.com/LingJingMaster/Shadowrocket-Rules) 的主要规则类别。

## 直接使用

主产物是 [`Shadowrocket.conf`](./Shadowrocket.conf)。

在线配置地址：

```text
https://raw.githubusercontent.com/chenzetong/shadowrocket-subboost/main/Shadowrocket.conf
```

1. 将 `Shadowrocket.conf` 通过“文件”或分享菜单导入 Shadowrocket。
2. 在 Shadowrocket 首页单独添加自己的节点或订阅。
3. 进入配置页，将导入的配置设为使用中。
4. 检查 `⚡ 自动选择`、`🇺🇸 美国中转` 和 `🇬🇧 伦敦->荷兰` 是否能匹配到节点。

Shadowrocket 配置文件没有 Mihomo `proxy-providers` 的等价写法，因此节点订阅不会嵌入 `.conf`。这样也避免把私人订阅 URL 写入 Git。

## 保留的 Clash 分流意图

| 服务 | 默认策略 |
|---|---|
| DNS 防泄露、广告 | REJECT |
| 私有网络、国内、Apple 服务 | DIRECT |
| AI、Gemini、Google | 节点选择 |
| YouTube、Telegram、X | 自动选择 |
| 代码托管、Microsoft、券商、支付、加密货币 | 节点选择 |
| 非中国、未命中流量 | 节点选择 |

保留了原配置中的自定义规则：

- `bybit.eu` → `🚀 节点选择`
- `wsnailong.com` → `⚡ 自动选择`
- Hugging Face → `⚡ 自动选择`
- Gemini 独立于完整 Google 规则，仍走 `✨ Gemini`
- OpenAI、Anthropic 及其他 AI 服务走 `🤖 AI 服务`
- PayPal、Stripe、Wise 与 Binance 保留独立策略

## 补入的参考仓库规则

- BlockHttpDNS、广告拦截
- 完整 Google、AI、YouTube、Bilibili、局域网和 Telegram
- GitHub、GitLab、Atlassian、Microsoft
- Apple Push、Apple 服务
- 富途 / moomoo / 长桥 / 老虎 / TradeUP / Schwab 券商
- China、Global、GEOIP CN 与最终兜底

Google/Apple 直接使用参考仓库的 Shadowrocket 列表，因此其中的 `USER-AGENT` 规则也能生效。规则优先级经过显式约束：Gemini 在 Google 前、Apple Push 在 Apple 前、`shortconn.im.qcloud.com` 国内直连在券商列表前，所有专项服务都在 China/Global 大类前。

## Clash 与 Shadowrocket 的差异

以下 Mihomo 设置不能逐项照搬，但已做功能对应：

- `mixed-port`、`allow-lan`：属于客户端监听行为，不是 Shadowrocket 分流规则。
- `fake-ip`、`sniffer`、`profile`：Shadowrocket 没有同名配置项。
- MRS `rule-providers`：改为 Shadowrocket 支持的远程 `.list` 和内联规则。
- DNS nameserver/fallback：转换为 `dns-server`、`fallback-dns-server`、`hijack-dns` 和 `[Host]`。
- `MATCH`：转换为 Shadowrocket 的 `FINAL`。

仓库保留 `mihomo.template.yaml` 作为迁移对照，不是 Shadowrocket 的导入文件。

## 重新生成

直接从模板生成：

```bash
python3 scripts/render_config.py --force
```

如果将配置托管到自己的公开地址，可加入更新 URL：

```bash
python3 scripts/render_config.py \
  --update-url "https://example.com/Shadowrocket.conf" \
  --force
```

`--update-url` 只能填写配置文件地址，不能填写节点订阅地址。

## 每周规则同步

`.github/workflows/sync-rules.yml` 每周一北京时间 **03:17** 自动运行：

1. 获取配置引用的 21 个上游 Shadowrocket 规则集。
2. 校验响应与规则格式，并保存到 `rules/`。
3. 将经典 Apple 规则和 `Apple_Domain.list` 去重合并，避免上游经典列表缺少约 1,550 条域名。
4. 更新 `rules/manifest.json` 的来源、规则数量及 SHA-256。
5. 重新生成并校验 `Shadowrocket.conf`，使其引用本仓库托管的规则。
6. 仅在内容确实变化时由 `github-actions[bot]` 提交，不制造每周空提交。

也可以在 GitHub Actions 页面手动运行 `Sync upstream rules`，或在本地执行：

```bash
python3 scripts/sync_rules.py
python3 scripts/render_config.py --force
python3 scripts/validate_config.py
```

定时任务需要仓库允许 GitHub Actions 对内容进行写入；工作流已经声明 `contents: write`。

## 校验

```bash
python3 scripts/validate_config.py
```

校验器检查必需节区、重复策略组、规则策略引用、远程规则格式、最终 `FINAL`，以及已知的规则覆盖冲突。它不能替代 iOS 上目标 Shadowrocket 版本的最终导入测试。

## 文件

```text
shadowrocket-subboost/
├── Shadowrocket.conf
├── Shadowrocket.template.conf
├── mihomo.template.yaml        # 仅作 Clash 迁移对照
├── rules/                       # 每周同步的规则快照及 manifest
├── scripts/
│   ├── render_config.py
│   ├── sync_rules.py
│   └── validate_config.py
└── .github/workflows/
    ├── sync-rules.yml
    └── validate.yml
```

## License

MIT
