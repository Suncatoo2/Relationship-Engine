# Storage 抽象层设计

> JSONL 是当前实现。SQLite / 图数据库 / Redis 是未来可能。
> 业务代码永远只调用 Storage 接口，不知道底层是什么。

---

## 设计原则

**业务逻辑永远不直接读写文件。** 只能通过 Storage 接口。

```
错误: 直接在 web_server.py 里 open("events.jsonl", "a")
正确: storage = JSONLStorage("data"); storage.append(event)
```

---

## 抽象接口

```python
class Storage(ABC):
    """Event Log 存储抽象接口"""

    @abstractmethod
    def append(self, event: dict) -> str:
        """追加一条事件，返回 event_id"""
        ...

    @abstractmethod
    def read_all(self, since: str = None, limit: int = None) -> Iterator[dict]:
        """读取所有事件（支持分页和增量）"""
        ...

    @abstractmethod
    def read_by_person(self, person: str, limit: int = None) -> Iterator[dict]:
        """按人物读取事件"""
        ...

    @abstractmethod
    def read_by_type(self, event_type: str, limit: int = None) -> Iterator[dict]:
        """按类型读取事件"""
        ...

    @abstractmethod
    def search(self, keyword: str, limit: int = None) -> list[dict]:
        """搜索事件"""
        ...

    @abstractmethod
    def count(self) -> int:
        """事件总数"""
        ...

    @abstractmethod
    def compact(self):
        """压缩/归档（可选实现）"""
        ...
```

---

## 当前实现：JSONLStorage

```python
class JSONLStorage(Storage):
    def __init__(self, data_dir: str):
        self._log_file = os.path.join(data_dir, "events.jsonl")

    def append(self, event: dict) -> str:
        with open(self._log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
        return event["id"]

    def read_all(self, since=None, limit=None) -> Iterator[dict]:
        with open(self._log_file, "r") as f:
            for line in f:
                data = json.loads(line)
                if since and data.get("id") <= since:
                    continue
                yield data
                # limit 在外层控制
```

---

## 未来实现

### SQLiteStorage (v0.6)

```python
class SQLiteStorage(Storage):
    def __init__(self, data_dir: str):
        self._db = sqlite3.connect(os.path.join(data_dir, "events.db"))
        self._init_schema()

    def _init_schema(self):
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                person TEXT DEFAULT '',
                data TEXT NOT NULL,
                source TEXT DEFAULT 'user_input'
            )
        """)
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_type ON events(type)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_person ON events(person)")
```

优势：按类型、按人物查询不需要全表扫描。

### GraphStorage (v2.0)

```python
class GraphStorage(Storage):
    """用于 Social Graph（人物关系网络）"""
    def __init__(self, data_dir: str):
        # Neo4j / NetworkX / 自定义图结构
        ...
```

---

## 迁移路径

```
v0.3.95 (现在):
  JSONLStorage — 直接文件读写，约 50 行代码

v0.4:
  EventLog 类改为调用 Storage 接口
  _auto_extract_facts 不再直接读文件
  现有 32 个测试应全部并行通过

v0.6:
  数据量达到 10 万级别时，切换为 SQLiteStorage
  或混合模式（hot 数据用 SQLite，cold 数据用 JSONL）

v2.0:
  Social Graph 功能启动时，新增 GraphStorage 实现
```

---

## 为什么不现在切换到 SQLite？

```
JSONL 的优势:
  - 人类可读（可以直接打开看）
  - append-only（不会因 crash 损坏）
  - git 友好（可以 diff）
  - 无依赖（不需要 sqlite3 模块）
  - 当前数据量下性能足够（< 100ms 全量 scan）

切换时机:
  - 事件量 > 10 万条
  - 全量读取 > 500ms
  - 需要复杂查询（JOIN、聚合）时
```
