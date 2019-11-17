# Problem

So, I get a lot of new emails, but these are all sent to a separate folder for me to read later, when I have time.  But I don't like to switch my email client from folder to folder as it takes to much clicks (taps on the cellphone)

# Solution

Send the emails to a tool that will build a simple static website.

# Using

Pipe to:

```bash
email2html -o /path/to/site/directory -d /path/to/database/file.sqlite3 -D 120
```

Where `-D`  sets the number of days to include into the index.  

All emails are parsed and saved in a SQLlite3 DB file. The index is then built from this database.  The `-D` tells how many last days to include to the index page. 