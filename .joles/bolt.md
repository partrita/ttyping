
### Mocking module imports

When mocking imports, it's important to understand how they were imported in the source file. If a file `src/my_module/utils.py` does:

```python
from importlib import resources

def load_file():
    resources.files("my_module.data")
```

The correct target to patch is `"my_module.utils.resources.files"` not `"my_module.utils.files"`. Patching `"importlib.resources.files"` also wouldn't affect the specific `resources.files` reference initialized within the scope of the file executing.
