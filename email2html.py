#!/usr/bin/env python3
import base64
import email
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Iterable


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

    def __repr__(self):
        return f'EmailPage({self.id[:20]}, {self.subject}, from {self.sender})'


class IPageRegistry:  # interface
    def save_page(self, page: EmailPage):
        raise NotImplementedError()

    def get_recent_pages(self) -> Iterable[EmailPage]:
        raise NotImplementedError()


class IPageParser:
    def get_page(self) -> EmailPage:
        raise NotImplementedError()


class ISiteBuilder:
    def build_site(self, pages: Iterable[EmailPage]):
        raise NotImplementedError()


class StdinParser(IPageParser):
    def get_page(self) -> EmailPage:
        msg: EmailMessage = email.message_from_binary_file(sys.stdin.buffer, _class=EmailMessage, policy=policy.default)

        page = EmailPage()
        page.id = msg['Message-ID'].strip('<>')
        page.date = parsedate_to_datetime(msg['Date'])
        page.sender = str(msg['From'])
        page.subject = str(msg["Subject"])
        body = msg.get_body(("html", "plain"))
        body_encoding = body.get('Content-Type', 'text/plain; charset=UTF-8')
        page.text = body.get_content()
        content_type, charset = self.get_content_type_and_charset(body_encoding)
        if isinstance(page.text, bytes) and charset != 'binary':
            page.text = page.text.decode(charset)
        page.content_type = content_type
        return page

    @staticmethod
    def get_content_type_and_charset(content_type_header):
        full_type, charset = content_type_header.split(';') if ';' in content_type_header else ('text/plain', 'charset=utf-8')
        match = re.match(r'charset="([^"])"', charset, re.IGNORECASE)
        charset = match.group(1) if match else 'utf-8'
        type, subtype = full_type.split('/')
        content_type = subtype if type == 'text' else 'binary'
        return content_type.lower(), charset.lower()


class StaticHtmlSiteBuilder(ISiteBuilder):
    def __init__(self, output_directory: str):
        self._output_directory = output_directory
        self.log = logging.getLogger(__class__.__name__)

    def build_site(self, pages: Iterable[EmailPage]):
        self.log.debug(f'Creating a static site in "{self._output_directory}"')
        os.makedirs(self._output_directory, exist_ok=True)
        index_lines = []
        index_lines.append(f"""
        <!doctype html><html lang="en">
        <head>
          <meta charset="utf-8">
          <title>News {datetime.now().strftime("%Y-%m-%d %H:%M")}</title>
        <style>
        * {{ line-height:200%;}}
        </style>
        </head>
        <body>
        <ul>
        """)
        n = 0
        for page in pages:
            filename = self.save_page_to_a_file(page)
            index_lines.append(f"""
            <li>
                {page.sender}: <a href="./{filename}">{page.subject}</a> <br/> {page.date.strftime('%A, %d %b, %Y %H:%M')}  
            </li>
            """)
            n += 1

        index_lines.append("""
        </ul>
        </body></html>
        """)
        self.log.debug(f"Writing index file with list of {n} pages ")
        with open(os.path.join(self._output_directory, 'index.html'), 'wb') as f:
            f.writelines(l.encode('utf-8') for l in index_lines)

    def save_page_to_a_file(self, page):
        filename = page.id.replace('@', '').replace('.', '') + '.html'
        with open(os.path.join(self._output_directory, filename), 'w') as f:
            f.write(page.text)
        return filename


class SQLitePageRegistry(IPageRegistry):
    def __init__(self, path_to_file: str, recent_period_days : int = 15):
        self._recent_period_days = recent_period_days
        self._path_to_file = path_to_file
        self.log = logging.getLogger(__class__.__name__)
        self.log.debug(f'Setting up sqlite-based registry in "{self._path_to_file}"')
        self.connection = sqlite3.connect(self._path_to_file)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS page(
                 id TEXT PRIMARY KEY,
                 message_timestamp INTEGER,
                 sender TEXT,
                 subject TEXT,
                 content_type TEXT,
                 body BLOB
            );
            """)

    def save_page(self, page: EmailPage):
        self.log.debug(f'Saving page {page}')
        with self.connection:
            try:
                self.connection.execute("""
                INSERT INTO page(id, message_timestamp, sender, subject, content_type, body)
                VALUES(:id, :message_timestamp, :sender, :subject, :content_type, :body)
                """, {
                    'id': page.id,
                    'message_timestamp': int(page.date.timestamp()),
                    'sender': page.sender,
                    'subject': page.subject,
                    'content_type': page.content_type,
                    'body': page.text}
                                        )
            except sqlite3.IntegrityError as e:
                self.log.debug(f'Failed saving page {page}: {e}')

    def get_recent_pages(self) -> Iterable[EmailPage]:
        last_datetime = (datetime.now() - timedelta(days=self._recent_period_days))
        oldest_ts = int(last_datetime.timestamp())
        self.log.debug(f"Getting all pages since {last_datetime} = {oldest_ts}")
        with self.connection:
            for row in self.connection.execute("SELECT * FROM page WHERE message_timestamp > ? ORDER BY message_timestamp DESC", (oldest_ts,)):
                yield EmailPage(
                    id=row['id'],
                    date=datetime.fromtimestamp(row['message_timestamp']),
                    sender=row['sender'],
                    subject=row['subject'],
                    content_type=row['content_type'],
                    text=row['body']
                )


class Application:
    def __init__(self):
        self.logger = logging.getLogger(__class__.__name__)
        self.logger.debug("Starting the application")
        self._create_options()
        self.parser: IPageParser = StdinParser()
        self.registry: IPageRegistry = SQLitePageRegistry(self.OPTIONS.database, recent_period_days=self.OPTIONS.days)
        self.site_builder: ISiteBuilder = StaticHtmlSiteBuilder(self.OPTIONS.output)

    def run(self):
        page = self.parser.get_page()
        self.registry.save_page(page)
        pages = list(self.registry.get_recent_pages())
        self.site_builder.build_site(pages)

    def _create_options(self):
        import argparse
        parser = argparse.ArgumentParser(description='News digest builder')
        parser.add_argument('-o', '--output', metavar="output_dir", help="output folder", required=True)
        parser.add_argument('-d', '--database', metavar="db_file", help="database file location", required=True)
        parser.add_argument('-D', '--days', metavar="days_ago", type=int, help="days to include into index", required=True)
        self.OPTIONS = parser.parse_args()
        self.logger.debug(f'Running with options {self.OPTIONS}')


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stderr))
    Application().run()
