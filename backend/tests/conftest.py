"""pytest 共享配置。

测试用 SQLite 内存库做依赖覆盖，不真正连接 MySQL；
但 src.config.database 在导入期就会 create_engine，需要方言驱动可导入
（pymysql 在 requirements.txt 中）。conftest 先于所有测试模块导入，保证环境变量先生效。
"""
from __future__ import annotations

import os

os.environ.setdefault("DB_KIND", "mysql")
