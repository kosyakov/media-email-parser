from unittest import TestCase

from email2html import StdinParser


class TestMe(TestCase):
    def test_charset_detection(self):
        self.assertEqual(('plain', 'utf-8'), StdinParser.get_content_type_and_charset("text/plain; charset=UTF-8"))

