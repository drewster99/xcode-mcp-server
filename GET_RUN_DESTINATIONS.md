# Getting Run Destinations in Xcode

This document details the investigation into querying Xcode run destinations (simulators, devices, Mac targets) via AppleScript and command-line tools for the purpose of enabling selective test execution.

## Background

The `run_project_tests` tool currently runs ALL tests in a project because AppleScript's `test workspaceDoc` command doesn't support filtering specific tests. To run individual tests, we need to use `xcodebuild test -only-testing:TestBundle/Class/testMethod`, which requires specifying a run destination via the `-destination` flag.

**The goal**: Determine how to query available run destinations and identify which one is currently active/preferred.

---

## What Works ✅

### 1. Listing Available Destinations via xcodebuild

**Command:**
```bash
xcodebuild -showdestinations -project <path> -scheme <scheme>
# OR
xcodebuild -showdestinations -workspace <path> -scheme <scheme>
```

**Example Output:**
```
Available destinations for the "SimpleApp" scheme:
    { platform:macOS, arch:arm64, id:00006040-000661D13C7A801C, name:My Mac }
    { platform:macOS, name:Any Mac }
```

For iOS projects, this would include all available simulators:
```
{ platform:iOS Simulator, id:ABC123, OS:17.0, name:iPhone 15 Pro }
{ platform:iOS Simulator, id:DEF456, OS:17.0, name:iPad Pro (11-inch) }
```

**Parsing:**
- Output format is consistent and parseable
- Each destination is a dictionary-like structure with key-value pairs
- Keys: `platform`, `arch`, `id`, `OS` (for simulators), `name`
- Can be parsed with regex or simple string splitting

**Advantages:**
- ✅ Reliable and consistent
- ✅ Works without opening Xcode
- ✅ Shows ALL valid destinations for a scheme
- ✅ Returns device IDs that can be used directly with `-destination` flag

**Usage for xcodebuild:**
```bash
# Pick a destination from the output
xcodebuild test \
  -project MyApp.xcodeproj \
  -scheme MyApp \
  -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
  -only-testing:MyAppTests/MyTestClass/testExample
```

---

### 2. Listing Available Destinations via AppleScript

**AppleScript Code:**
```applescript
tell application "Xcode"
    open projectPath

    set workspaceDoc to first workspace document whose path is projectPath

    -- Wait for workspace to load
    repeat 60 times
        if loaded of workspaceDoc is true then exit repeat
        delay 0.5
    end repeat

    -- Get all run destinations
    set runDests to run destinations of workspaceDoc

    repeat with dest in runDests
        set destName to name of dest
        set destPlatform to platform of dest
        set destArch to architecture of dest
        -- Process each destination
    end repeat
end tell
```

**Example Output:**
For a macOS project (SimpleApp.xcodeproj), this returns 3 destinations:

1. **Destination 1:**
   - Name: `My Mac`
   - Platform: `macosx`
   - Architecture: `arm64`

2. **Destination 2:**
   - Name: `My Mac (Rosetta)`
   - Platform: `macosx`
   - Architecture: `x86_64`

3. **Destination 3:**
   - Name: `Any Mac (arm64, x86_64)`
   - Platform: `macosx`
   - Architecture: `undefined_arch`

**Available Properties:**
- `name` - Human-readable destination name (e.g., "iPhone 15 Pro", "My Mac")
- `platform` - Platform identifier (e.g., "macosx", "iphonesimulator", "iphoneos")
- `architecture` - Architecture (e.g., "arm64", "x86_64", "undefined_arch")
- `device` - Device object (not always populated, returns complex object)

**Advantages:**
- ✅ Works within AppleScript workflow
- ✅ Provides same information as xcodebuild
- ✅ Can be integrated into existing AppleScript-based tools

**Disadvantages:**
- ⚠️ Requires Xcode to be running and project to be loaded
- ⚠️ Platform/architecture names may need mapping to xcodebuild format

---

## What Doesn't Work ❌

### Active Run Destination Property

The AppleScript property `active run destination of workspaceDoc` exists in Xcode's scripting dictionary but **does not function as expected**.

