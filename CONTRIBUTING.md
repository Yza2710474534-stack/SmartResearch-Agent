# 开发说明

## 1. 安装开发环境

从仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.lock.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
```

锁定文件包含运行、构建、测试和格式检查依赖。修改依赖时同时检查 `pyproject.toml` 和锁定版本，再验证安装与测试。

## 2. 本地检查

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m ruff format --check src tests scripts
.venv/bin/python -m pip check
```

测试使用离线资料及 HTTP 模拟，不需要配置 API Key。涉及真实模型的验证应单独记录模型、输入资料、耗时、用量和人工复核结果。

## 3. 重建演示输出

```bash
.venv/bin/python scripts/build_demo.py
```

脚本在临时目录运行默认主题的离线流程，将 `report.md`、`evidence.json`、`validation.json` 和公开示例的来源快照保存到 `examples/demo/`。不复制带运行时间的元信息，因此输出可以逐字比较。

修改样例资料或渲染逻辑后，运行脚本并检查演示差异。GitHub Actions 同样重建演示，避免 README 链接的示例与代码不一致。

## 4. 提交范围

提交代码、测试、文档、配置模板和随项目提供的演示资料。`.env`、`runs/`、虚拟环境及本地工具配置已加入忽略规则。包含用户上传资料或 API Key 的运行结果应留在本地。

## 5. 自动检查

`.github/workflows/ci.yml` 在 push 和 pull request 时运行 Python 3.9、3.11、3.12 的依赖检查、测试、Ruff 检查、命令行演示及样例一致性检查。

配置参考 [GitHub 官方 Python CI 指南](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)。远程检查状态以仓库 Actions 页面为准。
