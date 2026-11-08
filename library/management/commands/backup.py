import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Back up the database and private files to a timestamped directory. Pause writes during backup.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', default='backups')

    def handle(self, *args, **options):
        folder = Path(options['directory']) / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder.mkdir(parents=True, exist_ok=False)
        if connection.vendor == 'sqlite':
            import sqlite3
            connection.ensure_connection()
            with sqlite3.connect(folder / 'database.sqlite3') as destination:
                connection.connection.backup(destination)
        else:
            pg_dump = shutil.which('pg_dump')
            if not pg_dump:
                raise CommandError('Install PostgreSQL client tools and add pg_dump to PATH.')
            db = settings.DATABASES['default']
            env = os.environ.copy()
            env.update(PGPASSWORD=db['PASSWORD'], PGSSLMODE=db.get('OPTIONS', {}).get('sslmode', 'prefer'))
            result = subprocess.run([pg_dump, '-Fc', '--host', str(db['HOST']), '--port', str(db['PORT']),
                                     '--username', db['USER'], '--dbname', db['NAME'], '--file', str(folder / 'database.dump')],
                                    env=env, capture_output=True)
            if result.returncode:
                raise CommandError('pg_dump failed. Check PostgreSQL connection and client version; no credentials are printed.')
        with tarfile.open(folder / 'private_media.tar.gz', 'w:gz') as archive:
            if settings.MEDIA_ROOT.exists():
                archive.add(settings.MEDIA_ROOT, arcname='private_media')
        self.stdout.write(self.style.SUCCESS(f'Backup saved: {folder.resolve()}'))
