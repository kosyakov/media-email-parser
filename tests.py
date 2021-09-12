from unittest import TestCase

from email2html import StdinParser


class TestMe(TestCase):
    def test_charset_detection(self):
        self.assertEqual(('plain', 'utf-8'), StdinParser.get_content_type_and_charset("text/plain; charset=UTF-8"))


class AddNumber:
    def __init__(this, number_to_add: int):
        this.number_to_add = number_to_add

    def apply_to(this, some_number: int):
        return some_number + this.number_to_add


def add_number(number_to_add):
    def fn2(some_number):
        return some_number + number_to_add
    return fn2

class TestNonClosureParametrisation(TestCase):
    def test_me(self):
        add22 =  AddNumber(22)
        x = add22.apply_to(12)
        self.assertEqual(34, x)
        add14 = AddNumber(14)
        y = add14.apply_to(3)
        self.assertEqual(17, y)
        z = add_number(22)(12)
        self.assertEqual(34, z)


from unittest import TestCase


def isPalindrome(a_string: str):
    symbol_maps = {'e' : 'éèê', 'a': 'à'}
    spaces = " !.?,'"+'"'
    canonised_string = a_string.lower()
    for s in spaces:
        canonised_string = canonised_string.replace(s,'')
    for canonical_symbol, alternative_symbols in symbol_maps.items():
        for s in alternative_symbols:
            canonised_string = canonised_string.replace(s, canonical_symbol)
    return canonised_string == canonised_string[::-1]

class TestPython(TestCase):
    def test_palindrome(self):
        self.assertTrue(isPalindrome("L'ami naturel ? Le rut animal."))
        self.assertTrue(isPalindrome('un radar nu'))
        self.assertTrue(isPalindrome("À l'émir, Asimov a vomi sa rime, là"))
        self.assertTrue(isPalindrome('Ta bête te bat'))
        self.assertTrue(isPalindrome('Die Liebe ist Sieger, rege ist sie bei Leid'))
        self.assertTrue(isPalindrome('Now, Sir, even Hannah never is won'))
        self.assertTrue(isPalindrome('Лёша на полке клопа нашёл'))
        self.assertFalse(isPalindrome('asdf'))

    def test_reversed_int(self):
        self.assertEqual(41, self.reverse_int(14))

    def reverse_int(self, inpt: int):
        return int(str(inpt)[::-1])

    def test_factorial(self):
        num = 4
        factorial = 1
        count = 1
        while count <= num:
            factorial *= count
            count +=1
        print(num, "! = ", factorial)