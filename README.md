V1.0

Backup instruction:

Make backup: 
mkdir -p backups
python manage.py dumpdata --natural-foreign --natural-primary --indent 2 > backups/dump_$(date +%Y-%m-%d_%H-%M).json

Restore backup:
python manage.py loaddata backups/YOUR_dump.json

All files in rent_system/backups
