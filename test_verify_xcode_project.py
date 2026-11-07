"""Regressions for resolved PBX project paths, including Bitrise build 153."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('verify_xcode_project', ROOT / 'scripts/verify_xcode_project.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class GeneratedXcodeProjectTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project_directory = self.root / 'ios_app_dist/ci_xcode'
        self.project_directory.mkdir(parents=True)
        self.app_source = self.root / 'ios_app_dist/YourApp.swiftpm/App.swift'
        self.catalog = self.root / 'swift-verification/Sources/ControlCore/KeyboardCatalog.swift'
        for path in (self.app_source, self.catalog):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('// source\n')
        self.document = {
            'rootObject': 'PROJECT',
            'objects': {
                'PROJECT': {'isa': 'PBXProject', 'mainGroup': 'MAIN', 'projectDirPath': '', 'targets': ['APP']},
                'MAIN': {'isa': 'PBXGroup', 'sourceTree': '<group>', 'children': ['BUNDLE', 'CORE']},
                'BUNDLE': {'isa': 'PBXGroup', 'sourceTree': '<group>', 'path': '../YourApp.swiftpm', 'children': ['APP_FILE']},
                'CORE': {'isa': 'PBXGroup', 'sourceTree': '<group>', 'path': '../../swift-verification/Sources/ControlCore', 'children': ['CATALOG_FILE']},
                'APP_FILE': {'isa': 'PBXFileReference', 'sourceTree': '<group>', 'path': 'App.swift'},
                'CATALOG_FILE': {'isa': 'PBXFileReference', 'sourceTree': '<group>', 'path': 'KeyboardCatalog.swift'},
                'APP_BUILD': {'isa': 'PBXBuildFile', 'fileRef': 'APP_FILE'},
                'CATALOG_BUILD': {'isa': 'PBXBuildFile', 'fileRef': 'CATALOG_FILE'},
                'SOURCES': {'isa': 'PBXSourcesBuildPhase', 'files': ['APP_BUILD', 'CATALOG_BUILD']},
                'APP': {'isa': 'PBXNativeTarget', 'name': 'SuperCraftOS', 'buildPhases': ['SOURCES']},
            },
        }
        self.expected = {self.app_source, self.catalog}

    def validate(self):
        return verifier.validate_project(self.document, self.project_directory, self.expected)

    def test_external_groups_resolve_from_project_directory(self):
        self.assertEqual(self.validate(), {'targets': 1, 'inputs': 2})

    def test_build_153_duplicate_parent_graph_is_rejected(self):
        objects = self.document['objects']
        # Xcode reported ios_app_dist in both "git" and the main group.
        objects['MAIN']['children'] = ['GIT', 'IOS', 'CORE']
        objects['GIT'] = {'isa': 'PBXGroup', 'path': '../..', 'children': ['IOS']}
        objects['IOS'] = {'isa': 'PBXGroup', 'path': 'ios_app_dist', 'children': ['BUNDLE']}
        objects['BUNDLE']['path'] = 'YourApp.swiftpm'
        with self.assertRaisesRegex(verifier.ProjectValidationError, 'ios_app_dist: belongs to multiple groups'):
            self.validate()

    def test_build_153_repeated_prefix_is_rejected_even_without_duplicate_parent(self):
        self.document['objects']['BUNDLE']['path'] = 'ios_app_dist/YourApp.swiftpm'
        with self.assertRaisesRegex(verifier.ProjectValidationError, 'ci_xcode/ios_app_dist/YourApp.swiftpm/App.swift'):
            self.validate()

    def test_source_root_reference_does_not_inherit_group_path(self):
        source = self.document['objects']['APP_FILE']
        source.update(sourceTree='SOURCE_ROOT', path='../YourApp.swiftpm/App.swift')
        self.assertEqual(self.validate()['inputs'], 2)

    def test_catalog_can_be_compiled_by_multiple_targets_without_two_group_parents(self):
        objects = self.document['objects']
        objects['PROJECT']['targets'].append('KEYBOARD')
        objects['KEYBOARD'] = {'isa': 'PBXNativeTarget', 'name': 'Keyboard', 'buildPhases': ['KEYBOARD_SOURCES']}
        objects['KEYBOARD_SOURCES'] = {'isa': 'PBXSourcesBuildPhase', 'files': ['KEYBOARD_CATALOG_BUILD']}
        objects['KEYBOARD_CATALOG_BUILD'] = {'isa': 'PBXBuildFile', 'fileRef': 'CATALOG_FILE'}
        self.assertEqual(self.validate(), {'targets': 2, 'inputs': 3})

    def test_existing_but_uncompiled_app_source_is_rejected(self):
        self.document['objects']['SOURCES']['files'].remove('CATALOG_BUILD')
        with self.assertRaisesRegex(verifier.ProjectValidationError, 'App compile membership mismatch'):
            self.validate()

    def test_missing_resource_is_rejected(self):
        objects = self.document['objects']
        objects['MAIN']['children'].append('ASSETS')
        objects['ASSETS'] = {'isa': 'PBXFileReference', 'sourceTree': '<group>', 'path': 'Missing.xcassets'}
        objects['ASSET_BUILD'] = {'isa': 'PBXBuildFile', 'fileRef': 'ASSETS'}
        objects['RESOURCES'] = {'isa': 'PBXResourcesBuildPhase', 'files': ['ASSET_BUILD']}
        objects['APP']['buildPhases'].append('RESOURCES')
        with self.assertRaisesRegex(verifier.ProjectValidationError, 'missing PBXResourcesBuildPhase input'):
            self.validate()

    def test_duplicate_compile_input_is_rejected(self):
        objects = self.document['objects']
        objects['COPY_BUILD'] = copy.deepcopy(objects['APP_BUILD'])
        objects['SOURCES']['files'].append('COPY_BUILD')
        with self.assertRaisesRegex(verifier.ProjectValidationError, 'duplicate compile input'):
            self.validate()


if __name__ == '__main__':
    unittest.main()
