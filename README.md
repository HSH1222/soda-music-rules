# 汽水音乐三大唱片规则

此仓库保存三合一提取器使用的三大唱片公司筛选规则。

## 文件

- `major_label_blocklist.json`：规则正文。
- `manifest.json`：版本、更新时间、文件大小和 SHA-256 校验值。
- `sources.json`：允许自动采集的官方名单页和解析规则。
- `source_snapshots.json`：上一次成功采集的官方名单快照。
- `review_queue.json`：官网移除项等待人工审核，不自动解除拦截。
- `tools/collect_official_rules.py`：严格采集官方名单并更新规则。
- `tools/build_manifest.py`：生成清单。

## 更新规则

GitHub Actions 每天北京时间 09:15 读取环球、索尼、华纳的官方名单页。
明确出现在官方厂牌或艺人名单中的新增项自动加入规则，并递增版本、生成
`manifest.json`。官网移除的项目只写入 `review_queue.json`，必须人工核验后处理。

也可以在 Actions 页面选择 `Update official rules`，点击 `Run workflow` 手动执行。
服务器仍需同步 `major_label_blocklist.json` 与 `manifest.json` 到 `/soda-rules/`。

只加入已经核验的签约、直属或联合厂牌和明确目录权利。战略合作、单曲发行或普通分销关系不自动推定为旗下艺人。
