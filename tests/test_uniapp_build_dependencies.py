import json
from pathlib import Path


PACKAGE_JSON = Path("uniapp/package.json")
PACKAGE_LOCK = Path("uniapp/package-lock.json")
PLUGIN = "@babel/plugin-proposal-private-property-in-object"


def test_wechat_build_uses_a_real_private_property_babel_plugin():
    """Prevent package-lock's placeholder package from reaching DevTools."""
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))

    assert PLUGIN in package.get("devDependencies", {})
    resolved = lock["packages"][f"node_modules/{PLUGIN}"]["version"]
    assert "placeholder" not in resolved
