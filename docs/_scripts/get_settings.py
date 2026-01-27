from io import StringIO
from pathlib import Path
from typing import Any

import mkdocs_gen_files

MASK = """
### {name}

*Type:* `{type}`

*Default:* `{default}`

-----------

"""
DEFAULTS: dict[str, tuple[Any, ...]] = {}
TABLE = []
TABLE.append("# Settings")
TABLE.append("")
TERMS = {}

index = "settings.md"

FILE = Path("src/hope_dedup_engine/config/__init__.py").absolute()
res = FILE.read_text()
buf = StringIO(res)
exec_code = compile(res, "mulstring", "exec")
exec(exec_code)  # noqa S102

for k, v in DEFAULTS.items():
    TERMS[k] = MASK.format(name=k, type=v[0], default=v[1])

TABLE.extend([TERMS[term] for term in sorted(TERMS.keys())])


with mkdocs_gen_files.open(index, "w") as f:
    f.writelines("\n".join(TABLE))
mkdocs_gen_files.set_edit_path(index, "get_settings.py")