#### Test 1: Query Active Destination (Fresh Project)

```applescript
tell application "Xcode"
    set workspaceDoc to first workspace document whose path is projectPath
    set activeDest to active run destination of workspaceDoc
    -- Returns: missing value
end tell
```

**Result:** `missing value`

---

#### Test 2: Query Active Destination After Building

```applescript
tell application "Xcode"
    set workspaceDoc to first workspace document whose path is projectPath

    -- Build the project
    set buildResult to build workspaceDoc
    repeat
        if completed of buildResult is true then exit repeat
        delay 0.5
    end repeat

    -- Now check active run destination
    set activeDest to active run destination of workspaceDoc
    -- Returns: missing value
end tell
```

**Result:** `missing value` (unchanged after build)

---

#### Test 3: Query Active Destination After Running

```applescript
tell application "Xcode"
    set workspaceDoc to first workspace document whose path is projectPath

    -- Run the project
    set runResult to run workspaceDoc
    delay 3

    -- Check while running
    set activeDest to active run destination of workspaceDoc
    -- Returns: missing value

    stop workspaceDoc
end tell
```

**Result:** `missing value` (even while app is running)

---

#### Test 4: Explicitly Set Then Query Active Destination

```applescript
tell application "Xcode"
    set workspaceDoc to first workspace document whose path is projectPath

    -- Get first available destination
    set runDests to run destinations of workspaceDoc
    set firstDest to item 1 of runDests

    -- Try to SET the active run destination
    set active run destination of workspaceDoc to firstDest
    delay 1

    -- Now try to GET it back
    set activeDest to active run destination of workspaceDoc
    -- Returns: missing value
end tell
```

**Result:** `missing value` (even after explicitly setting it!)

The property accepted the `set` command without error, but immediately reading it back still returned `missing value`.

---

#### Test 5: Check Active Destination from Scheme

```applescript
tell application "Xcode"
    set workspaceDoc to first workspace document whose path is projectPath
    set activeScheme to active scheme of workspaceDoc

    -- Try to get destination from scheme instead of workspace
    set destFromScheme to active run destination of activeScheme
end tell
```

**Result:** Error: `Can't get active run destination of scheme "SimpleApp"`

The scheme object doesn't support this property at all.

---

#### Test 6: Check Build Result for Destination Info

```applescript
tell application "Xcode"
    set workspaceDoc to first workspace document whose path is projectPath
    set buildResult to build workspaceDoc

    repeat
        if completed of buildResult is true then exit repeat
        delay 0.5
    end repeat

    -- Check if build result contains destination info
    set props to properties of buildResult
    -- Examine props
end tell
```

**Result:** Build result properties include:
- `status` - build status (succeeded/failed)
- `completed` - boolean
- `build log` - full text log
- `id` - unique identifier

But **no destination information** in the build result object.

---

## Analysis

### Why `active run destination` Doesn't Work

Several possibilities:

1. **Write-only property**: The property can be set but not read (unusual in AppleScript but possible)
2. **Incomplete API**: The property exists in the dictionary but isn't fully implemented
3. **Requires specific state**: May only work in contexts we haven't discovered (e.g., debugging session)
4. **Xcode version-specific**: May have worked in older Xcode versions but is now deprecated/broken
5. **UI-only property**: The "active" destination may only exist in the UI layer, not the automation layer

### Testing Environment

- **Xcode Version**: (determined by the system running these tests)
- **macOS**: Darwin 25.1.0
- **Test Project**: SimpleApp.xcodeproj (macOS target)
- **Schemes Tested**: SimpleApp (default scheme)

---

## Workarounds and Solutions

Since we **cannot** reliably query the active destination, here are viable alternatives:

### Solution 1: Use First Available Destination (Recommended)

When destinations are listed (via AppleScript or xcodebuild), they appear to be ordered by preference. The first destination is typically the default.

```python
def get_default_destination(project_path, scheme):
    """Get the first (default) destination for a scheme"""
    # Run: xcodebuild -showdestinations -scheme X -project Y
    # Parse output
    # Return first destination string
    return "platform=iOS Simulator,name=iPhone 15 Pro"
```

