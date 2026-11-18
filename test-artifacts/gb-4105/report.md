# gb-4105 调区归属验收报告

传感器调区后，剖面按采样时刻找归属。本目录为验收测试与结果，源码无测试产物。

## 环境
- Python 3.11 + pytest 8.3.4（fastapi 0.115.6 / SQLAlchemy 2.0.36 / psycopg 3.2.3 / httpx，按 backend/requirements.txt）。
- 真实 PostgreSQL 16.16（zonky embedded 二进制，非 root 运行于 127.0.0.1:15432，库 operatortrace / 用户 trace）。
- Redis 以进程内 FakeQueue 替代；`drain()` 与 `src.worker` 主循环逐行一致（取任务→running→execute→落库）。
- 并发用例起真实 uvicorn（127.0.0.1:18099）+ 多线程 httpx 同时打栅栏放行。

复现：`DATABASE_URL=postgresql+psycopg://trace:tracepass@127.0.0.1:15432/operatortrace python3 -m pytest -v`（conftest 自动建表、播种、接管队列）。

## 结果：16 项全部通过（重复 5 轮稳定）

### 迟到记录（test_late_backfill_and_archive）
- 补登前受理的剖面 v0：无区间，3 条采样全部找不到归属不参加连接，输出为空。
- 补登 2 条过去区间后版本升为 v1；新剖面采用修正后归属，输出 `试验间 avg 70 / 南场 avg 50`。
- 旧剖面存档（结果、checksum）未被覆盖；`POST /traces/{id}/rerun` 另存新轨迹仍锁 v0，重跑 checksum 与原分组完全一致。
- 受理时（queued）即可经 GET /traces/{id} 与列表查到 zone_version，完成后版本不变。

### 区间交界（test_boundary_* / test_adjacent_*）
- `[起点,终点)`：09:00:00 入区、09:59:59 入区、10:00:00 整点出区、08:59:59 无归属。
- 相邻区间 `[09:00,09:30)` `[09:30,10:00)` 不算相交，09:30 整点归属后一区间；登记相邻区间合法。
- 同一时刻不同写法（`T` 与空格）规范化后等价，重叠判定不受写法影响。

### 并发重叠（test_concurrent_overlap / test_batch_atomic_reject）
- 4 线程并发登记同一相交区间：恰好 1 个 200、3 个 409，版本只 +1，区间只入 1 条。
- 3 线程并发登记互不相交区间：全部 200，版本连续 2/3/4。
- 混合并发（一撞一不撞）：撞的整批 409，不撞的 200。
- 批内一条撞已生效区间：整批拒绝，版本与区间零变化；批内自相交同样整批拒绝。
- 串行化手段：登记事务对数据集行 `SELECT ... FOR UPDATE`，READ COMMITTED 下后到的登记看见先提交区间再校验。

### 其余边界
- 原连接方式（无 zone_mode / `current`）行为不变，右表重复键保留倍数；非法 zone_mode、非法 ISO 时间、`valid_from>=valid_to`、空批均 422/400；观察员登记/重跑 403、只读可查；缺失数据集/轨迹 404。
- 迁移幂等：旧库 `ALTER TABLE traces ADD COLUMN IF NOT EXISTS zone_version`，`zone_batches/zone_intervals` 由 metadata 建表；种子连续运行不新增。

## 主要改动
- backend：`models/zone.py`（批次+区间）、`services/zones.py`（行锁串行化整批登记、受理快照 pinned）、`services/operators.py`（hash_join 增加 zone_mode=current/sample_time）、`services/traces.py`（受理钉版+重跑另存）、`schemas/business.py`（区间校验规范化）、routes/controllers/seed 迁移、`migrations/002_zone_attribution.md`。
- frontend：数据集页「调区登记」面板（版本+区间+补登表单）、执行队列与剖面页展示归属版本与连接方式、剖面页「按原快照重跑」。
