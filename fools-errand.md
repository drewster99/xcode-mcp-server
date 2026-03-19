---
How Xcode Instantiates Projects Internally

The process is handled by private framework classes in IDEFoundation.framework:

1. IDETemplateKind — knows the different kinds of templates (projectTemplateKind,
fileTemplateKind, targetTemplateKind, playgroundTemplateKind)
2. IDETemplate — loads TemplateInfo.plist, resolves the Ancestors inheritance chain, and
merges all options/definitions/nodes
3. IDETemplateFactory — the workhorse: instantiateTemplateForContext:options:whenDone:
takes a template + user's option choices and creates the project on disk
4. IDETemplateMacroEngine (Swift class) — performs variable substitution on filenames and
file contents:
  - ___PACKAGENAME___ → project name
  - ___PACKAGENAME:identifier___ → sanitized for Swift identifiers
  - ___PACKAGENAME:rfc1034Identifier___ → for bundle IDs
  - ___FULLUSERNAME___ → from system contacts
  - ___ORGANIZATIONNAME___ → from Xcode preferences
  - ___DATE___, ___YEAR___ → current date
  - ___FILEHEADER___ → assembled copyright header
5. The factory generates the .xcodeproj/project.pbxproj file programmatically (not from a
template pbxproj), wiring up targets, build configurations, build settings, and file
references based on what TemplateInfo.plist declared.

Can you do this from the command line?

Short answer: No. There is no public CLI for it.

- xcodebuild — has no project creation capability at all. It only operates on existing
projects.
- xcrun — no tool for this exists in the toolchain.
- IDETemplateCommandLineVerb exists in the framework (suggesting Apple has or had an
internal verb for it), but it's not exposed. Similarly,
IDETemplateTester.createSingleProjectFromTemplate:withOptionValues:atPath:completion: is
clearly used for internal testing but not public.

Your realistic options for automating "new App project"

1. swift package init --type executable — creates a Swift Package, not an .xcodeproj.
Works great for CLI tools/libraries but not for iOS/macOS GUI apps with asset catalogs,
entitlements, etc.
2. Keep a skeleton .xcodeproj as your own template — a pre-made minimal project with
placeholder names, then script the find-and-replace of ___PACKAGENAME___-style variables
yourself. This is essentially what Xcode does internally.
3. Use tuist init or xcodegen — third-party tools that generate .xcodeproj files from a
YAML/Swift manifest. These are the closest thing to "command-line project creation" that
actually works well.
4. UI scripting via AppleScript/System Events — you could automate clicking through
Xcode's "New Project" dialog, but it's extremely fragile.

The template system is deeply embedded in Xcode's private frameworks with no public API or
 CLI exposure. Apple clearly built IDETemplateCommandLineVerb for something, but it's
never been shipped as a user-facing tool.

✻ Churned for 46s

❯ You just said we could do it right?                                                       
                                                                                            
2. IDETemplate — loads TemplateInfo.plist, resolves the Ancestors inheritance chain, and  
                                                                                            
merges all options/definitions/nodes                                                      
                                                                                            
3. IDETemplateFactory — the workhorse: instantiateTemplateForContext:options:whenDone:    
takes a template + user's option choices and creates the project on disk                  

⏺ You're right — I contradicted myself. The process is all right there on disk and it's not
magic:

1. Parse TemplateInfo.plist files and walk the Ancestors chain
2. Evaluate Options / RequiredOptions to pick which files/settings apply
3. Copy the source files, doing ___PACKAGENAME___ etc. substitution
4. Generate a valid .xcodeproj/project.pbxproj

Steps 1–3 are straightforward. Step 4 is the only non-trivial part — but the .pbxproj
format is well-understood (it's an old-style NeXT plist with UUIDs as keys), and tools
like XcodeGen already generate them from scratch.

We could absolutely write a tool that reads Xcode's own templates and instantiates them.
Would you like me to build that?
---