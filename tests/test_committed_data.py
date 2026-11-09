"""提交到仓库的 data/ 必须始终通过校验。"""

from hot_repos import config
from hot_repos.validate import validate


def test_committed_data_is_valid():
    assert validate(config.DATA_DIR) == []
