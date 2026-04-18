#!/usr/bin/env python3
"""Project template generation for creating new Xcode projects."""

import os
import re
import uuid
from typing import Optional


def generate_xcode_id() -> str:
    """Generate a 24-character uppercase hex string matching Xcode's UUID format."""
    return uuid.uuid4().hex[:24].upper()


def sanitize_to_identifier(name: str) -> str:
    """
    Convert a project name to a valid Swift identifier.
    "My Cool App" -> "MyCoolApp", "hello-world" -> "helloworld"
    """
    # Remove anything that isn't alphanumeric or whitespace/hyphen/underscore
    cleaned = re.sub(r'[^A-Za-z0-9 _-]', '', name)
    # Split on separators, capitalize each word, join
    parts = re.split(r'[ _-]+', cleaned)
    result = parts[0] + ''.join(p.capitalize() for p in parts[1:])
    # Ensure starts with a letter
    if result and not result[0].isalpha():
        result = 'App' + result
    return result


# --- pbxproj template ---
# Based on objectVersion 77 (Xcode 16+) with PBXFileSystemSynchronizedRootGroup.
# Placeholders use Python .format() style: {name}
# Curly braces in the pbxproj itself are doubled: {{ }}

PBXPROJ_TEMPLATE = """\
// !$*UTF8*$!
{{
\tarchiveVersion = 1;
\tclasses = {{
\t}};
\tobjectVersion = 77;
\tobjects = {{

/* Begin PBXFileReference section */
\t\t{id_product_ref} /* {project_name}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = {project_name}.app; sourceTree = BUILT_PRODUCTS_DIR; }};
/* End PBXFileReference section */

/* Begin PBXFileSystemSynchronizedRootGroup section */
\t\t{id_sync_group} /* {project_name} */ = {{
\t\t\tisa = PBXFileSystemSynchronizedRootGroup;
\t\t\tpath = {project_name};
\t\t\tsourceTree = "<group>";
\t\t}};
/* End PBXFileSystemSynchronizedRootGroup section */

/* Begin PBXFrameworksBuildPhase section */
\t\t{id_frameworks_phase} /* Frameworks */ = {{
\t\t\tisa = PBXFrameworksBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
\t\t{id_main_group} = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{id_sync_group} /* {project_name} */,
\t\t\t\t{id_products_group} /* Products */,
\t\t\t);
\t\t\tsourceTree = "<group>";
\t\t}};
\t\t{id_products_group} /* Products */ = {{
\t\t\tisa = PBXGroup;
\t\t\tchildren = (
\t\t\t\t{id_product_ref} /* {project_name}.app */,
\t\t\t);
\t\t\tname = Products;
\t\t\tsourceTree = "<group>";
\t\t}};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
\t\t{id_native_target} /* {project_name} */ = {{
\t\t\tisa = PBXNativeTarget;
\t\t\tbuildConfigurationList = {id_target_config_list} /* Build configuration list for PBXNativeTarget "{project_name}" */;
\t\t\tbuildPhases = (
\t\t\t\t{id_sources_phase} /* Sources */,
\t\t\t\t{id_frameworks_phase} /* Frameworks */,
\t\t\t\t{id_resources_phase} /* Resources */,
\t\t\t);
\t\t\tbuildRules = (
\t\t\t);
\t\t\tdependencies = (
\t\t\t);
\t\t\tfileSystemSynchronizedGroups = (
\t\t\t\t{id_sync_group} /* {project_name} */,
\t\t\t);
\t\t\tname = {project_name};
\t\t\tpackageProductDependencies = (
\t\t\t);
\t\t\tproductName = {project_name};
\t\t\tproductReference = {id_product_ref} /* {project_name}.app */;
\t\t\tproductType = "com.apple.product-type.application";
\t\t}};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
\t\t{id_project} /* Project object */ = {{
\t\t\tisa = PBXProject;
\t\t\tattributes = {{
\t\t\t\tBuildIndependentTargetsInParallel = 1;
\t\t\t\tLastSwiftUpdateCheck = 1600;
\t\t\t\tLastUpgradeCheck = 1600;
\t\t\t\tTargetAttributes = {{
\t\t\t\t\t{id_native_target} = {{
\t\t\t\t\t\tCreatedOnToolsVersion = 16.0;
\t\t\t\t\t}};
\t\t\t\t}};
\t\t\t}};
\t\t\tbuildConfigurationList = {id_project_config_list} /* Build configuration list for PBXProject "{project_name}" */;
\t\t\tdevelopmentRegion = en;
\t\t\thasScannedForEncodings = 0;
\t\t\tknownRegions = (
\t\t\t\ten,
\t\t\t\tBase,
\t\t\t);
\t\t\tmainGroup = {id_main_group};
\t\t\tminimizedProjectReferenceProxies = 1;
\t\t\tpreferredProjectObjectVersion = 77;
\t\t\tproductRefGroup = {id_products_group} /* Products */;
\t\t\tprojectDirPath = "";
\t\t\tprojectRoot = "";
\t\t\ttargets = (
\t\t\t\t{id_native_target} /* {project_name} */,
\t\t\t);
\t\t}};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
\t\t{id_resources_phase} /* Resources */ = {{
\t\t\tisa = PBXResourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
\t\t{id_sources_phase} /* Sources */ = {{
\t\t\tisa = PBXSourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
\t\t{id_project_debug} /* Debug */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;
\t\t\t\tASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS = YES;
\t\t\t\tCLANG_ANALYZER_NONNULL = YES;
\t\t\t\tCLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
\t\t\t\tCLANG_ENABLE_MODULES = YES;
\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;
\t\t\t\tCLANG_ENABLE_OBJC_WEAK = YES;
\t\t\t\tCLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
\t\t\t\tCLANG_WARN_BOOL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_COMMA = YES;
\t\t\t\tCLANG_WARN_CONSTANT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
\t\t\t\tCLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
\t\t\t\tCLANG_WARN_DOCUMENTATION_COMMENTS = YES;
\t\t\t\tCLANG_WARN_EMPTY_BODY = YES;
\t\t\t\tCLANG_WARN_ENUM_CONVERSION = YES;
\t\t\t\tCLANG_WARN_INFINITE_RECURSION = YES;
\t\t\t\tCLANG_WARN_INT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
\t\t\t\tCLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
\t\t\t\tCLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
\t\t\t\tCLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
\t\t\t\tCLANG_WARN_STRICT_PROTOTYPES = YES;
\t\t\t\tCLANG_WARN_SUSPICIOUS_MOVE = YES;
\t\t\t\tCLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
\t\t\t\tCLANG_WARN_UNREACHABLE_CODE = YES;
\t\t\t\tCLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
\t\t\t\tCOPY_PHASE_STRIP = NO;
\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;
\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;
\t\t\t\tENABLE_TESTABILITY = YES;
\t\t\t\tENABLE_USER_SCRIPT_SANDBOXING = YES;
\t\t\t\tGCC_C_LANGUAGE_STANDARD = gnu17;
\t\t\t\tGCC_DYNAMIC_NO_PIC = NO;
\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;
\t\t\t\tGCC_OPTIMIZATION_LEVEL = 0;
\t\t\t\tGCC_PREPROCESSOR_DEFINITIONS = (
\t\t\t\t\t"DEBUG=1",
\t\t\t\t\t"$(inherited)",
\t\t\t\t);
\t\t\t\tGCC_WARN_64_TO_32_BIT_CONVERSION = YES;
\t\t\t\tGCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
\t\t\t\tGCC_WARN_UNDECLARED_SELECTOR = YES;
\t\t\t\tGCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
\t\t\t\tGCC_WARN_UNUSED_FUNCTION = YES;
\t\t\t\tGCC_WARN_UNUSED_VARIABLE = YES;
{project_debug_platform_settings}\t\t\t\tLOCALIZATION_PREFERS_STRING_CATALOGS = YES;
\t\t\t\tMTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
\t\t\t\tMTL_FAST_MATH = YES;
\t\t\t\tONLY_ACTIVE_ARCH = YES;
\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = "DEBUG $(inherited)";
\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = "-Onone";
\t\t\t}};
\t\t\tname = Debug;
\t\t}};
\t\t{id_project_release} /* Release */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;
\t\t\t\tASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS = YES;
\t\t\t\tCLANG_ANALYZER_NONNULL = YES;
\t\t\t\tCLANG_ANALYZER_NUMBER_OBJECT_CONVERSION = YES_AGGRESSIVE;
\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
\t\t\t\tCLANG_ENABLE_MODULES = YES;
\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;
\t\t\t\tCLANG_ENABLE_OBJC_WEAK = YES;
\t\t\t\tCLANG_WARN_BLOCK_CAPTURE_AUTORELEASING = YES;
\t\t\t\tCLANG_WARN_BOOL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_COMMA = YES;
\t\t\t\tCLANG_WARN_CONSTANT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_DEPRECATED_OBJC_IMPLEMENTATIONS = YES;
\t\t\t\tCLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
\t\t\t\tCLANG_WARN_DOCUMENTATION_COMMENTS = YES;
\t\t\t\tCLANG_WARN_EMPTY_BODY = YES;
\t\t\t\tCLANG_WARN_ENUM_CONVERSION = YES;
\t\t\t\tCLANG_WARN_INFINITE_RECURSION = YES;
\t\t\t\tCLANG_WARN_INT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_NON_LITERAL_NULL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_OBJC_IMPLICIT_RETAIN_SELF = YES;
\t\t\t\tCLANG_WARN_OBJC_LITERAL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
\t\t\t\tCLANG_WARN_QUOTED_INCLUDE_IN_FRAMEWORK_HEADER = YES;
\t\t\t\tCLANG_WARN_RANGE_LOOP_ANALYSIS = YES;
\t\t\t\tCLANG_WARN_STRICT_PROTOTYPES = YES;
\t\t\t\tCLANG_WARN_SUSPICIOUS_MOVE = YES;
\t\t\t\tCLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
\t\t\t\tCLANG_WARN_UNREACHABLE_CODE = YES;
\t\t\t\tCLANG_WARN__DUPLICATE_METHOD_MATCH = YES;
\t\t\t\tCOPY_PHASE_STRIP = NO;
\t\t\t\tDEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
\t\t\t\tENABLE_NS_ASSERTIONS = NO;
\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;
\t\t\t\tENABLE_USER_SCRIPT_SANDBOXING = YES;
\t\t\t\tGCC_C_LANGUAGE_STANDARD = gnu17;
\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;
\t\t\t\tGCC_WARN_64_TO_32_BIT_CONVERSION = YES;
\t\t\t\tGCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
\t\t\t\tGCC_WARN_UNDECLARED_SELECTOR = YES;
\t\t\t\tGCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
\t\t\t\tGCC_WARN_UNUSED_FUNCTION = YES;
\t\t\t\tGCC_WARN_UNUSED_VARIABLE = YES;
{project_release_platform_settings}\t\t\t\tLOCALIZATION_PREFERS_STRING_CATALOGS = YES;
\t\t\t\tMTL_ENABLE_DEBUG_INFO = NO;
\t\t\t\tMTL_FAST_MATH = YES;
\t\t\t\tSWIFT_COMPILATION_MODE = wholemodule;
\t\t\t\tVALIDATE_PRODUCT = YES;
\t\t\t}};
\t\t\tname = Release;
\t\t}};
\t\t{id_target_debug} /* Debug */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
\t\t\t\tASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tENABLE_PREVIEWS = YES;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
{target_debug_platform_settings}\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (
\t\t\t\t\t"$(inherited)",
\t\t\t\t\t"{ld_runpath}",
\t\t\t\t);
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = {bundle_identifier};
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;
\t\t\t\tSWIFT_VERSION = 6.0;
\t\t\t\t{targeted_device_family_line}}};
\t\t\tname = Debug;
\t\t}};
\t\t{id_target_release} /* Release */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
\t\t\t\tASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tENABLE_PREVIEWS = YES;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
{target_release_platform_settings}\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (
\t\t\t\t\t"$(inherited)",
\t\t\t\t\t"{ld_runpath}",
\t\t\t\t);
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = {bundle_identifier};
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;
\t\t\t\tSWIFT_VERSION = 6.0;
\t\t\t\t{targeted_device_family_line}}};
\t\t\tname = Release;
\t\t}};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
\t\t{id_project_config_list} /* Build configuration list for PBXProject "{project_name}" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t{id_project_debug} /* Debug */,
\t\t\t\t{id_project_release} /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};
\t\t{id_target_config_list} /* Build configuration list for PBXNativeTarget "{project_name}" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t{id_target_debug} /* Debug */,
\t\t\t\t{id_target_release} /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};
/* End XCConfigurationList section */
\t}};
\trootObject = {id_project} /* Project object */;
}}
"""

