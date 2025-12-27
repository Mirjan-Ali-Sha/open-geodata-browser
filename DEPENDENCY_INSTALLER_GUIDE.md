# QGIS Plugin Dependency Installer Guide

## Overview

This document explains how to implement a robust dependency installation system for QGIS plugins that:
- Correctly finds the Python executable on all operating systems
- Allows users to install dependencies directly from QGIS
- Supports "hot-reload" (plugin works immediately after installation, no restart needed)

---

## The Problem

On **Windows QGIS**, `sys.executable` points to `qgis.exe` or `qgis-ltr-bin.exe`, NOT to `python.exe`. This means the common approach:

```python
# ❌ WRONG - This launches QGIS, not Python!
subprocess.run([sys.executable, '-m', 'pip', 'install', 'package-name'])
```

Results in errors like:
```
CRITICAL: Invalid Data Source: C:\Users\...\-m is not a valid or recognized data source.
CRITICAL: Invalid Data Source: C:\Users\...\pip is not a valid or recognized data source.
```

---

## The Solution

### Files Required

1. **`dependency_installer.py`** - The installer module (copy to your plugin folder)
2. **Main plugin file** - Updated to use the installer

### Key Components

#### 1. Python Executable Detection (Windows)

```python
def _find_windows_python(self) -> str:
    # Method 1: OSGEO4W_ROOT environment variable
    osgeo4w_root = os.environ.get('OSGEO4W_ROOT')
    if osgeo4w_root:
        for py_ver in ['Python312', 'Python311', 'Python310', 'Python39']:
            python_path = os.path.join(osgeo4w_root, 'apps', py_ver, 'python.exe')
            if os.path.exists(python_path):
                return python_path
    
    # Method 2: Check PATH for QGIS Python
    # Method 3: Navigate from QGIS installation directory
    # Method 4: Use python-qgis.bat wrapper
    # Fallback: sys.executable (works on Linux/macOS)
```

#### 2. OS Compatibility

```python
def get_python_executable(self) -> str:
    if os.name == 'nt':  # Windows
        return self._find_windows_python()
    else:  # Linux/macOS - sys.executable works correctly
        return sys.executable
```

---

## Implementation Patterns

### Pattern A: Check at Plugin Use (Recommended)

Dependencies are checked **when the user clicks on the plugin**, not at QGIS startup.

**Advantages:**
- ✅ QGIS starts quickly
- ✅ Dialog only appears when user actually needs the plugin
- ✅ Better user experience

**Main Plugin Structure:**

```python
# At module level - try to import dependencies
DEPENDENCIES_AVAILABLE = False
try:
    import required_package
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    pass

class MyPlugin:
    REQUIRED_PACKAGES = {
        'package-name': 'import_name',  # pip name: import name
    }
    
    def __init__(self, iface):
        self.iface = iface
        self.dependencies_ok = DEPENDENCIES_AVAILABLE
        # NO dependency check here - keeps QGIS startup fast
    
    def run(self):
        # Check dependencies when user clicks the plugin
        if not self.dependencies_ok:
            if self._reload_dependencies():
                self.dependencies_ok = True
            else:
                self._check_and_install_dependencies()
                if not self.dependencies_ok:
                    return
        
        # Show plugin dialog
        self.show_dialog()
    
    def _check_and_install_dependencies(self):
        from .dependency_installer import DependencyInstaller
        installer = DependencyInstaller(self.iface, self.REQUIRED_PACKAGES)
        if installer.check_and_install():
            if self._reload_dependencies():
                self.dependencies_ok = True
    
    def _reload_dependencies(self):
        """Hot-reload: Import packages after installation"""
        global DEPENDENCIES_AVAILABLE, required_package
        try:
            import required_package as pkg
            required_package = pkg
            DEPENDENCIES_AVAILABLE = True
            return True
        except ImportError:
            return False
```

---

### Pattern B: Check at Plugin Initialization

Dependencies are checked **when QGIS loads the plugin** (in `__init__`).

