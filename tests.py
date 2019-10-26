from unittest import TestCase

from email2html import Application


class TestMe(TestCase):
    def test_charset_detection(self):
        self.assertEqual(('plain', 'utf-8'), Application.get_content_type_and_charset("text/plain; charset=UTF-8"))

