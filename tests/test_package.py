"""Basic package metadata tests."""

import unittest

import veranav


class PackageMetadataTest(unittest.TestCase):
    """Validate the initial public package interface."""

    def test_version(self) -> None:
        self.assertEqual(veranav.__version__, "0.1.0")

    def test_public_exports(self) -> None:
        self.assertEqual(veranav.__all__, ["__version__"])


if __name__ == "__main__":
    unittest.main()
