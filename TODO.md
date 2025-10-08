# TODO

## Planned Features & Fixes

### Testing & Discovery
- [ ] Add filesystem fallback to `get_xcode_projects` when mdfind returns empty results
- [ ] Implement selective test execution with `-only-testing` flag support
- [ ] Add `get_available_destinations` tool to query run destinations
- [ ] Create mock-based test suite that doesn't trigger Xcode UI alerts
- [ ] Fix test projects not being found immediately after creation (Spotlight indexing delay)

### Build & Run Enhancements
- [ ] Add destination parameter to `run_project_tests` for specific device/simulator targeting
- [ ] Support test filtering by class/method in `run_project_tests`
- [ ] Add timeout configuration for build and test operations
- [ ] Implement parallel test execution support

### Documentation & Quality
- [ ] Create CHANGELOG.md with version history
- [ ] Add ROADMAP.md for future feature planning
- [ ] Create TEST_GUIDE.md with comprehensive testing instructions
- [ ] Improve error messages with troubleshooting suggestions
- [ ] Document which operations require Xcode to be open vs closed

### Code Quality
- [ ] Add proper error handling for "Can't get workspace document" errors
- [ ] Improve AppleScript error messages with more context
- [ ] Add retry logic for transient Xcode automation failures
- [ ] Cache recent project paths to improve discovery speed

---

## Implementation Details

### Selective Test Execution (GET_RUN_DESTINATIONS research)

**Problem**: AppleScript's `test workspaceDoc` command doesn't support filtering specific tests. Need to use `xcodebuild test -only-testing:TestBundle/Class/testMethod`.

**Key Finding**: AppleScript's `active run destination of workspaceDoc` property always returns `missing value` - it's broken/unimplemented.

**Solution**: Use `xcodebuild -showdestinations` to get available destinations:
```bash
xcodebuild -showdestinations -project <path> -scheme <scheme>
# Returns: { platform:iOS Simulator, id:ABC123, OS:17.0, name:iPhone 15 Pro }
```

**Implementation approach**:
1. Query destinations using `xcodebuild -showdestinations`
2. Parse output to extract destination info
3. Select first destination as default (or let user specify)
4. Build xcodebuild command with `-destination` flag

Example code for parsing destinations:
```python
def get_available_destinations(project_path: str, scheme: str):
    is_workspace = project_path.endswith('.xcworkspace')
    flag = '-workspace' if is_workspace else '-project'

    cmd = ['xcodebuild', '-showdestinations', flag, project_path, '-scheme', scheme]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse: { platform:iOS Simulator, id:ABC123, name:iPhone 15 Pro }
    # Return: [{'platform': 'iOS Simulator', 'id': 'ABC123', 'destination_string': 'id=ABC123'}]
```

### Xcode Project Discovery Issues

**Problem**: `get_xcode_projects` uses mdfind (Spotlight) which has indexing delays for newly created/copied projects.

**Current behavior**:
- Tests copy projects to working directory
- mdfind doesn't immediately index these
- Projects aren't found, tests fail

**Solution**: Implement filesystem fallback
```python
def get_xcode_projects_with_fallback(search_path):
    # Try mdfind first (fast for indexed files)
    results = mdfind_projects(search_path)

    if not results and os.path.exists(search_path):
        # Fallback to os.walk for newly created projects
        results = []
        for root, dirs, files in os.walk(search_path):
            for d in dirs:
                if d.endswith(('.xcodeproj', '.xcworkspace')):
                    results.append(os.path.join(root, d))

    return results
```

### Test Infrastructure Notes

**Current test structure**:
```
test_projects/
├── fromXcode/           # Original projects from Xcode (DO NOT MODIFY)
├── templates/           # Modified copies for testing
│   ├── SimpleApp/       # Basic command line app
│   ├── BrokenApp/       # App with compile errors
│   └── ConsoleApp/      # App with console output
└── working/             # Temporary test execution
```

**Known issues**:
1. Build tests fail with "Can't get workspace document" when project not open
2. Xcode shows UI alerts about missing projects during tests
3. Some AppleScript commands require workspace to be loaded first

**Test runner fix that works**:
```python
# Set ALLOWED_FOLDERS in MCP module directly
import xcode_mcp_server.__main__ as mcp_server
mcp_server.ALLOWED_FOLDERS = {str(self.working_dir)}
```

### Build Error Handling

**Current implementation**: Returns JSON with structured errors/warnings
```json
{
    "full_log_path": "/tmp/xcode-mcp-server/logs/build-{hash}.txt",
    "summary": {"total_errors": N, "total_warnings": M},
    "errors_and_warnings": "error: ...\nwarning: ..."
}
```

**Improvements needed**:
- Better parsing of Swift vs Objective-C errors
- Group errors by file
- Extract fix-it suggestions

### Runtime Output Structure

**Current format**: JSON with intelligent filtering
```json
{
    "full_log_path": "/tmp/xcode-mcp-server/logs/runtime-{hash}.txt",
    "errors": ["error lines with context"],
    "warnings": ["warning lines with context"],
    "matching_lines": ["lines matching regex filter"],
    "summary": {"total_lines": N, "errors": X, "warnings": Y}
}
```

**Note**: Errors and warnings are always included with full context, never lost to filtering.

### Recent Projects Support

**Already implemented** in `get_xcode_projects`:
- Reads from `~/Library/Preferences/com.apple.dt.Xcode.plist`
- `IDERecentProjectDocumentURLs` key contains recent projects
- Shown first in results when `include_recents=True`

### Notification System Status

**Decision**: Not implementing typed notification system from NOTIFICATIONS_PLAN.md

**Current state**:
- Simple notification functions in `utils/applescript.py`
- All notifications use "Drew's Xcode MCP" title
- Global `NOTIFICATIONS_ENABLED` flag works
- History tracking implemented for debugging

### Important File Paths

**xcresult bundles**:
- Runtime logs: `~/Library/Developer/Xcode/DerivedData/*/Logs/Launch/*.xcresult`
- Test results: `~/Library/Developer/Xcode/DerivedData/*/Logs/Test/*.xcresult`
- Build logs: Captured directly from Xcode UI via AppleScript

**Parsing xcresults**:
```bash
# Get runtime console output
xcrun xcresulttool get --path <xcresult> --id <logRef_id>

# Get test results
xcrun xcresulttool get --path <xcresult> --format json
```

### AppleScript Gotchas

1. **Workspace loading**: Must wait for `loaded of workspaceDoc is true`
2. **String escaping**: Backslashes and quotes must be escaped
3. **Build/test results**: Check `completed of buildResult is true` in loop
4. **Project paths**: Remove trailing slashes, use absolute paths
5. **Timeout handling**: AppleScript operations can hang, need subprocess timeouts

### Security Model

**Current implementation**:
- `ALLOWED_FOLDERS` environment variable or CLI args
- All paths validated: absolute, exist, directory, no '..'
- Default to `$HOME` if not specified
- Every tool validates project path against allowed folders