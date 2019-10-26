#!/usr/bin/env python3
import base64
import email
import logging
import re
import sys
from datetime import datetime
from email import policy
from email.message import EmailMessage
from pprint import pprint
from unittest import TestCase


class EmailPage:
    def __init__(self,
                 id: str = None,
                 date: datetime = None,
                 sender: str = None,
                 subject: str = None,
                 content_type: str = None,
                 text: str = None,
                 ):
        self.id = id
        self.date = date
        self.sender = sender
        self.subject = subject
        self.content_type = content_type
        self.text = text

class Application:
    def __init__(self):
        self.log = logging.getLogger()

    def run(self):
        msg : EmailMessage = email.message_from_binary_file(sys.stdin.buffer, _class=EmailMessage, policy=policy.default)

        page = EmailPage()
        page.subject = str(msg["Subject"])
        page.id = msg['Message-ID']

        body=msg.get_body(("html", "plain"))
        body_encoding = body.get('Content-Type', 'text/plain; charset=UTF-8')
        cte = body.get('Content-Transfer-Encoding', 'plain')
        page.text = body.get_content()
        content_type, charset = self.get_content_type_and_charset(body_encoding)
        if isinstance(page.text, bytes) and charset != 'binary':
            page.text = page.text.decode(charset)
        page.content_type = content_type
        pprint(page.__dict__)

    @staticmethod
    def get_content_type_and_charset(content_type_header):
        full_type, charset =  content_type_header.split(';') if ';' in content_type_header else ('text/plain', 'charset=utf-8')
        match = re.match(r'charset="([^"])"', charset, re.IGNORECASE)
        charset = match.group(1) if match else 'utf-8'
        type, subtype = full_type.split('/')
        content_type = subtype if type == 'text' else 'binary'
        return content_type.lower(), charset.lower()


if __name__ == '__main__': Application().run()
