"""Database connection helper. The password is asked for once and never stored."""
import argparse
import getpass
import os

import psycopg2

DB_NAME = "orvane"


def add_connection_args(parser: argparse.ArgumentParser):
    parser.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    parser.add_argument("--port", default=os.environ.get("PGPORT", "5432"))
    parser.add_argument("--user", default=os.environ.get("PGUSER", "postgres"))


def password(args):
    if not getattr(args, "_password", None):
        args._password = os.environ.get("PGPASSWORD") or getpass.getpass(f"PostgreSQL password for {args.user}: ")
    return args._password


def connect(args, dbname=DB_NAME):
    return psycopg2.connect(host=args.host, port=args.port, user=args.user,
                            password=password(args), dbname=dbname)