**Advantages:**
- User is prompted immediately if dependencies are missing

**Disadvantages:**
- ❌ Slows down QGIS startup
- ❌ Dialog appears even if user doesn't need the plugin

**Not Recommended** - Only use if absolutely necessary.

```python
def __init__(self, iface):
    self.iface = iface
    self.dependencies_ok = DEPENDENCIES_AVAILABLE
    
    # Check at startup (SLOWS DOWN QGIS!)
    if not self.dependencies_ok:
        self._check_and_install_dependencies()
```

---

## Complete Implementation Checklist

### Step 1: Add `dependency_installer.py` to your plugin

Copy the `dependency_installer.py` file to your plugin folder. Update the `PLUGIN_NAME`:

```python
class DependencyInstaller:
    PLUGIN_NAME = "Your Plugin Name"  # Change this!
```

### Step 2: Update your main plugin file

1. **Add conditional imports at module level:**

```python
DEPENDENCIES_AVAILABLE = False
try:
    import your_required_package
    # import other_package
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    pass
```

2. **Define required packages in your class:**

```python
class YourPlugin:
    REQUIRED_PACKAGES = {
        'pip-package-name': 'import_module_name',
    }
```

3. **Initialize with dependency flag:**

```python
def __init__(self, iface):
    self.dependencies_ok = DEPENDENCIES_AVAILABLE
    # Do NOT check dependencies here!
```

4. **Check in run() method:**

```python
def run(self):
    if not self.dependencies_ok:
        if self._reload_dependencies():
            self.dependencies_ok = True
        else:
            self._check_and_install_dependencies()
            if not self.dependencies_ok:
                return
    
    self.show_dialog()
```

5. **Add helper methods:**

```python
def _check_and_install_dependencies(self):
    from .dependency_installer import DependencyInstaller
    installer = DependencyInstaller(self.iface, self.REQUIRED_PACKAGES)
    installer.PLUGIN_NAME = "Your Plugin Name"
    if installer.check_and_install(silent_if_ok=True):
        if self._reload_dependencies():
            self.dependencies_ok = True

def _reload_dependencies(self):
    global DEPENDENCIES_AVAILABLE
    global your_required_package  # Add all your imports
    try:
        import your_required_package as pkg
        your_required_package = pkg
        DEPENDENCIES_AVAILABLE = True
        return True
    except ImportError:
        return False
```

---

## Cross-Platform Support

| OS                   | Python Detection                        | Works? |
| -------------------- | --------------------------------------- | ------ |
| Windows (OSGeo4W)    | OSGEO4W_ROOT → apps/PythonXX/python.exe | ✅      |
| Windows (Standalone) | QGIS bin dir → python.exe               | ✅      |
| Linux                | sys.executable                          | ✅      |
| macOS                | sys.executable                          | ✅      |

The installer automatically handles Windows-specific issues while using `sys.executable` on Linux/macOS where it works correctly.

---

## What Changed in Our Plugins

### supervised_classifier v1.0.3
- Added `dependency_installer.py` with robust Python detection
- Updated `supervised_classifier.py`:
  - Conditional imports with `DEPENDENCIES_AVAILABLE` flag
  - `_check_and_install_dependencies()` method
  - `_reload_dependencies()` for hot-reload
  - Dependency check moved from `__init__` to `run()`

### open_geodata_browser v1.2.1
- Added `dependency_installer.py` with robust Python detection
- Updated `geodata_browser.py`:
  - Simplified main file with same pattern
  - Hot-reload capability
  - Check only when user clicks plugin

---

## Summary

| Feature            | Pattern A (Recommended) | Pattern B       |
| ------------------ | ----------------------- | --------------- |
| Check timing       | When user clicks plugin | At QGIS startup |
| QGIS startup speed | Fast ✅                  | Slow ❌          |
| User experience    | Better ✅                | Interruptive ❌  |
| Hot-reload         | Yes ✅                   | Yes ✅           |

**Always use Pattern A** - Check dependencies only when the user actually tries to use the plugin.
