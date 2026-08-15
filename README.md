# 汽水音乐三大唱片规则

此仓库保存三合一提取器使用的三大唱片公司筛选规则。

## 文件

- `major_label_blocklist.json`：规则正文。
- `manifest.json`：版本、更新时间、文件大小和 SHA-256 校验值。
- `tools/build_manifest.py`：生成清单。

## 更新规则

1. 核验环球、索尼、华纳的官方签约或版权信息。
2. 修改 `major_label_blocklist.json`，同时递增 `database_version` 和 `updated_at`。
3. 提交到 `main` 分支。
4. GitHub Actions 会自动重新生成 `manifest.json`。
5. 将两个 JSON 文件同步到国内更新服务器的 `/soda-rules/` 目录。

只加入已经核验的签约、直属或联合厂牌和明确目录权利。战略合作、单曲发行或普通分销关系不自动推定为旗下艺人。