**Advantages:**
- ✅ Simple and reliable
- ✅ Matches likely user intent (default is usually what they want)
- ✅ No guessing required

**Disadvantages:**
- ⚠️ May not match what user manually selected in Xcode UI (but this is acceptable)

---

### Solution 2: Parse xcodebuild Destination Format

Convert destination dictionaries from xcodebuild output into `-destination` flag format:

**Input from xcodebuild:**
```
{ platform:iOS Simulator, id:ABC123, OS:17.0, name:iPhone 15 Pro }
```

**Output for xcodebuild command:**
```
-destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

OR use the ID directly:
```
-destination 'id=ABC123'
```

**Implementation:**
```python
import re

def parse_destinations(xcodebuild_output):
    """Parse destinations from xcodebuild -showdestinations output"""
    destinations = []

    # Regex to match destination lines
    pattern = r'\{\s*platform:([^,}]+)(?:,\s*id:([^,}]+))?(?:,\s*OS:([^,}]+))?(?:,\s*name:([^}]+))?\s*\}'

    for match in re.finditer(pattern, xcodebuild_output):
        platform = match.group(1).strip()
        dest_id = match.group(2).strip() if match.group(2) else None
        os_version = match.group(3).strip() if match.group(3) else None
        name = match.group(4).strip() if match.group(4) else None

        # Build destination string
        if dest_id:
            dest_string = f"id={dest_id}"
        elif name:
            dest_string = f"platform={platform},name={name}"
        else:
            dest_string = f"platform={platform}"

        destinations.append({
            'platform': platform,
            'id': dest_id,
            'name': name,
            'os': os_version,
            'destination_string': dest_string
        })

    return destinations
```

---

### Solution 3: Let LLM/User Choose

Present available destinations to the LLM and let it choose based on context:

```python
def select_destination_for_tests(destinations, test_type):
    """LLM-friendly destination selection"""
    # For unit tests: prefer "Any Mac" or generic simulator
    # For UI tests: prefer specific device (iPhone 15 Pro)
    # For performance tests: prefer physical device if available

    if test_type == "unit":
        # Prefer generic destinations
        for dest in destinations:
            if "Any" in dest['name']:
                return dest['destination_string']

    # Default: return first
    return destinations[0]['destination_string']
```

---

### Solution 4: Support Explicit Destination Parameter

Add an optional `destination` parameter to test execution tools:

```python
@mcp.tool()
def run_project_tests(
    project_path: str,
    tests_to_run: Optional[List[str]] = None,
    scheme: Optional[str] = None,
    destination: Optional[str] = None,  # ← New parameter
    max_wait_seconds: int = 300
) -> str:
    """
    Run tests with optional destination override.

    Args:
        destination: Optional destination string (e.g., "platform=iOS Simulator,name=iPhone 15 Pro")
                    If not provided, uses first available destination.
    """
    if not destination:
        # Auto-select first destination
        destinations = get_available_destinations(project_path, scheme)
        destination = destinations[0]['destination_string']

    # Use xcodebuild with -destination flag
    # ...
```

---

## Recommendations for Implementation

### For Selective Test Execution

1. **Query destinations** using `xcodebuild -showdestinations` (more reliable than AppleScript)
2. **Parse the output** to extract destination info
3. **Select first destination** as the default (or implement smarter selection logic)
4. **Build xcodebuild command**:
   ```bash
   xcodebuild test \
     -project <path> \
     -scheme <scheme> \
     -destination '<selected_destination>' \
     -only-testing:TestBundle/Class/testMethod
   ```

### For Future Enhancements

If a `get_active_destination` or `set_active_destination` tool is added:

- ✅ **DO**: List available destinations
- ✅ **DO**: Set destination via AppleScript (even though we can't read it back, it may affect Xcode's behavior)
- ❌ **DON'T**: Try to read `active run destination of workspaceDoc` - it doesn't work
- ✅ **DO**: Document that "active" destination is based on heuristics (first in list) rather than true active state

---

## Code Examples

### Complete Working Example: Get Destinations via xcodebuild

```python
import subprocess
import re
from typing import List, Dict, Optional

