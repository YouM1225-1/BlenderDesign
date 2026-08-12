# 本仓库工作准则

## 代码检索:先用 graft

本仓库由 graft 建了代码图(`graft/`,61 个 Python 文件、1199 个符号节点、2402 条边)。
定位、理解、追踪代码时**先查图,不要直接 grep 或通读文件**。

- **找位置 / 理解机制**:`graft ask "<问题>" --source`。`--source` 会内联命中处的源码,
  通常一次调用就是完整答案,不需要再开文件。
- **需要"所有出现"**:`graft grep "<字面量>"`。`ask` 是 ranked top-N,**会漏**;
  穷尽场景一律用 grep,且搜短符号名,不要写完整签名(过于具体的正则会返回空)。
- **改动任何符号之前**:先 `graft callers <symbol> --depth all` 确认爆炸半径。
  只改主文件就收手是这个仓库最容易犯的错——协议、bridge、server 三侧常常要同步改。
- **想知道某个文件有什么**:`graft skeleton <file>`,约 200 token,比通读便宜一个数量级。
- 图在每次查询前自动增量刷新,结果始终反映当前磁盘状态(含未提交改动)。全部 `$0`,不需要 API key。

提问措辞尽量带上仓库里真实存在的标识符(`status_impl`、`_check_params_shape` 这类)。
概念层(`graft build --deep`)尚未构建,当前检索是词法匹配,措辞与标识符无重叠时会零命中。

`graft/` 不进 git。新 clone 或新建 worktree 后需各自跑一次 `graft build`,
否则 SessionStart 无图可注入,且不会自动补建。

## 验证

`bash scripts/checks.sh` 是唯一的验证入口(ruff + mypy + vendor 校验 + 嵌套导入 smoke + pytest)。
声称"改好了"之前必须跑它并确认 `ALL CHECKS PASSED`。

形式化证据要求 **Git 工作树完全干净,未跟踪文件也算脏**(见 `smoke/e2e.py` 的
`_current_provenance`)。新增文件后先提交,再跑证据链。
