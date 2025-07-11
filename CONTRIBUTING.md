# 🤝 贡献指南

我们非常欢迎社区的贡献！感谢您愿意花时间来改进MCP智能端口扫描器。

## 目录

- [如何贡献](#如何贡献)
- [行为准则](#行为准则)
- [提交问题 (Issue)](#提交问题-issue)
- [提交拉取请求 (Pull Request)](#提交拉取请求-pull-request)
- [开发环境设置](#开发环境设置)
- [代码风格](#代码风格)
- [发布流程](#发布流程)

## 如何贡献

您可以通过以下方式为项目做出贡献：

- **报告Bug**：发现问题并提交Issue
- **建议新功能**：提出您的想法和建议
- **改进文档**：修正拼写、完善示例、补充内容
- **提交代码**：修复Bug或实现新功能

## 行为准则

我们致力于为所有贡献者和用户提供一个友好、安全和热情的环境。所有参与者都应遵守项目的行为准则。

## 提交问题 (Issue)

在提交Issue之前，请先搜索现有Issue，确保没有重复。

### Bug报告

- **标题**：清晰地描述问题，例如 "Bug: 在批量扫描模式下，并发控制失效"
- **环境**：提供您的操作系统、Python版本、项目版本
- **复现步骤**：详细描述如何复现问题
- **预期行为**：描述您期望发生什么
- **实际行为**：描述实际发生了什么，并附上日志或截图

### 功能请求

- **标题**：清晰地描述功能，例如 "Feature: 增加对IPv6的支持"
- **问题描述**：解释该功能要解决什么问题
- **方案建议**：如果您有实现思路，请分享出来

## 提交拉取请求 (Pull Request)

1. **Fork项目**：在您的GitHub账户下创建一个项目的副本。
2. **克隆您的Fork**：`git clone https://github.com/YOUR_USERNAME/mcp-port-scanner.git`
3. **创建新分支**：`git checkout -b feature/your-feature-name`
4. **进行修改**：编写代码，确保测试通过。
5. **提交更改**：`git commit -m "feat: Add some amazing feature"`
6. **推送到分支**：`git push origin feature/your-feature-name`
7. **创建Pull Request**：在GitHub上打开一个Pull Request，并详细描述您的更改。

## 开发环境设置

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/mcp-port-scanner.git
cd mcp-port-scanner

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装开发依赖
pip install -r requirements.txt

# 安装RustScan（必需）
# ...
```

## 代码风格

- **PEP 8**：遵循PEP 8代码风格指南
- **类型注解**：为所有函数和方法添加类型注解
- **文档字符串**：为模块、类、函数添加说明
- **Black & isort**：我们使用 `black` 进行代码格式化，`isort` 进行import排序

```bash
# 格式化代码
black .
isort .
```

## 发布流程

（此部分由项目维护者执行）

1. 更新 `CHANGELOG.md`
2. 更新 `pyproject.toml` 中的版本号
3. 创建git标签：`git tag -a v0.1.0 -m "Version 0.1.0"`
4. 推送标签：`git push origin v0.1.0`
5. 构建发布包：`python -m build`
6. 发布到PyPI：`twine upload dist/*`

---

感谢您的贡献！ 