def get_available_destinations(project_path: str, scheme: str) -> List[Dict[str, str]]:
    """
    Get all available run destinations for a scheme.

    Args:
        project_path: Path to .xcodeproj or .xcworkspace
        scheme: Scheme name

    Returns:
        List of destination dictionaries with keys:
        - platform: e.g., "iOS Simulator", "macOS"
        - id: Device ID (if available)
        - name: Device name (if available)
        - os: OS version (if available)
        - destination_string: Formatted for -destination flag
    """
    # Determine project type
    is_workspace = project_path.endswith('.xcworkspace')
    flag = '-workspace' if is_workspace else '-project'

    # Run xcodebuild
    cmd = [
        'xcodebuild',
        '-showdestinations',
        flag,
        project_path,
        '-scheme',
        scheme
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"xcodebuild failed: {result.stderr}")

    # Parse destinations
    destinations = []
    pattern = r'\{\s*platform:([^,}]+)(?:,\s*(?:arch|id|OS|name):([^,}]+))*\s*\}'

    for line in result.stdout.split('\n'):
        if '{' in line and 'platform:' in line:
            # Extract key-value pairs
            dest = {}

            # Platform
            platform_match = re.search(r'platform:([^,}]+)', line)
            if platform_match:
                dest['platform'] = platform_match.group(1).strip()

            # ID
            id_match = re.search(r'id:([^,}]+)', line)
            if id_match:
                dest['id'] = id_match.group(1).strip()

            # Name
            name_match = re.search(r'name:([^}]+)', line)
            if name_match:
                dest['name'] = name_match.group(1).strip()

            # OS
            os_match = re.search(r'OS:([^,}]+)', line)
            if os_match:
                dest['os'] = os_match.group(1).strip()

            # Build destination string
            if dest.get('id'):
                dest['destination_string'] = f"id={dest['id']}"
            elif dest.get('name'):
                dest['destination_string'] = f"platform={dest['platform']},name={dest['name']}"
            else:
                dest['destination_string'] = f"platform={dest['platform']}"

            destinations.append(dest)

    return destinations


def get_default_destination(project_path: str, scheme: str) -> str:
    """
    Get the default (first) destination for a scheme.

    Returns:
        Destination string formatted for -destination flag
    """
    destinations = get_available_destinations(project_path, scheme)

    if not destinations:
        raise Exception(f"No destinations found for scheme {scheme}")

    return destinations[0]['destination_string']
```

### Usage Example

```python
# Get all destinations
destinations = get_available_destinations(
    "/path/to/MyApp.xcodeproj",
    "MyApp"
)

print(f"Found {len(destinations)} destinations:")
for dest in destinations:
    print(f"  - {dest['name']} ({dest['platform']})")
    print(f"    Use: -destination '{dest['destination_string']}'")

# Get default destination
default = get_default_destination(
    "/path/to/MyApp.xcodeproj",
    "MyApp"
)

# Run specific tests
subprocess.run([
    'xcodebuild', 'test',
    '-project', '/path/to/MyApp.xcodeproj',
    '-scheme', 'MyApp',
    '-destination', default,
    '-only-testing:MyAppTests/LoginTests/testValidLogin',
    '-only-testing:MyAppTests/LoginTests/testInvalidPassword'
])
```

---

## Conclusion

**Key Findings:**

1. ✅ We **CAN** list available run destinations via AppleScript and xcodebuild
2. ❌ We **CANNOT** query the "active" run destination via AppleScript (property always returns `missing value`)
3. ✅ We **CAN** work around this by using the first/default destination
4. ✅ This is **sufficient** to implement selective test execution

**Recommended Approach:**

- Use `xcodebuild -showdestinations` to query destinations (most reliable)
- Select the first destination as the default
- Optionally allow LLM/user to override with specific destination
- This enables `-only-testing:` functionality without needing to know the "active" destination

**Status of Selective Test Execution:**

**UNBLOCKED** - Can be implemented immediately with the workarounds documented above.
