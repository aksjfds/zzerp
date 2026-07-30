# zzerp v5

zzerp v5 是基于 FastAPI、PostgreSQL 和 Vue 的模块化 ERP。后端采用模块化
单体：业务模块拥有各自的数据和规则，通过公开 API 协作；生产部门通过独立
部门门面暴露能力，但共享一套生产库存、流转和工单状态机。

## 开发验证

```bash
python3 -m pip install -r backend/requirements-dev.txt
pnpm --dir frontend install
pnpm run check
```

后端测试默认使用内存数据库配置完成架构与单元验证，不需要本机 PostgreSQL。
设置 `RUN_DATABASE_TESTS=1` 和 `DATABASE_URL` 后，还会验证实际 PostgreSQL
表结构与模块所有权清单是否一致。GitHub Actions 会自动执行这两类验证以及
前端类型检查和生产构建。

## Docker 开发

```bash
docker compose up -d --build app
docker exec -it app bash
pnpm f
```

Compose 会为容器创建独立的 `frontend/node_modules` 数据卷，并按照容器的
Linux 架构自动安装锁文件中的依赖。不要把宿主机的 `node_modules` 直接共享给
容器；Vite/Rolldown 等工具包含平台相关的原生二进制。开发镜像固定使用
Python 3.12 和 Node 22，并在构建阶段安装 `backend/requirements-dev.txt`；
后端依赖变更后再次执行带 `--build` 的启动命令即可。

## 测试部署

Render 后端、Netlify 前端和 Neon PostgreSQL 的配置与操作顺序见
[部署说明](docs/deployment.md)。数据库密钥只配置在托管平台环境变量中，不写入
仓库。

## 文档入口

- [项目目录与文件职责](docs/project-structure.md)
- [模块架构、边界与迁移状态](docs/modular-architecture.md)
- [数据库设计](docs/database-design.md)
- [开发基线](docs/development-baseline.md)
- [Render、Netlify 与 Neon 测试部署](docs/deployment.md)
