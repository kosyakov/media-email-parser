#!/usr/bin/env python3
import html
import email
import logging
import os
import pickle
import re
import sqlite3
import sys
import traceback
from datetime import datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Iterable, Tuple, List


class EmailPage:
    def __init__(self,
                 id: str = None,
                 date: datetime = None,
                 sender: str = None,
                 subject: str = None,
                 content_type: str = None,
                 headers: List[Tuple[str, str]] = None,
                 text: str = None,
                 ):
        self.id = id
        self.date = date
        self.sender = sender
        self.subject = subject
        self.content_type = content_type
        self.headers: List[Tuple[str, str]] = headers if headers else []
        self.text = text

    def __repr__(self):
        return f'EmailPage({self.id}, {self.subject}, from {self.sender})'


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
    def __init__(self):
        self.log = logging.getLogger(__class__.__name__)


    def get_page(self) -> EmailPage:
        self.log.debug("Going to read a message from stdin")
        lines = [l for l in sys.stdin]
        self.log.debug(f'Got {len(lines)} lines, the first one is {lines[0].strip()}')
        while not self.is_a_header_line(lines[0]):
            lines.pop(0)
            self.log.debug(f"Removed the first line, left with {len(lines)} lines")
        msg: EmailMessage = email.message_from_string(''.join(lines), _class=EmailMessage, policy=policy.default)
        self.log.debug(f'Parsed email message from {len(lines)} line with {len(msg.defects)} defects')
        page = EmailPage()
        page.date = parsedate_to_datetime(msg['Date']) if msg['Date'] else datetime.now()
        page.sender = str(msg['From'])
        page.subject = str(msg["Subject"])
        page.id = msg['Message-ID'].strip('<>')
        page.headers = msg.items()
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
        full_type, charset = content_type_header.split(';', 1) if ';' in content_type_header else ('text/plain', 'charset=utf-8')
        match = re.match(r'charset="([^"])"', charset, re.IGNORECASE)
        charset = match.group(1) if match else 'utf-8'
        type, subtype = full_type.split('/')
        content_type = subtype if type == 'text' else 'binary'
        return content_type.lower(), charset.lower()

    def is_a_header_line(self, line: str):
        name, _, value = line.partition(':')
        return ' ' not in name


class StaticHtmlSiteBuilder(ISiteBuilder):
    def __init__(self, output_directory: str):
        self._output_directory = output_directory
        self.date_format = '%d %b, %Y (%a) %H:%M'
        self.log = logging.getLogger(__class__.__name__)
        self.CSS_STYLE="""
* { font-family: Arial, Helvetica}
ul {padding:0;}
li { padding:0.75cm 0 0.75cm 0; border-top: 1px solid #ccc; }
a.title { font-size: 120%; text-decoration: none; }
.sender { color: #333; }
.date { font-size: 80%; }
        """

    def build_site(self, pages: Iterable[EmailPage]):
        self.log.debug(f'Creating a static site in "{self._output_directory}"')
        os.makedirs(self._output_directory, exist_ok=True)
        index_lines = []
        index_lines.append(f"""
        <!doctype html><html lang="en">
        <head>
          <meta charset="utf-8">
          <title>News {datetime.now().strftime(self.date_format)}</title>
        <style>
        {self.CSS_STYLE}
        </style>
        </head>
        <body>
        <ul>
        """)
        n = 0
        for page in pages:
            filename = self.save_page_to_a_file(page)
            sender = self.get_sender(page)
            index_lines.append(f"""
            <li>
                <a class="title" href="./{filename}">{html.escape(page.subject)}</a> — <span class="sender">{sender}</span> / <span class="date">{page.date.strftime(self.date_format)}</span>
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

    def get_sender(self, page):
        sender, _, __ = page.sender.partition('<')
        return html.escape(sender).strip(' ')

    def save_page_to_a_file(self, page):
        filename = page.id.replace('@', '').replace('.', '') + '.html'
        with open(os.path.join(self._output_directory, filename), 'w') as f:
            f.write(page.text)
            f.write("\n\n<!-- Headers:\n")
            f.write("\n".join(f'{n}: {v}' for n,v in page.headers))
            f.write("\n\n-->\n")
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
                 headers TEXT,
                 body TEXT
            );
            """)

    def save_page(self, page: EmailPage):
        self.log.debug(f'Saving page {page}')
        with self.connection:
            try:
                self.connection.execute("""
                INSERT INTO page(id, message_timestamp, sender, subject, content_type, body)
                VALUES(:id, :message_timestamp, :sender, :subject, :content_type, :headers, :body)
                """, {
                    'id': page.id,
                    'message_timestamp': int(page.date.timestamp()),
                    'sender': page.sender,
                    'subject': page.subject,
                    'content_type': page.content_type,
                    'headers': pickle.dumps(page.headers),
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
                    headers=pickle.loads(row['headers']),
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
        try:
            page = self.parser.get_page()
            self.registry.save_page(page)
        except Exception as e:
            self.logger.error("Unable to save page from stdin: " + str(e))
            traceback.print_exc(file=sys.stderr)
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
    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(name)s\t%(message)s', level=logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stderr))
    Application().run()
