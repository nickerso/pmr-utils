from pmr_cache import PMRCache, Workspace, InstanceMismatchError, CacheNotInitialisedError
import shutil, pathlib

BASE = pathlib.Path("cache_test")
if BASE.exists():
    shutil.rmtree(BASE)

PMR = "https://models.physiomeproject.org/"

cache = PMRCache(BASE, PMR)
print(f'Created: {cache}')
print(f'Instance file: {(BASE / ".pmr-instance").read_text().strip()}')

try:
    cache = PMRCache(BASE, PMR)
    print(f'Created: {cache}')
    print(f'Instance file: {(BASE / ".pmr-instance").read_text().strip()}')
except InstanceMismatchError as e:
    print(f'Error: unexpected instance mismatch error: {e}')
except Exception as e:
    print(f'Error: unexpected error: {e}')


try:
    PMRCache(BASE, "https://staging.physiomeproject.org/")
    print("Error: expected instance mismatch error was not raised")
except InstanceMismatchError as e:
    print(f'Caught expected instance mismatch error: {e}')

try:
    existing_folder = pathlib.Path("__pycache__")
    cache = PMRCache(existing_folder, PMR)
    print(f'Oh no! Created cache in existing folder: {cache}')
except CacheNotInitialisedError as e:
    print(f'Caught expected cache not initialised error: {e}')

ws = Workspace(
    id="workspace/123",
    url="https://models.physiomeproject.org/workspace/123",
    name="Test Workspace",
    description="A workspace for testing"
)

shutil.rmtree(BASE)