WORKSPACE_DATA_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<Workspace
   version = "1.0">
   <FileRef
      location = "self:">
   </FileRef>
</Workspace>
"""

APP_SWIFT_TEMPLATE = """\
import SwiftUI

@main
struct {identifier}App: App {{
    var body: some Scene {{
        WindowGroup {{
            ContentView()
        }}
    }}
}}
"""

CONTENT_VIEW_TEMPLATE = """\
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Image(systemName: "globe")
                .imageScale(.large)
                .foregroundStyle(.tint)
            Text("Hello, world!")
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
"""

ASSETS_CONTENTS_JSON = """\
{
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
"""

ACCENT_COLOR_CONTENTS_JSON = """\
{
  "colors" : [
    {
      "idiom" : "universal"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
"""

APP_ICON_IOS_CONTENTS_JSON = """\
{
  "images" : [
    {
      "idiom" : "universal",
      "platform" : "ios",
      "size" : "1024x1024"
    },
    {
      "appearances" : [
        {
          "appearance" : "luminosity",
          "value" : "dark"
        }
      ],
      "idiom" : "universal",
      "platform" : "ios",
      "size" : "1024x1024"
    },
    {
      "appearances" : [
        {
          "appearance" : "luminosity",
          "value" : "tinted"
        }
      ],
      "idiom" : "universal",
      "platform" : "ios",
      "size" : "1024x1024"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
"""

APP_ICON_MACOS_CONTENTS_JSON = """\
{
  "images" : [
    {
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "16x16"
    },
    {
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "16x16"
    },
    {
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "32x32"
    },
    {
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "32x32"
    },
    {
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "128x128"
    },
    {
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "128x128"
    },
    {
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "256x256"
    },
    {
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "256x256"
    },
    {
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "512x512"
    },
    {
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "512x512"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
"""


def _ios_project_platform_settings(deployment_target: str) -> str:
    """Project-level platform settings for iOS (Debug and Release share the same)."""
    return (
        f"\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = {deployment_target};\n"
        f"\t\t\t\tSDKROOT = iphoneos;\n"
    )


def _macos_project_platform_settings(deployment_target: str) -> str:
    """Project-level platform settings for macOS."""
    return (
        f"\t\t\t\tMACOSX_DEPLOYMENT_TARGET = {deployment_target};\n"
        f"\t\t\t\tSDKROOT = macosx;\n"
    )


def _ios_target_platform_settings() -> str:
    """Target-level platform settings for iOS."""
    return (
        "\t\t\t\tINFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;\n"
        "\t\t\t\tINFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;\n"
        "\t\t\t\tINFOPLIST_KEY_UILaunchScreen_Generation = YES;\n"
        '\t\t\t\tINFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";\n'
        '\t\t\t\tINFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";\n'
    )


def _macos_target_platform_settings() -> str:
    """Target-level platform settings for macOS."""
    return ""


def generate_project(
    parent_dir: str,
    project_name: str,
    platform: str = "ios",
    bundle_identifier: Optional[str] = None,
    deployment_target: Optional[str] = None,
) -> dict:
    """
    Generate a complete Xcode project on disk.

    Args:
        parent_dir: Validated parent directory (must already exist)
        project_name: Name of the project
        platform: "ios" or "macos"
        bundle_identifier: Bundle ID, defaults to com.example.{identifier}
        deployment_target: Deployment target version, defaults to "26.0"

    Returns:
        Dict with project_path, project_directory, and files_created
    """
    identifier = sanitize_to_identifier(project_name)
    if not bundle_identifier:
        bundle_identifier = f"com.example.{identifier}"
    if not deployment_target:
        deployment_target = "26.0"

    # Generate all UUIDs
    ids = {
        'id_main_group': generate_xcode_id(),
        'id_products_group': generate_xcode_id(),
        'id_product_ref': generate_xcode_id(),
        'id_sync_group': generate_xcode_id(),
        'id_sources_phase': generate_xcode_id(),
        'id_frameworks_phase': generate_xcode_id(),
        'id_resources_phase': generate_xcode_id(),
        'id_native_target': generate_xcode_id(),
        'id_project': generate_xcode_id(),
        'id_project_config_list': generate_xcode_id(),
        'id_project_debug': generate_xcode_id(),
        'id_project_release': generate_xcode_id(),
        'id_target_config_list': generate_xcode_id(),
        'id_target_debug': generate_xcode_id(),
        'id_target_release': generate_xcode_id(),
    }

    # Platform-specific settings
    if platform == "macos":
        project_debug_platform = _macos_project_platform_settings(deployment_target)
        project_release_platform = _macos_project_platform_settings(deployment_target)
        target_debug_platform = _macos_target_platform_settings()
        target_release_platform = _macos_target_platform_settings()
        ld_runpath = "@executable_path/../Frameworks"
        targeted_device_family_line = ""
        app_icon_json = APP_ICON_MACOS_CONTENTS_JSON
    else:
        project_debug_platform = _ios_project_platform_settings(deployment_target)
        project_release_platform = _ios_project_platform_settings(deployment_target)
        target_debug_platform = _ios_target_platform_settings()
        target_release_platform = _ios_target_platform_settings()
        ld_runpath = "@executable_path/Frameworks"
        targeted_device_family_line = 'TARGETED_DEVICE_FAMILY = "1,2";\n\t\t\t'
        app_icon_json = APP_ICON_IOS_CONTENTS_JSON

    # Fill in the pbxproj template
    pbxproj_content = PBXPROJ_TEMPLATE.format(
        project_name=project_name,
        bundle_identifier=bundle_identifier,
        ld_runpath=ld_runpath,
        targeted_device_family_line=targeted_device_family_line,
        project_debug_platform_settings=project_debug_platform,
        project_release_platform_settings=project_release_platform,
        target_debug_platform_settings=target_debug_platform,
        target_release_platform_settings=target_release_platform,
        **ids,
    )

    # Create directory structure
    project_dir = os.path.join(parent_dir, project_name)
    xcodeproj_dir = os.path.join(project_dir, f"{project_name}.xcodeproj")
    workspace_dir = os.path.join(xcodeproj_dir, "project.xcworkspace")
    source_dir = os.path.join(project_dir, project_name)
    assets_dir = os.path.join(source_dir, "Assets.xcassets")
    accent_color_dir = os.path.join(assets_dir, "AccentColor.colorset")
    app_icon_dir = os.path.join(assets_dir, "AppIcon.appiconset")

    for d in [workspace_dir, accent_color_dir, app_icon_dir]:
        os.makedirs(d, exist_ok=True)

    # Write all files
    files_created = []

    def write_file(path: str, content: str):
        with open(path, 'w') as f:
            f.write(content)
        # Store relative path from project_dir
        files_created.append(os.path.relpath(path, project_dir))

    write_file(os.path.join(xcodeproj_dir, "project.pbxproj"), pbxproj_content)
    write_file(os.path.join(workspace_dir, "contents.xcworkspacedata"), WORKSPACE_DATA_TEMPLATE)
    write_file(
        os.path.join(source_dir, f"{identifier}App.swift"),
        APP_SWIFT_TEMPLATE.format(identifier=identifier),
    )
    write_file(os.path.join(source_dir, "ContentView.swift"), CONTENT_VIEW_TEMPLATE)
    write_file(os.path.join(assets_dir, "Contents.json"), ASSETS_CONTENTS_JSON)
    write_file(os.path.join(accent_color_dir, "Contents.json"), ACCENT_COLOR_CONTENTS_JSON)
    write_file(os.path.join(app_icon_dir, "Contents.json"), app_icon_json)

    return {
        "project_path": os.path.join(project_dir, f"{project_name}.xcodeproj"),
        "project_directory": project_dir,
        "files_created": files_created,
    }
