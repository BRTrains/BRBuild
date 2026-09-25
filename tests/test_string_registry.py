import unittest

from Lang.StringRegistry import StringRegistry


class StringRegistryTests(unittest.TestCase):
    def test_identical_text_uses_one_canonical_string(self):
        registry = StringRegistry()

        first = registry.write_string("Class 153", "first_name", deduplicate=True)
        second = registry.write_string("Class 153", "second_group_name", deduplicate=True)

        self.assertEqual(first, "string(str_first_name)")
        self.assertEqual(second, first)
        self.assertEqual(len(registry), 1)
        self.assertEqual(list(registry.items()), [("str_first_name", "Class 153")])

    def test_cleaned_identical_text_is_also_deduplicated(self):
        registry = StringRegistry()

        first = registry.write_string("Class 153", "first_name", deduplicate=True)
        second = registry.write_string("Class (153),", "second_name", deduplicate=True)

        self.assertEqual(second, first)
        self.assertEqual(len(registry), 1)

    def test_different_text_remains_distinct(self):
        registry = StringRegistry()

        first = registry.write_string("Class 153", "first_name", deduplicate=True)
        second = registry.write_string("Class 155", "second_name", deduplicate=True)

        self.assertNotEqual(first, second)
        self.assertEqual(len(registry), 2)

    def test_deduplication_is_opt_in(self):
        registry = StringRegistry()

        first = registry.write_string("Class 153", "first_name")
        second = registry.write_string("Class 153", "second_name")

        self.assertNotEqual(first, second)
        self.assertEqual(len(registry), 2)

    def test_same_name_retains_existing_reference(self):
        registry = StringRegistry()

        first = registry.write_string("First", "vehicle_name")
        second = registry.write_string("Second", "vehicle_name")

        self.assertEqual(first, second)
        self.assertEqual(list(registry.items()), [("str_vehicle_name", "First")])


if __name__ == "__main__":
    unittest.main()